# MEME-KEEPER 🐋🤖

**An AI agent that trades memecoin signals and EXECUTES real onchain transactions through KeeperHub.**

Built for the [KeeperHub — Agents Onchain Hackathon](https://dorahacks.io/hackathon/agents-onchain/detail).

> *"A working transaction that executes through KeeperHub beats a polished demo
> that never touches a chain."* — the hackathon's rule #1.

MEME-KEEPER watches the memecoin market, **decides** when something matters,
and **executes a real blockchain transaction** using KeeperHub as its execution
layer — with simulation before signing, stable idempotency keys, status polling
and a full audit trail. No fake demos: every execution produces a
transaction hash on the explorer.

## The problem (the "last mile")

Most agent demos stop at *reasoning*: the agent prints what it *would* do.
The hard part is *acting* — moving value onchain with guarantees. MEME-KEEPER
is built around that last mile: signals → decision → **executed transaction**,
through KeeperHub's reliability layer (sponsored gas, gas estimation with
backoff, idempotent submissions, native audit trail).

## How it works

```
signals (free)                       decision                  execution (KeeperHub)
┌─────────────┐      ┌──────────┐    ┌───────────┐    ┌──────────────────────────────┐
│ 🐋 whale    │      │          │    │ score ≥   │    │ Direct Execution API         │
│ 📈 momentum │─────▶│ signals  │───▶│ threshold │───▶│ /execute/transfer            │
│ 🔗 onchain  │      │          │    │           │    │ /execute/contract-call       │
│ (read)      │      └──────────┘    └───────────┘    │ /execute/check-and-execute   │
└─────────────┘                                       │  + simulate (preflight)      │
                                                      │  + Idempotency-Key (stable)  │
                                                      │  + status polling + retries  │
                                                      └──────────────┬───────────────┘
                                                                     ▼
                                              audit trail (local JSONL: the WHY
                                              + KeeperHub audit: the HOW — gas,
                                              hash, receipts)
```

### Signals (all free, no paid APIs)
| Signal | Source | What it detects |
|---|---|---|
| 🐋 Whale | BaseScan / Etherscan API | Large token transfers in the last N minutes |
| 📈 Momentum | CoinGecko API | 24h price change above threshold |
| 🔗 Onchain read | KeeperHub `contract-call` (read) | Any contract value (balance, pool price, …) |

### Execution (the point of the hackathon)
- **Preflight simulation** — `preflight_then_execute()` never broadcasts unless
  `success=true` and `wouldRevert=false` (the safe first-write sequence from
  KeeperHub's docs).
- **Stable Idempotency-Key** — derived from the *work*
  (`taskId|chain|recipient|amount|token`, SHA-256), so retries never double-spend.
- **Status polling** — bounded backoff until the receipt confirms the outcome.
- **Three execution modes**: native transfer, ERC-20 transfer, contract call
  (e.g. a Uniswap V2 swap). `check-and-execute` is also exposed: decide AND
  execute in a single onchain-verified call.

### Reliability & observability (what the judges ask for)
- Gas: KeeperHub handles estimation + sponsorship (mainnet Ethereum);
  the client adds a configurable `gasLimitMultiplier`.
- Retries: idempotent by design, `idempotentReplay` marker respected.
- Audit: every signal, decision, simulation, broadcast and resolution is
  written to `audit/audit.jsonl` (the WHY), complementing KeeperHub's own
  audit trail (the HOW: tx hash, gas, receipts).

## Safety (what the agent NEVER does)

- Never broadcasts without a passing simulation.
- Never duplicates a transaction (stable idempotency keys).
- Throttled: max transactions per hour + per-transaction cap in config.
- `--confirm` asks for manual confirmation before any broadcast.
- `--simulate` mode makes broadcasting impossible.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env                    # add KH_API_KEY (Settings → API Keys)
cp config.example.json config.json      # token address, thresholds, recipient

python verify.py                        # diagnose: key, wallet, chains, simulation
python agent.py --once                  # one scan (observation mode without a key)
python agent.py --watch                 # monitor the market in a loop
python agent.py --simulate              # safe: simulates, never broadcasts
python agent.py --selftest              # offline end-to-end test (no network)
python demo.py                          # full cycle with a REAL transaction
python scripts/create_workflow.py       # create a KeeperHub sweep workflow
```

## Proof of execution

Every real run ends with an explorer link, e.g.:

```
https://basescan.org/tx/0x...
```

That link — plus the demo video and this repository — is the submission.

## Project layout

| File | Role |
|---|---|
| `keeperhub.py` | REST client for the Direct Execution API + idempotency + polling |
| `signals.py` | Whale watch, price momentum, onchain reads |
| `agent.py` | The loop: monitor → decide → execute → audit |
| `audit.py` | Local JSONL audit trail (the WHY of every transaction) |
| `demo.py` | Scripted demo for the submission video |
| `verify.py` | Setup diagnostics |
| `scripts/create_workflow.py` | KeeperHub workflow surface (sweep builder) |
| `SETUP.md` | Full step-by-step setup |

## Stack

Python 3 · KeeperHub Direct Execution API · BaseScan/Etherscan API ·
CoinGecko API · Base (EVM) — gas ~$0.001/tx, sponsored gas available on mainnet.
