"""
verify.py — Diagnóstico do setup antes de rodar o agente.

    python verify.py

Checa: chave de API, conexão com a API, carteira Turnkey, workflows
existentes e uma simulação de transferência (não transmite nada).
"""

import os
import sys

from agent import load_env, load_config
from keeperhub import KeeperHub, KeeperHubError

OK = "✅"
WARN = "⚠️ "
FAIL = "❌"


def main():
    load_env()
    cfg = load_config()
    env = os.environ
    ok_count = 0
    warn_count = 0

    api_key = env.get("KH_API_KEY", "").strip()
    if not api_key:
        print(f"{FAIL} KH_API_KEY ausente. Veja SETUP.md (app.keeperhub.com -> Settings -> API Keys).")
        sys.exit(1)
    if not api_key.startswith("kh_"):
        print(f"{WARN} KH_API_KEY não começa com kh_ — confira se copiou a chave certa.")

    kh = KeeperHub(api_key)
    print(f"{OK} chave configurada (…{api_key[-6:]})")

    # 1) conexão + chains
    try:
        chains = kh.get_chains()
        names = [c.get("name") for c in chains] if isinstance(chains, list) else []
        print(f"{OK} API respondeu — {len(names)} chains suportadas: {', '.join(names[:6])}")
        ok_count += 1
    except KeeperHubError as e:
        print(f"{FAIL} API inacessível: {e}")
        sys.exit(1)

    # 2) carteira Turnkey
    try:
        w = kh.get_wallet()
        addr = (w or {}).get("address") or (w or {}).get("walletAddress")
        print(f"{OK} carteira Turnkey: {addr}")
        ok_count += 1
    except KeeperHubError as e:
        print(f"{WARN} carteira: {e} (hint: {e.hint}) — provisiona em app.keeperhub.com (Wallet)")
        warn_count += 1

    # 3) workflows existentes
    try:
        wfs = kh.list_workflows()
        n = len(wfs) if isinstance(wfs, list) else 0
        print(f"{OK} {n} workflow(s) na organização")
        ok_count += 1
    except KeeperHubError as e:
        print(f"{WARN} workflows: {e}")
        warn_count += 1

    # 4) simulação de transferência (não transmite!)
    chain = cfg["chain"]["id"]
    recipient = cfg["wallet"]["recipient"]
    amount = cfg["execution"].get("amount", "0.0001")
    try:
        res = kh.transfer(chain, recipient, amount, simulate=True)
        if res.get("success", True) and not res.get("wouldRevert", False):
            print(f"{OK} simulação de transferência {amount} na chain {chain}: OK (sem transmitir)")
            ok_count += 1
        else:
            print(f"{WARN} simulação retornou: {res}")
            warn_count += 1
    except KeeperHubError as e:
        print(f"{WARN} simulação: {e} (code={e.code}) — "
              f"{'carteira sem fundos? carregue um pouco de Base ETH' if e.code == 'insufficient_balance' else 'veja hint'}")
        warn_count += 1

    print(f"\n{OK} {ok_count} ok · {warn_count} atenção")
    if warn_count:
        print("Veja SETUP.md para os passos pendentes.")
    else:
        print("Setup pronto — rode: python agent.py --once")


if __name__ == "__main__":
    main()
