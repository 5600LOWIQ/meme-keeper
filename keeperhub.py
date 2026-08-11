"""
keeperhub.py — Cliente REST do KeeperHub (execution layer onchain).

Usa a Direct Execution API: https://docs.keeperhub.com/api/direct-execution
Tudo aqui segue o padrão seguro recomendado pela própria API:

  1. SIMULATE primeiro (não assina, não transmite, não custa nada)
  2. Se success=true e wouldRevert=false, transmite de verdade
  3. Com Idempotency-Key estável (a mesma chave na simulação e na transmissão
     NÃO é necessária — a chave identifica o TRABALHO, não a tentativa)
  4. Pola GET /api/execute/{executionId}/status até concluir

Sem chave de API, nada aqui funciona — exceto GET /api/chains (público).
"""

import hashlib
import json
import re
import time

import requests

BASE_URL = "https://app.keeperhub.com/api"


class KeeperHubError(Exception):
    """Erro da API do KeeperHub. `code` é o código estável (ex.: insufficient_balance)."""

    def __init__(self, message, code=None, status=None, hint=None, request_id=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.hint = hint
        self.request_id = request_id


# ---------------------------------------------------------------------------
# Canonicalização (regras da doc: Idempotency-Key determinística)
# ---------------------------------------------------------------------------

def canonical_amount(a) -> str:
    """Normaliza um valor para string decimal canônica (ex.: '0.1000' -> '0.1')."""
    s = str(a).strip()
    if s.startswith(("+", "-")):
        raise ValueError(f"amount inválido (sem sinal): {a!r}")
    if "e" in s.lower():
        raise ValueError(f"amount inválido (sem notação científica): {a!r}")
    if not re.match(r"^(\d+\.?\d*|\.\d+)$", s):
        raise ValueError(f"amount inválido: {a!r}")
    if "." in s:
        i, f = s.split(".", 1)
        i = i.lstrip("0") or "0"
        f = f.rstrip("0")
        return i if f == "" else f"{i}.{f}"
    return s.lstrip("0") or "0"


def stable_idempotency_key(task_id, chain_id, recipient, amount, token=""):
    """Deriva a Idempotency-Key do TRABALHO (estável entre tentativas).

    taskId|chainId|recipient|amount|token, com cada parte canônica,
    hash SHA-256 em hex minúsculo. Ver docs 'Choosing a stable key'.
    """
    parts = [
        str(task_id).strip().replace("%", "%25").replace("|", "%7C"),
        str(chain_id).strip(),
        str(recipient).strip().lower(),
        canonical_amount(amount),
        (str(token).strip() or "").lower(),
    ]
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

class KeeperHub:
    """Cliente fino da Direct Execution API. Cada método devolve o JSON bruto."""

    def __init__(self, api_key, base_url=BASE_URL, timeout=90):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "meme-keeper/1.0 (dorahacks-agents-onchain)",
        })

    # ---------------- baixo nível ----------------

    def _request(self, method, path, body=None, idempotency_key=None):
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            r = self.session.request(method, self.base_url + path,
                                     json=body, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise KeeperHubError(f"Falha de rede: {e}") from e

        try:
            data = r.json()
        except ValueError:
            data = {"error": r.text[:300]}

        if r.status_code >= 400:
            raise KeeperHubError(
                data.get("error") or data.get("detail") or f"HTTP {r.status_code}",
                code=data.get("code") or data.get("error"),
                status=r.status_code,
                hint=data.get("hint"),
                request_id=data.get("request_id") or r.headers.get("x-request-id"),
            )
        return data

    # ---------------- leitura ----------------

    def get_chains(self):
        """Lista as chains suportadas (público, sem auth)."""
        return self.session.get(self.base_url + "/chains", timeout=self.timeout).json()

    def get_wallet(self):
        """Info da carteira Turnkey da organização."""
        return self._request("GET", "/integrations/wallet")

    def list_workflows(self):
        return self._request("GET", "/workflows")

    def execution_status(self, execution_id):
        """Status da execução, com receipts (prova onchain) e sponsored flag."""
        return self._request("GET", f"/execute/{execution_id}/status")

    # ---------------- escrita (Direct Execution) ----------------

    def transfer(self, chain_id, recipient_address, amount,
                 token_address=None, token_config=None,
                 gas_limit_multiplier=None, simulate=False,
                 idempotency_key=None):
        """Transfere nativo (ETH/Base ETH) ou ERC-20."""
        body = {
            "chainId": str(chain_id),
            "recipientAddress": recipient_address,
            "amount": canonical_amount(amount),
        }
        if token_address:
            body["tokenAddress"] = token_address
        if token_config:
            body["tokenConfig"] = token_config
        if gas_limit_multiplier:
            body["gasLimitMultiplier"] = str(gas_limit_multiplier)
        if simulate:
            body["simulate"] = True
        return self._request("POST", "/execute/transfer", body, idempotency_key)

    def contract_call(self, chain_id, contract_address, function_name,
                      function_args=None, abi=None, value=None,
                      gas_limit_multiplier=None, simulate=False,
                      idempotency_key=None):
        """Chama qualquer função de contrato (read vira read, write vira write)."""
        body = {
            "chainId": str(chain_id),
            "contractAddress": contract_address,
            "functionName": function_name,
        }
        if function_args is not None:
            body["functionArgs"] = json.dumps(function_args)
        if abi:
            body["abi"] = json.dumps(abi) if not isinstance(abi, str) else abi
        if value is not None:
            body["value"] = canonical_amount(value)
        if gas_limit_multiplier:
            body["gasLimitMultiplier"] = str(gas_limit_multiplier)
        if simulate:
            body["simulate"] = True
        return self._request("POST", "/execute/contract-call", body, idempotency_key)

    def check_and_execute(self, chain_id, contract_address, function_name,
                          function_args, condition, action,
                          abi=None, simulate=False, idempotency_key=None):
        """Lê um valor onchain, avalia a condição e executa a ação se bater.

        É a joia do KeeperHub pra agente: decisão + execução numa chamada só,
        com o resultado da condição no retorno (observable pra audit trail).
        """
        body = {
            "chainId": str(chain_id),
            "contractAddress": contract_address,
            "functionName": function_name,
            "functionArgs": json.dumps(function_args),
            "condition": condition,
            "action": action,
        }
        if abi:
            body["abi"] = json.dumps(abi) if not isinstance(abi, str) else abi
        if simulate:
            body["simulate"] = True
        return self._request("POST", "/execute/check-and-execute", body, idempotency_key)

    # ---------------- fluxo seguro de primeira escrita ----------------

    def preflight_then_execute(self, fn, task_id, chain_id, recipient, amount,
                               token="", **kwargs):
        """Simula primeiro; só transmite se a simulação passar. Retorna (sim, real).

        `fn` é um dos métodos de escrita (transfer, contract_call...).
        `task_id` identifica o trabalho (ex.: 'sweep-2026-08-11-19h42');
        chain_id/recipient/amount/token definem o EFEITO onchain e entram na
        Idempotency-Key estável (ver docs 'Choosing a stable key').
        """
        sim = fn(simulate=True, **kwargs)
        ok = sim.get("success", True) and not sim.get("wouldRevert", False)
        if not ok:
            return sim, None
        key = stable_idempotency_key(task_id, chain_id, recipient, amount, token)
        real = fn(simulate=False, idempotency_key=key, **kwargs)
        return sim, real


# ---------------------------------------------------------------------------
# Polagem de status com backoff (reliability que o judging pede)
# ---------------------------------------------------------------------------

def poll_until_done(kh: KeeperHub, execution_id, max_wait=180, interval=5):
    """Pola o status até completed/failed, com backoff exponencial."""
    waited = 0
    while waited < max_wait:
        st = kh.execution_status(execution_id)
        status = st.get("status")
        if status in ("completed", "failed"):
            return st
        time.sleep(interval)
        waited += interval
        interval = min(interval * 1.5, 20)
    return {"status": "timeout", "executionId": execution_id, "note": "polling excedeu max_wait"}
