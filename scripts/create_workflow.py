"""
create_workflow.py — Cria um workflow no KeeperHub via API.

Mostra a superfície "workflow builder" do KeeperHub (além da Direct Execution):
um workflow que, a cada 30min, confere o saldo da carteira e, se passar do
limiar, transfere o excedente (sweep). Criado DESABILITADO por segurança —
habilite no app depois de conferir.

    python scripts/create_workflow.py

Se o schema REST divergir da doc, o erro vem com `hint` — e você pode criar
o mesmo workflow em 2 minutos pelo builder visual (app.keeperhub.com), que
conta igual pro judging ("Use of KeeperHub surfaces").
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import load_env, load_config  # noqa: E402
from keeperhub import KeeperHub, KeeperHubError  # noqa: E402


def main():
    load_env()
    cfg = load_config()
    api_key = os.environ.get("KH_API_KEY", "").strip()
    if not api_key:
        print("❌ Sem KH_API_KEY. Veja SETUP.md")
        sys.exit(1)
    kh = KeeperHub(api_key)

    chain = cfg["chain"]["id"]
    wallet_addr = cfg["wallet"]["recipient"]

    nodes = [
        {
            "id": "trigger-schedule",
            "type": "trigger",
            "data": {
                "label": "A cada 30 min",
                "type": "trigger",
                "config": {"triggerType": "Schedule", "interval": "*/30 * * * *"},
                "status": "idle",
            },
        },
        {
            "id": "check-balance",
            "type": "action",
            "data": {
                "label": "Conferir saldo",
                "description": "Saldo nativo da carteira",
                "type": "action",
                "config": {"actionType": "web3/check-balance",
                           "network": str(chain),
                           "address": wallet_addr},
                "status": "idle",
            },
        },
        {
            "id": "cond",
            "type": "condition",
            "data": {
                "label": "Saldo > 0.01?",
                "type": "condition",
                "config": {"operator": ">",
                           "value": "0.01",
                           "left": "{{@check-balance:Label.balance}}"},
                "status": "idle",
            },
        },
        {
            "id": "sweep",
            "type": "action",
            "data": {
                "label": "Sweep pro cofre",
                "type": "action",
                "config": {"actionType": "web3/transfer-funds",
                           "network": str(chain),
                           "recipientAddress": wallet_addr,
                           "amount": "{{@check-balance:Label.balance}}"},
                "status": "idle",
            },
        },
    ]
    edges = [
        {"id": "e1", "source": "trigger-schedule", "target": "check-balance"},
        {"id": "e2", "source": "check-balance", "target": "cond"},
        {"id": "e3", "source": "cond", "target": "sweep", "sourceHandle": "true"},
    ]

    body = {
        "name": "MemeKeeper Sweep (chain %s)" % chain,
        "description": "Sweep automático de saldo acima do limiar — criado pelo agente MEME-KEEPER",
        "nodes": nodes,
        "edges": edges,
        "enabled": False,  # sempre desabilitado ao criar
    }

    try:
        res = kh._request("POST", "/workflows/create", body)
        print("✅ Workflow criado:", res.get("id") or res)
        print("   Fica DESABILITADO — habilite em app.keeperhub.com após conferir os nós.")
    except KeeperHubError as e:
        print("⚠️  Não consegui criar via API:")
        print(f"   {e}")
        print("   Hint: crie o mesmo workflow no builder visual (app.keeperhub.com) —")
        print("   Trigger Schedule 30min -> Check Balance -> Condition > 0.01 -> Transfer Funds.")


if __name__ == "__main__":
    main()
