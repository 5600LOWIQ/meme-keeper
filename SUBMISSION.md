# SUBMISSION — roteiro final (30-40 min)

Tudo que falta é **3 coisas que só você pode fazer** (contas + dinheiro).
O resto está pronto neste repositório. Siga a ordem — não pule passos.

---

## 🥇 PASSO 1 — Subir o código pro GitHub (~10 min)

O repositório já está inicializado e com o primeiro commit feito.
Só falta criar o repo no GitHub e enviar. Duas opções:

**Opção A (recomendada, instala o gh uma vez):**
```bash
winget install --id GitHub.cli
gh auth login        # abre navegador — autorize
cd 19-keeperhub-agent
gh repo create meme-keeper --public --source . --remote origin --push
```

> ✅ **Já feito** — repo publicado: https://github.com/5600LOWIQ/meme-keeper

**Opção B (sem instalar nada):**
1. Acesse https://github.com/new → nome do repo: `meme-keeper` → **Public** → Create.
2. Depois, no terminal:
```bash
cd 19-keeperhub-agent
git remote add origin https://github.com/SEU_USUARIO/meme-keeper.git
git push -u origin main
```

> ⚠️ Confira que `.env` e `config.json` estão no `.gitignore` (estão) — **nunca** suba chaves.

---

## 🥈 PASSO 2 — Conta no KeeperHub + API key (~10 min)

1. Acesse https://app.keeperhub.com → crie conta (email).
2. A plataforma **provisiona automaticamente** sua carteira Turnkey (não-custodial)
   e uma **cota mensal de gas patrocinado** na mainnet. Você não faz nada além de entrar.
3. **Settings → API Keys → Organisation** → crie uma chave (começa com `kh_`).
4. Copie pro arquivo `.env` deste projeto:
   ```
   KH_API_KEY=kh_sua_chave_aqui
   ```
5. Teste: `python verify.py` — deve mostrar ✅ em tudo (exceto talvez a simulação
   de transferência, que pede fundos — próximo passo).

---

## 🥉 PASSO 3 — Botar R$ 10-30 de Base ETH na carteira (~10 min)

O gas é patrocinado; o **valor movido** não. Base é a rede mais barata do mundo
(gas ~US$ 0,001 por transação) e o agente já está configurado pra ela.

1. No app do KeeperHub, copie o endereço da carteira (**Wallet**).
2. Mande um pouquinho de **Base ETH** (rede **Base**, não Ethereum mainnet!)
   pra esse endereço — saque direto da corretora que você já usa. R$ 10-30 basta.
3. Confira: `python verify.py` — a simulação deve dar ✅.
4. Ajuste no `config.json` se quiser:
   - `wallet.recipient` → seu endereço (0x0 = o agente resolve sozinho a própria carteira);
   - `signals.whale.token_address` → contrato do memecoin que quer vigiar;
   - `signals.momentum.coingecko_id` → id no CoinGecko (ex.: `pepe`);
   - `signals.min_score` → limiar (2 = precisa sinal forte).

---

## 📹 PASSO 4 — Rodar a demo e gerar a transação REAL (~5 min)

```bash
python demo.py
```
O demo pergunta antes de transmitir. Responda **s**.
No fim ele imprime o **transactionLink** (ex.: `https://basescan.org/tx/0x...`).
**Copie esse link** — é a prova onchain da submissão.

---

## 🎬 PASSO 5 — Gravar o vídeo demo (~10 min)

**Não precisa aparecer o rosto.** É gravação de tela + sua voz narrando.
Opcional: OBS Studio (grátis) ou a gravação de tela do Windows (Win+G).

**Roteiro (5 min, fala por fala):**

1. **(0:00)** "Este é o MEME-KEEPER: um agente de IA que monitora o mercado de
   memecoins e executa transações reais na blockchain através do KeeperHub."
   → Mostre o `README.md` e o `config.json` na tela.
2. **(0:40)** "O agente usa três sinais grátis: baleias movendo o token,
   momentum de preço e leituras onchain direto via KeeperHub."
   → Rode `python agent.py --once` e mostre os sinais coletados.
3. **(1:30)** "Antes de qualquer transação, o agente SIMULA — sem assinar,
   sem gastar, sem risco. Só transmite se a simulação passar."
   → Rode `python agent.py --simulate` (mostra o preflight).
4. **(2:30)** "Agora a execução real." → Rode `python demo.py`, responda **s**.
   → Narre: "o sinal disparou, a simulação passou, o KeeperHub estimou o gas,
   a transação foi transmitida com idempotency e estamos aguardando o receipt."
5. **(3:30)** "Aqui está a prova na blockchain." → Abra o `transactionLink` no
   navegador (basescan.org) e aponte o hash, o valor e o status.
6. **(4:00)** "E o audit trail: cada decisão registrada — por que o agente
   executou, o que foi transmitido e o resultado."
   → `python verify.py` + mostre `audit/audit.jsonl` (ou rode `type audit\audit.jsonl`).
7. **(4:40)** Fechamento: "Código aberto no GitHub, transação real na chain.
   Obrigado." Fim.

---

## 📝 PASSO 6 — Submeter no DoraHacks (~10 min)

Na página do hackathon → **Submit BUIDL**:

**Link do GitHub:** `https://github.com/5600LOWIQ/meme-keeper` (já publicado ✅)

**Descrição (cole isto, traduza pro inglês já está):**

> **MEME-KEEPER** — an AI agent that watches memecoin signals (whale transfers,
> price momentum, onchain reads) and **executes real onchain transactions**
> through KeeperHub's Direct Execution API.
>
> It never broadcasts without a passing simulation (preflight), uses stable
> idempotency keys so retries never double-spend, polls execution status with
> backoff, and writes a complete audit trail (the why of every transaction,
> alongside KeeperHub's own audit trail).
>
> Proof: the agent executed a real transaction on Base — see the transaction
> link below. Everything is open source: signals, decision engine, execution
> client and safety controls.
>
> KeeperHub surfaces used: Direct Execution API (transfer / contract-call /
> check-and-execute), simulate preflight, sponsored-gas path, idempotency,
> audit trail, and a workflow builder script (`scripts/create_workflow.py`).

**Demo video:** o arquivo do PASSO 5.

**Transaction link:** `https://basescan.org/tx/0xbb4eb5828086387951813db660bfa661674c56970af3d2e1a0a31806c6885553` (executada 11/08 — status `completed`, receipt `success`, **gas patrocinado pelo KeeperHub** ✅)

**Tags:** AI Agents · Onchain · DeFi · Ethereum/Base

**Deadline:** 13/08 10:00 UTC+2 = **13/08 05:00 da manhã, horário de Brasília**
(na prática: a noite de dia 12 é o último momento seguro). **Não deixe pra
última hora** — a submissão pede vídeo + link + repo, e "incomplete
submissions cannot be judged".

---

## ⚠️ Se travar em qualquer passo
- **KeeperHub:** Discord oficial → https://discord.gg/keeperhub (canal `help`),
  engenheiros em office hours até o deadline.
- **DoraHacks:** botão "Ask Question" na página do hackathon.
- **Qualquer coisa do código:** me chama aqui.
