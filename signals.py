"""
signals.py — Motor de sinais de memecoin.

Três fontes independentes, todas grátis:
  1. BALEIA  : transferências grandes do token (Basescan / Etherscan API)
  2. MOMENTUM: variação de preço 24h (CoinGecko API)
  3. ONCHAIN : leitura direta de contrato via KeeperHub contract-call
               (read-only — não precisa de carteira nem de fundos)

Cada sinal devolve um dict com `score` (0-2). O agente soma os scores e
só executa quando passa do limiar `signals.min_score` do config.
"""

import datetime as dt
import os

import requests

from keeperhub import KeeperHub, KeeperHubError


def _now():
    return dt.datetime.now(dt.timezone.utc)


def whale_transfers(token_address, chain="base", window_minutes=10, min_value_usd=0, api_key=None):
    """Busca transferências recentes do token no explorer e devolve as grandes.

    Retorna lista de dicts: {hash, from, to, value_usd, age_min}.
    Sem API key do explorer, retorna [] (o sinal simplesmente não dispara).
    """
    if not api_key or not token_address or token_address.startswith("0x0"):
        return []

    if chain == "base":
        url = "https://api.basescan.org/api"
        decimals_url = "https://api.basescan.org/api"
    else:
        url = "https://api.etherscan.io/api"
        decimals_url = "https://api.etherscan.io/api"

    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": token_address,
        "page": 1,
        "offset": 20,
        "sort": "desc",
        "apikey": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
    except (requests.RequestException, ValueError):
        return []
    if data.get("status") != "1" or not data.get("result"):
        return []

    # decimais do token (pela 1ª transferência da lista)
    try:
        decimals = int(data["result"][0].get("tokenDecimal", "18") or "18")
    except ValueError:
        decimals = 18

    cutoff = _now() - dt.timedelta(minutes=window_minutes)
    out = []
    for tx in data["result"]:
        try:
            ts = int(tx.get("timeStamp", "0"))
        except ValueError:
            continue
        when = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        if when < cutoff:
            break  # lista é ordenada por tempo desc
        try:
            raw = int(tx.get("value", "0"))
        except ValueError:
            continue
        amount = raw / (10 ** decimals)
        # valor aproximado em USD: precisa de preço — deixamos None p/ o agente
        # enriquecer com o CoinGecko; o filtro forte é o `amount` em unidades.
        out.append({
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "amount": amount,
            "ts": when.isoformat(),
            "age_min": round((_now() - when).total_seconds() / 60, 1),
        })
    return out


def momentum(coingecko_id, min_24h_change_pct=0):
    """Variação de preço 24h via CoinGecko (grátis, sem chave)."""
    if not coingecko_id:
        return {"score": 0, "change_pct": 0.0, "price_usd": None, "note": "sem coingecko_id"}
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coingecko_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
    except (requests.RequestException, ValueError):
        return {"score": 0, "change_pct": 0.0, "price_usd": None, "note": "CoinGecko indisponível"}

    coin = (data or {}).get(coingecko_id) or {}
    change = coin.get("usd_24h_change") or 0.0
    price = coin.get("usd")
    score = 2 if change >= min_24h_change_pct else 0
    return {
        "score": score,
        "change_pct": round(change, 2),
        "price_usd": price,
        "note": f"24h {change:+.2f}% (limiar {min_24h_change_pct:+.1f}%)",
    }


def onchain_read(kh: KeeperHub, chain_id, contract_address, function_name, function_args=None, abi=None):
    """Leitura onchain via KeeperHub (read-only — nunca assina nem custa).

    Ex.: balanço de uma baleia, preço de um pool Uniswap V3 (slot0), etc.
    Retorna o resultado bruto da leitura ou None se falhar.
    """
    if kh is None:
        return None
    try:
        res = kh.contract_call(chain_id, contract_address, function_name, function_args=function_args, abi=abi)
        return res.get("result")
    except KeeperHubError:
        return None


def score_signal(signal):
    """Normaliza um sinal (qualquer fonte) pra pontuação padrão 0-2."""
    if signal is None:
        return 0
    if isinstance(signal, dict):
        return int(signal.get("score", 1 if signal.get("note") else 0))
    return 1 if signal else 0
