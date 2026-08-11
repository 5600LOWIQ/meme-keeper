# SETUP — passo a passo (20-30 min)

Tudo é grátis e home office. Só o item 4 pede um valor pequeno (R$ 10-30).

---

## 1. Conta no DoraHacks (5 min)
1. Acesse https://dorahacks.io e crie conta (Google/GitHub serve).
2. Entre na página do hackathon: https://dorahacks.io/hackathon/agents-onchain/detail
3. Clique em **Join a Team** (ou crie um time só seu) e **Register**.
4. Deadline de submissão: **13/08 10:00 UTC+2** (12/08 à noite no Brasil). Não deixe pra última hora.

## 2. Conta no KeeperHub (5 min)
1. Acesse https://app.keeperhub.com e crie conta.
2. Ao entrar, a plataforma **provisiona automaticamente**:
   - uma **carteira Turnkey** (não-custodial, chaves em hardware seguro) — sua;
   - uma **cota mensal de gas patrocinado na mainnet** — primeiras transações sem fundear nada.
3. Entre no Discord deles: https://discord.gg/keeperhub (canal `general`/`help`) — os engenheiros fazem office hours até o deadline. Se travar em qualquer passo, pergunta lá.

## 3. API key (2 min)
1. No app: **Settings → API Keys → Organisation**.
2. Crie uma chave (começa com `kh_`).
3. Copie para o arquivo `.env` deste projeto:
   ```
   KH_API_KEY=kh_sua_chave_aqui
   ```

## 4. Fundear a carteira com um pouquinho de Base ETH (R$ 10-30)
O gas é patrocinado, mas o **valor movido** precisa existir. Base é a melhor
opção: gas quase zero e memecoins a rodo.
1. Copie o endereço da carteira Turnkey (app.keeperhub.com → Wallet).
2. Mande para ela um pouquinho de **Base ETH** (rede Base, não Ethereum mainnet
   nem outra). Qualquer corretora que você já use (ou a Binance/Bitget) permite
   saque direto pra rede Base. R$ 10-30 = milhares de transações possíveis.
3. Confira com `python verify.py` — ele simula uma transferência e diz se a carteira está pronta.

> Sem esse passo, o agente ainda roda em **modo observação/simulação** — você
> só não consegue a transação REAL que a submissão exige.

## 5. Configurar (5 min)
```bash
cp .env.example .env
cp config.example.json config.json
```
No `config.json`:
- `wallet.recipient` → seu endereço (0x0 = o agente envia pra ele mesmo);
- `signals.whale.token_address` → contrato do memecoin que você quer vigiar
  (ex.: um token da Base — ache o endereço no basescan.org);
- `signals.momentum.coingecko_id` → id do token no CoinGecko (ex.: `pepe`);
- `signals.min_score` → limiar de decisão (2 = precisa de sinal forte).
- `execution.amount` → valor por transação (padrão 0.0001 — bem pequeno).

Bônus (opcional): chave grátis do Basescan em https://basescan.org → API Keys,
para o whale watch funcionar de verdade.

## 6. Rodar e gerar a prova onchain
```bash
python verify.py          # diagnóstico (tudo ✅ = pronto)
python agent.py --once    # varredura única
python demo.py            # ciclo completo: sinal → simula → TRANSMITE → audit
```
No fim do `demo.py` você recebe o **`transactionLink`** (ex.:
`https://basescan.org/tx/0x...`). É ELE que vai na submissão.

## 7. Submeter (10 min)
No DoraHacks, em "Submit BUIDL":
1. **Link do GitHub** — crie um repositório com esta pasta. **NUNCA** suba o
   `.env` (adicione ao `.gitignore`). Se já tiver chave vazada, revogue e troque.
2. **Vídeo demo** — grave a tela rodando `python demo.py` (5 min). Narre o que
   cada passo faz. **Não precisa aparecer o rosto** — gravação de tela basta.
3. **Link da transação** — o `transactionLink` do passo 6.

## Dicas de julgamento (o que eles pontuam)
- **Execução** (pesa mais): transação REAL, com hash. Feito ✅
- **Surfaces do KeeperHub**: MCP/CLI/API, workflows, audit trail. Usamos a
  Direct Execution API + workflow de sweep (`scripts/create_workflow.py`). ✅
- **Reliability**: retries, gas, idempotency, audit. O agente simula antes,
  usa chave idempotente e registra tudo. ✅
- **Originalidade/utilidade real**: agente de memecoin que move valor de
  verdade, não só responde chat. ✅
- **Qualidade/DX**: código limpo, documentado, um comando pra rodar. ✅
