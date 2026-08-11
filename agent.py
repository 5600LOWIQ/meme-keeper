"""
agent.py — MEME-KEEPER: agente de memecoin que EXECUTA onchain via KeeperHub.

Fluxo (o "last mile" que o hackathon premia):
    monitora -> decide -> SIMULA -> EXECUTA de verdade -> audita

Modos:
    python agent.py --once            # uma varredura (sinais + decisão)
    python agent.py --watch           # loop com intervalo (padrão 300s)
    python agent.py --simulate        # NUNCA transmite (só simula) — seguro p/ testar
    python agent.py --selftest        # pipeline completo OFFLINE (sem rede, sem chave)

Safety integrada:
    - preflight (simulate) antes de qualquer broadcast
    - Idempotency-Key estável por trabalho (sem transação duplicada)
    - limite de transações por hora e teto por transação
    - --confirm pede confirmação manual antes de transmitir
"""

import argparse
import datetime as dt
import json
import os
import sys
import time

from audit import Audit
from keeperhub import KeeperHub, KeeperHubError, poll_until_done
from signals import momentum, onchain_read, whale_transfers

DEFAULT_INTERVAL = 300  # segundos entre varreduras no --watch


def load_env(path=".env"):
    """Carrega .env simples (KEY=value) sem dependências."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_config(path="config.json"):
    if not os.path.exists(path):
        print(f"❌ config.json não encontrado. Copie config.example.json -> config.json")
        sys.exit(1)
    return json.load(open(path, encoding="utf-8"))


# ---------------------------------------------------------------------------
# Sinais
# ---------------------------------------------------------------------------

def gather_signals(cfg, kh, env):
    """Coleta os sinais configurados e devolve (lista, score_total)."""
    s = cfg["signals"]
    results = []

    if s.get("whale", {}).get("enabled"):
        wh = s["whale"]
        key = env.get("BASESCAN_API_KEY") or env.get("ETHERSCAN_API_KEY") or ""
        chain = cfg["chain"].get("id") == "1" and "ethereum" or "base"
        txs = whale_transfers(
            wh.get("token_address", ""), chain=chain,
            window_minutes=wh.get("window_minutes", 10),
            api_key=key,
        )
        big = [t for t in txs if t.get("amount", 0) >= wh.get("min_amount", 0)]
        if wh.get("min_value_usd") and big:
            # enriquece com preço do CoinGecko p/ estimar USD
            mom = momentum(s.get("momentum", {}).get("coingecko_id", ""))
            px = mom.get("price_usd")
            if not px:
                big = []  # sem preço não dá pra medir valor — não força sinal
            else:
                big = [t for t in big if t["amount"] * px >= wh.get("min_value_usd")]
        score = min(2, len(big))
        detail = f"{len(big)} transferência(s) grande(s) em {wh.get('window_minutes', 10)}min"
        if big:
            detail += f" | maior: {big[0]['amount']:.4g} ({big[0]['age_min']}min atrás)"
        results.append({"source": "whale", "score": score, "detail": detail})
        if big:
            print(f"  🐋 whale: {detail}")

    if s.get("momentum", {}).get("enabled"):
        m = momentum(s["momentum"].get("coingecko_id", ""),
                     s["momentum"].get("min_24h_change_pct", 0))
        results.append({"source": "momentum", "score": m["score"], "detail": m["note"]})
        print(f"  📈 momentum: {m['note']}")

    if s.get("onchain", {}).get("enabled") and kh is not None:
        oc = s["onchain"]
        val = onchain_read(kh, cfg["chain"]["id"], oc["contract_address"],
                           oc["function_name"], oc.get("function_args"), oc.get("abi"))
        ok = val is not None and str(val) not in ("0", "0x0", "None")
        results.append({"source": "onchain", "score": 2 if ok else 0,
                        "detail": f"{oc['function_name']} -> {val}" if val is not None else "leitura falhou"})
        print(f"  🔗 onchain: {results[-1]['detail']}")

    total = sum(r["score"] for r in results)
    return results, total


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def build_execution(cfg, kh, task_id, simulate_only):
    """Monta e executa a ação configurada. Retorna dict de resultado."""
    ex = cfg["execution"]
    chain = cfg["chain"]["id"]
    action = ex.get("action", "transfer-native")
    recipient = cfg["wallet"]["recipient"]

    if action == "transfer-native":
        fn = kh.transfer
        kwargs = dict(chain_id=chain, recipient_address=recipient,
                      amount=ex["amount"],
                      gas_limit_multiplier=ex.get("gas_limit_multiplier"))
        label = f"transferência nativa de {ex['amount']} p/ {recipient[:10]}…"
    elif action == "transfer-token":
        fn = kh.transfer
        kwargs = dict(chain_id=chain, recipient_address=recipient,
                      amount=ex["amount"], token_address=ex["token_address"],
                      gas_limit_multiplier=ex.get("gas_limit_multiplier"))
        label = f"transferência de {ex['amount']} token p/ {recipient[:10]}…"
    elif action == "swap":
        fn = kh.contract_call
        kwargs = dict(chain_id=chain, contract_address=ex["router_address"],
                      function_name="swapExactETHForTokens",
                      function_args=[0, ex["path"], recipient,
                                     int(time.time()) + 600],
                      value=ex["amount"],
                      gas_limit_multiplier=ex.get("gas_limit_multiplier"))
        label = f"swap de {ex['amount']} ETH por token (router {ex['router_address'][:10]}…)"

    print(f"  ⚡ executando: {label}")
    if simulate_only:
        res = fn(simulate=True, **kwargs)
        print(f"  🧪 SIMULAÇÃO: success={res.get('success', 'n/a')} "
              f"wouldRevert={res.get('wouldRevert', 'n/a')}")
        return {"mode": "simulate", "response": res}

    token = kwargs.get("token_address") or ""
    sim, real = kh.preflight_then_execute(
        fn, task_id, chain, recipient, ex["amount"], token=token, **kwargs)
    if real is None:
        return {"mode": "blocked", "response": sim}
    tx = real.get("transactionHash")
    link = real.get("transactionLink")
    eid = real.get("executionId")
    print(f"  ✅ TRANSMITIDA: executionId={eid} tx={tx}")
    if link:
        print(f"  🔗 {link}")
    if eid:
        st = poll_until_done(kh, eid)
        print(f"  📡 status: {st.get('status')}")
        return {"mode": "real", "execution_id": eid, "tx": tx, "link": link,
                "status": st}
    return {"mode": "real", "execution_id": eid, "tx": tx, "link": link}


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def run_once(cfg, kh, audit, env, simulate_only, require_confirm):
    print(f"\n── varredura {dt.datetime.now().strftime('%H:%M:%S')} ──")
    results, total = gather_signals(cfg, kh, env)
    for r in results:
        audit.signal(r["source"], r["score"], r["detail"])

    threshold = cfg["signals"].get("min_score", 2)
    print(f"  score total: {total} (limiar {threshold})")

    if total < threshold:
        audit.decision(total, threshold, "none", "abaixo do limiar")
        print("  😴 nenhum sinal forte — sem transação.")
        return "noop"

    # throttle: limite de transações por hora
    hour_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    recent = [e for e in audit.tail(200)
              if e["event"] == "broadcast"
              and dt.datetime.fromisoformat(e["ts"]) >= hour_ago]
    max_per_hour = cfg["safety"].get("max_tx_per_hour", 2)
    if len(recent) >= max_per_hour:
        audit.decision(total, threshold, "blocked", "throttle por hora")
        print(f"  🛑 limite de {max_per_hour} tx/h atingido.")
        return "throttled"

    reason = "; ".join(f"{r['source']}={r['score']}" for r in results)
    audit.decision(total, threshold, cfg["execution"].get("action"), reason)
    print(f"  🎯 sinal forte ({reason}) -> EXECUTAR")

    task_id = f"meme-keeper-{dt.datetime.now().strftime('%Y-%m-%d-%H%M')}"
    if require_confirm:
        ok = input("    transmitir de verdade? [s/N] ").strip().lower() in ("s", "sim", "y", "yes")
        if not ok:
            audit.decision(total, threshold, "cancelled", "confirmação manual negada")
            print("  ✋ cancelado pelo usuário.")
            return "cancelled"

    try:
        res = build_execution(cfg, kh, task_id, simulate_only)
    except KeeperHubError as e:
        audit.error("execute", str(e), code=e.code)
        print(f"  ❌ erro: {e} (hint: {e.hint})")
        return "error"

    if res["mode"] == "simulate":
        audit.simulate(res["response"].get("success"), cfg["execution"], res["response"])
        return "simulated"
    if res["mode"] == "blocked":
        audit.simulate(False, cfg["execution"], res["response"])
        print("  🛑 simulação falhou — nada transmitido.")
        return "blocked"

    audit.broadcast(res.get("execution_id"), res.get("tx"), res.get("link"))
    if res.get("status"):
        audit.status(res["execution_id"], res["status"].get("status"),
                     receipts=res["status"].get("receipts"))
        audit.resolution(res["execution_id"], res["status"].get("status"),
                         res["status"].get("receiptStatus") or "")
    return "executed"


def selftest():
    """Pipeline completo OFFLINE: sinal fake -> decisão -> simulação -> auditoria."""
    print("🧪 SELFTEST (offline, sem rede e sem chave)...")
    cfg = {
        "chain": {"id": "8453", "name": "Base", "explorer": "https://basescan.org"},
        "wallet": {"recipient": "0x742d35cc6634c0532925a3b844bc454e4438f44e"},
        "execution": {"action": "transfer-native", "amount": "0.0001",
                      "gas_limit_multiplier": "1.2"},
        "signals": {"whale": {"enabled": False},
                    "momentum": {"enabled": False},
                    "min_score": 1},
        "safety": {"max_tx_per_hour": 2},
        "audit_dir": "audit",
    }

    class FakeKH:
        def transfer(self, **kw):
            assert kw["simulate"] is True, "selftest deve rodar só em simulação"
            return {"success": True, "wouldRevert": False, "executionId": "fake"}

    audit = Audit("audit")
    # injeta um sinal fake forte
    fake_signal = {"source": "fake", "score": 2,
                   "detail": "sinal injetado no selftest"}
    results = [fake_signal]
    total = sum(r["score"] for r in results)

    assert total >= cfg["signals"]["min_score"], "decisão deveria disparar"
    audit.decision(total, 1, "transfer-native", "selftest")
    audit.simulate(True, {}, {"success": True, "wouldRevert": False})

    res = FakeKH().transfer(chain_id="8453", recipient_address="0x0",
                            amount="0.0001", simulate=True)
    assert res["success"] and not res["wouldRevert"], "simulação fake falhou"

    # valida canonical_amount e idempotency
    from keeperhub import canonical_amount, stable_idempotency_key
    assert canonical_amount("0.1000") == "0.1"
    assert canonical_amount("007") == "7"
    assert canonical_amount(".5") == "0.5"
    k1 = stable_idempotency_key("t", "8453", "0xABC", "0.001")
    k2 = stable_idempotency_key("t", "8453", "0xabc", "0.0010")
    assert k1 == k2, "chave idempotente deve ser estável entre tentativas"

    print("✅ SELFTEST PASSOU — pipeline, auditoria e idempotency OK.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="MEME-KEEPER: agente memecoin que executa onchain via KeeperHub")
    ap.add_argument("--once", action="store_true", help="uma varredura só")
    ap.add_argument("--watch", action="store_true", help="loop contínuo")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                    help=f"segundos entre varreduras (padrão {DEFAULT_INTERVAL})")
    ap.add_argument("--simulate", action="store_true",
                    help="NUNCA transmite — só simula (seguro)")
    ap.add_argument("--confirm", action="store_true",
                    help="pede confirmação manual antes de transmitir")
    ap.add_argument("--selftest", action="store_true", help="teste offline do pipeline")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    load_env()
    cfg = load_config()
    env = os.environ
    audit = Audit(cfg.get("audit_dir", "audit"))

    kh = None
    api_key = env.get("KH_API_KEY", "").strip()
    if api_key and not api_key.startswith("kh_"):
        print("⚠️  KH_API_KEY parece inválida (deve começar com kh_). Veja SETUP.md")
    if api_key:
        kh = KeeperHub(api_key)
    else:
        print("⚠️  Sem KH_API_KEY — modo observação (sinais sim, execução não).")

    # destinatário 0x0 = a própria carteira Turnkey (resolve automaticamente)
    recipient = cfg["wallet"].get("recipient", "")
    if recipient.replace("0x", "").strip("0") == "":
        if kh is None:
            print("⚠️  destinatário 0x0 precisa da KH_API_KEY p/ resolver a própria carteira.")
        else:
            try:
                w = kh.get_wallet()
                addr = (w or {}).get("address") or (w or {}).get("walletAddress")
                if addr:
                    cfg["wallet"]["recipient"] = addr
                    print(f"ℹ️  destinatário = carteira do próprio agente: {addr}")
            except KeeperHubError as e:
                print(f"⚠️  não resolvi a carteira: {e} — configure wallet.recipient no config.json")

    if args.once or not (args.watch or args.once):
        run_once(cfg, kh, audit, env, args.simulate, args.confirm)
    elif args.watch:
        print(f"👁  monitorando a cada {args.interval}s. Ctrl+C para parar.")
        try:
            while True:
                run_once(cfg, kh, audit, env, args.simulate, args.confirm)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 parado.")


if __name__ == "__main__":
    main()
