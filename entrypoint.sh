#!/bin/bash
set -e

echo "🚀 Flight Monitor iniciando..."
echo "Horário atual: $(date)"

# Cria diretórios se não existirem
mkdir -p /app/data /app/logs

# Instala o crontab
crontab /app/crontab
echo "✅ Crontab instalado (06h e 18h BRT)"

# Inicializa o banco de dados
python /app/src/database.py --init
echo "✅ Banco de dados pronto"

# Verificação inicial (permite falha sem derrubar container)
if [ "${SKIP_STARTUP_CHECK:-false}" != "true" ]; then
  echo "🔍 Executando verificação inicial de preços..."
  python /app/src/flight_agent.py --startup 2>&1 | tee -a /app/logs/startup.log || \
    echo "⚠️  Verificação inicial falhou. Verifique /app/logs/startup.log"
fi

echo "⏰ Iniciando cron daemon..."
cron -f
