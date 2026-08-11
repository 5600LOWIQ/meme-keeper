"""
audit.py — Audit trail local do agente.

Cada evento relevante vira uma linha JSONL em audit/audit.jsonl:
  signal, decision, simulate, broadcast, status, resolution, error

Isso complementa o audit trail nativo do KeeperHub (painel Runs / receipts):
aqui guardamos o PORQUÊ (o sinal que justificou a transação) — o KeeperHub
guarda o COMO (gas, hash, receipt). Juntos formam a trilha completa que o
judging de "Reliability and observability" procura.
"""

import datetime as dt
import json
import os
import uuid


class Audit:
    def __init__(self, audit_dir="audit"):
        self.audit_dir = audit_dir
        os.makedirs(audit_dir, exist_ok=True)
        self.path = os.path.join(audit_dir, "audit.jsonl")
        self.session_id = uuid.uuid4().hex[:8]

    def _entry(self, event, **fields):
        entry = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "session": self.session_id,
            "event": event,
            **fields,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def signal(self, source, score, detail):
        return self._entry("signal", source=source, score=score, detail=detail)

    def decision(self, score, threshold, action, reason):
        return self._entry("decision", score=score, threshold=threshold,
                           action=action, reason=reason)

    def simulate(self, ok, payload, response):
        return self._entry("simulate", ok=bool(ok), payload=payload,
                           response=response)

    def broadcast(self, execution_id, transaction_hash, transaction_link, sponsored=None):
        return self._entry("broadcast", execution_id=execution_id,
                           transaction_hash=transaction_hash,
                           transaction_link=transaction_link,
                           sponsored=sponsored)

    def status(self, execution_id, status, receipts=None):
        return self._entry("status", execution_id=execution_id,
                           status=status, receipts=receipts)

    def resolution(self, execution_id, outcome, detail):
        return self._entry("resolution", execution_id=execution_id,
                           outcome=outcome, detail=detail)

    def error(self, where, message, code=None):
        return self._entry("error", where=where, message=message, code=code)

    def tail(self, n=10):
        if not os.path.exists(self.path):
            return []
        lines = open(self.path, encoding="utf-8").read().strip().splitlines()
        return [json.loads(l) for l in lines[-n:]]
