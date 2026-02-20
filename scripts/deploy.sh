#!/bin/bash
# HealthLedger Pi — Deploy Script
# Läuft auf: Raspberry Pi 5 ODER aivm (zum Testen)
# Usage: bash deploy.sh [pi|aivm]

set -e
TARGET="${1:-aivm}"
echo "🏥 HealthLedger Deploy → $TARGET"

# Verzeichnis anlegen
mkdir -p ~/healthledger/static
mkdir -p ~/healthledger/data
mkdir -p ~/healthledger/uploads
cd ~/healthledger

# Dateien vom GitHub laden
BASE="https://raw.githubusercontent.com/zentis666/healthledger-pi/main"
curl -fsSL "$BASE/backend/main.py"       -o main.py
curl -fsSL "$BASE/frontend/index.html"   -o static/index.html
curl -fsSL "$BASE/docker-compose.yml"    -o docker-compose.yml

# Für Pi: Ollama auf AI-NAS
if [ "$TARGET" = "pi" ]; then
  sed -i 's|localhost:11434|192.168.178.146:11434|g' docker-compose.yml
  PORT=8080
else
  PORT=8086
fi

echo "✅ Dateien geladen"
docker compose up -d --build
echo ""
echo "🎉 HealthLedger läuft!"
echo "→ http://$(hostname -I | awk '{print $1}'):$PORT"
echo ""
echo "Logs: docker logs healthledger -f"
