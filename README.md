# ✈️ Flight Monitor — Rio de Janeiro → Peru

Monitor automático de passagens com alertas por e-mail.

## Rotas Monitoradas

| Trecho | Data | Meta (2 pessoas) |
|---|---|---|
| Rio de Janeiro (GIG) → Lima (LIM) | 10/11/2026 | — |
| Lima (LIM) → Cusco (CUZ) | 15/11/2026 | ≤ R$ 700 |
| Cusco (CUZ) → Rio de Janeiro (GIG) | 20/11/2026 | — |
| **Total internacionais (GIG↔LIM)** | — | **≤ R$ 4.000** |
| **Grand total (tudo)** | — | **≤ R$ 4.700** |

## Pré-requisitos

- Docker e Docker Compose instalados
- Conta Gmail com **Senha de app** criada
  - Acesse: myaccount.google.com → Segurança → Senhas de app

## Configuração

```bash
# 1. Clone ou copie a pasta flight-monitor
# 2. Crie o arquivo .env a partir do exemplo
cp .env.example .env

# 3. Edite o .env com suas credenciais
nano .env
```

Conteúdo do `.env`:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx   # Senha de app do Gmail
ALERT_EMAIL=seu@gmail.com       # Onde receber os alertas
```

## Uso

```bash
# Subir o monitor (roda 2x por dia automaticamente)
docker compose up -d

# Acompanhar logs
docker compose logs -f

# Forçar uma verificação agora
docker compose exec flight-monitor python src/flight_agent.py

# Ver histórico de preços coletados
docker compose exec flight-monitor python src/flight_agent.py --history

# Parar
docker compose down
```

## Como funciona

```
06h e 18h (BRT)
      ↓
flight_agent.py
  ├── Skyscanner scraper   →  coleta menor preço de cada rota
  ├── Google Flights       →  coleta menor preço (rotas com scraper=both)
  ├── Salva no SQLite      →  /app/data/flights.db (persistido via volume)
  ├── price_analyzer.py    →  compara com meta e média histórica
  └── notifier.py          →  envia e-mail HTML se meta atingida
```

## Personalizar metas

Edite `config.yaml`:

```yaml
thresholds:
  international_total: 4000   # GIG→LIM + CUZ→GIG (2 pessoas)
  lima_cusco_both: 700        # LIM→CUZ (2 pessoas)
  grand_total: 4700           # tudo junto
```

## Estrutura

```
flight-monitor/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── config.yaml          ← rotas, datas, metas
├── requirements.txt
├── crontab
├── entrypoint.sh
├── data/                ← banco SQLite (criado automaticamente)
├── logs/                ← logs do cron
└── src/
    ├── flight_agent.py  ← orquestrador principal
    ├── database.py
    ├── price_analyzer.py
    ├── notifier.py
    └── scrapers/
        ├── skyscanner.py
        └── google_flights.py
```

## Notas

- O scraping do Skyscanner e Google Flights pode ocasionalmente falhar por proteções anti-bot. O monitor trata isso graciosamente e tenta novamente no próximo ciclo.
- Os preços ficam salvos em `./data/flights.db` e sobrevivem a reinicializações do container.
- O cooldown padrão é de 24h por alerta para evitar spam.
