# 📊 HealthLedger Pi — Status

**Updated:** 2026-02-20 — v1.1 YubiKey Auth  
**Phase:** 🟡 Auth in Deployment

## ✅ Live

| Was | Details |
|-----|---------|
| Backend v1.0 | Pi 192.168.178.150:8086 |
| Frontend PWA | Läuft |
| FIDO2 Auth v1.1 | ✅ Committed — Deploy ausstehend |

## 🔐 Auth-Architektur

```
Setup-Flow:
  /login.html → Name eingeben → YubiKey antippen
  → /api/auth/register/begin → Challenge
  → WebAuthn Create (Browser) → YubiKey Tap
  → /api/auth/register/finish → Credential in DB

Login-Flow:
  /login.html → YubiKey antippen
  → /api/auth/login/begin → Challenge
  → WebAuthn Get (Browser) → YubiKey Tap
  → /api/auth/login/finish → JWT (8h)
  → localStorage → alle API-Calls mit Bearer Token

Sicherheit:
  ✅ Sign-Count Replay-Schutz
  ✅ JWT HS256, 8h Gültigkeit
  ✅ Audit-Log mit Username
  ✅ Notfall-Endpunkt ohne Auth (Arzt/Rettung)
  ✅ Setup-Mode nur wenn kein Key registriert
```

## 🚀 Deploy-Befehl

```bash
cd ~/healthledger
curl -fsSL https://raw.githubusercontent.com/zentis666/healthledger-pi/main/backend/main.py -o main.py
curl -fsSL https://raw.githubusercontent.com/zentis666/healthledger-pi/main/frontend/login.html -o static/login.html
curl -fsSL https://raw.githubusercontent.com/zentis666/healthledger-pi/main/docker-compose.yml -o docker-compose.yml
docker compose up -d --force-recreate
```

## 📋 Nächste Schritte

- [ ] Deploy v1.1 auf Pi
- [ ] YubiKey (5C am Mac) registrieren
- [ ] Login testen
- [ ] JWT_SECRET persistent setzen
- [ ] Caddy HTTPS (für iOS NFC)
