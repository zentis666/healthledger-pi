# Session Log — HealthLedger Pi

## Session 04 — 2026-02-21 — HTTPS + YubiKey Auth + Apple Health Importer

### Erledigte Aufgaben

#### ✅ Apple Health Importer
- `tools/apple_health_importer.py` — 422 Zeilen, 10 Messtypen
- Importiert export.zip oder export.xml (iOS 16+ DTD-Bug Fix)
- Deduplizierung: max. 3 Messungen pro Typ pro Tag
- API Endpoint `/api/import/apple-health` in main.py
- CLI: `docker exec healthledger python apple_health_importer.py /app/export.zip Sven --dry-run`

#### ✅ HTTPS mit Caddy
- Self-signed Cert (4096 bit RSA, 10 Jahre), Port 8443 → 8086
- Certs: `/etc/caddy/certs/` mit `root:caddy 640` Permissions
- Safari/Brave brauchen zwingend HTTPS für WebAuthn

#### ✅ SPA-Routing Fix
- `/` → `login.html`, `/app` → `index.html`
- Explizite Route für `/login.html` vor SPA-Fallback

#### ✅ fido2 v2.1.1 API Fix
- Installierte Version: fido2 2.1.1 (nicht 0.x wie im Code erwartet)
- Challenge manuell mit `secrets.token_bytes(32)` generieren
- base64url: `.decode().rstrip("=")` — Reihenfolge kritisch!

#### ✅ RP_ID + YubiKey Reset
- RP_ID muss Hostname sein: `pibeihilfe` statt IP
- YubiKey 5C nach PIN-Sperre über YubiKey Manager zurückgesetzt

### Offene Punkte (nächste Session)
- [ ] YubiKey 5C registrieren: Mac, Brave, `https://pibeihilfe:8443`
- [ ] Login-Flow komplett testen
- [ ] iPhone: Zertifikat vertrauen
- [ ] Apple Health export.zip importieren
- [ ] JWT_SECRET persistent in docker-compose
- [ ] fido2 Version auf 1.1.2 pinnen in requirements.txt

### Lessons Learned

**fido2 Library Versionen (WICHTIG)**
- v0.x und v2.x haben komplett verschiedene APIs
- v2.x: Kein `authenticator_selection` in `register_begin()`
- v2.x: `options.challenge` existiert nicht
- Empfehlung: `fido2==1.1.2` in requirements.txt pinnen

**WebAuthn + Safari**
- Safari: nur HTTPS, RP_ID = Hostname (keine IP)
- iCloud Keychain vs YubiKey: Safari bevorzugt immer iCloud
- Für Hardware-Zwang: Chrome oder `authenticatorAttachment: cross-platform`

**Docker Cache**
- `docker compose restart` relädt Python nicht
- Sauber: `docker compose down && docker compose up -d`

**Caddy Permissions**
- Key: `sudo chown root:caddy key.pem && chmod 640`
- Cert: `chmod 644`

### Befehle Referenz
```bash
# Auth Reset
docker exec healthledger python3 -c "
import sqlite3; db=sqlite3.connect('/app/data/healthledger.db')
db.execute('DELETE FROM auth_credentials'); db.execute('DELETE FROM auth_users')
db.commit(); print('Auth zurückgesetzt')"

# API testen
curl -sk https://pibeihilfe:8443/api/auth/status | python3 -m json.tool
curl -sk -X POST https://pibeihilfe:8443/api/auth/register/begin \
  -H "Content-Type: application/json" \
  -d '{"username":"sven","display_name":"Sven"}' | python3 -m json.tool

# Apple Health Import
docker exec healthledger python apple_health_importer.py /app/export.zip Sven --dry-run
```
