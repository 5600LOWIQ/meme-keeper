"""
demo.py — Roteiro da demo pro vídeo de submissão.

    python demo.py            # roda o ciclo completo (pergunta antes de transmitir)
    python demo.py --auto     # transmite sem perguntar (cuidado: gasta tx real)

O que o vídeo deve mostrar (narração sua por cima):
  1. O agente "acordando" e lendo os sinais do mercado de memecoin
  2. O sinal forte disparando (whale / momentum)
  3. A SIMULAÇÃO (não custa nada, prova que a tx não vai reverter)
  4. A EXECUÇÃO REAL via KeeperHub — com o hash e o link do explorer
  5. O audit trail completo (por que o agente fez aquilo)

Isso é literalmente o critério nº 1 do judging: "a working transaction
that executes through KeeperHub beats a polished demo that never touches a chain".
"""

import argparse
import datetime as dt
import os
import sys
import time

from agent import build_execution, gather_signals, load_env, load_config
from audit import Audit
from keeperhub import KeeperHub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="não pergunta antes de transmitir")
    ap.add_argument("--force", action="store_true",
                    help="demo scriptada: executa mesmo sem sinal forte (para o vídeo)")
    args = ap.parse_args()

    load_env()
    cfg = load_config()
    env = os.environ
    audit = Audit(cfg.get("audit_dir", "audit"))

    api_key = env.get("KH_API_KEY", "").strip()
    if not api_key:
        print("❌ Sem KH_API_KEY. Veja SETUP.md")
        sys.exit(1)
    kh = KeeperHub(api_key)

    # destinatário 0x0 = própria carteira (sweep seguro, sem queimar fundos)
    recipient = cfg["wallet"].get("recipient", "")
    if recipient.replace("0x", "").strip("0") == "":
        addr = kh.get_org_wallet_address()
        if addr:
            cfg["wallet"]["recipient"] = addr
            print(f"ℹ️  destinatário = carteira do próprio agente: {addr}")
        else:
            print("❌ Não resolvi a carteira — configure wallet.recipient no config.json")
            sys.exit(1)

    print("=" * 62)
    print("  MEME-KEEPER — agente de memecoin executando onchain via KeeperHub")
    print(f"  {dt.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · chain {cfg['chain']['name']}")
    print("=" * 62)

    # 1) sinais
    print("\n[1/4] LENDO SINAIS DO MERCADO...")
    results, total = gather_signals(cfg, kh, env)
    for r in results:
        audit.signal(r["source"], r["score"], r["detail"])
    threshold = cfg["signals"].get("min_score", 2)
    print(f"      score: {total} / limiar {threshold}")
    if total < threshold and not args.force:
        print("      (sem sinal forte agora — rode com --force ou ajuste o config)")
        print("      Encerrando demo em modo observação. Nada foi transmitido.")
        return
    if total < threshold and args.force:
        print("      (--force: demo scriptada — executa mesmo sem sinal forte, para o vídeo)")

    # 2) decisão
    print("\n[2/4] DECISÃO: sinal forte detectado — executar transação real")
    reason = "; ".join(f"{r['source']}={r['score']}" for r in results)
    audit.decision(total, threshold, cfg["execution"].get("action"), reason)

    # 3) execução com preflight
    print("\n[3/4] EXECUÇÃO VIA KEEPERHUB (simula -> transmite -> confirma)")
    task_id = f"demo-{dt.datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
    if not args.auto:
        ok = input("      transmitir de verdade? [s/N] ").strip().lower() in ("s", "sim", "y", "yes")
        if not ok:
            print("      cancelado — demo encerrada sem transação.")
            return
    res = build_execution(cfg, kh, task_id, simulate_only=False)
    audit.broadcast(res.get("execution_id"), res.get("tx"), res.get("link"))
    if res.get("status"):
        audit.status(res["execution_id"], res["status"].get("status"),
                     receipts=res["status"].get("receipts"))

    # 4) audit trail
    print("\n[4/4] AUDIT TRAIL (o porquê de cada passo)")
    for e in audit.tail(8):
        print(f"      {e['ts'][11:19]} {e['event']:<10} {e.get('detail') or e.get('action') or e.get('status') or ''}")

    if res.get("link"):
        print("\n🎬 PROVA ONCHAIN (cole no vídeo e na submissão):")
        print(f"   {res['link']}")
    print("\nDemo completa. Este log inteiro é o roteiro do seu vídeo.")


if __name__ == "__main__":
    main()
