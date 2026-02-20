# 📊 HealthLedger Pi — Projektstatus

**Last Updated:** 2026-02-20 (Session 02 — MVP deployed & live!)  
**Phase:** 🟢 MVP LIVE

---

## ✅ Deployment

| Was | Status | Details |
|-----|--------|---------|
| Backend (FastAPI) | ✅ LIVE | Pi 192.168.178.150:8086 |
| Frontend (PWA) | ✅ LIVE | 6 Screens, Slogan integriert |
| Datenbank (SQLite) | ✅ LIVE | 4 Personen angelegt |
| KI-Verbindung (Ollama) | ✅ LIVE | → AI-NAS 192.168.178.146 |
| NAS-Storage | ✅ LIVE | /mnt/tank/family/healthledger/ |
| GitHub Repo | ✅ PUBLIC | zentis666/healthledger-pi |

---

## 🖥️ System

```
Hardware:   Raspberry Pi 5 (pibeihilfe)
IP LAN:     192.168.178.150:8086
Tailscale:  nicht eingerichtet (TODO)
Container:  healthledger (python:3.11-slim)
Ollama:     http://192.168.178.146:11434
Modelle:    qwen2.5:32b (Chat), qwen2.5vl:7b (Vision)
Daten:      /mnt/tank/family/healthledger/data/
Uploads:    /mnt/tank/family/healthledger/uploads/
```

---

## 📱 Features MVP (live)

- ✅ **Dashboard** — Familienübersicht, letzte Dokumente
- ✅ **Upload** — PDF/Foto → KI-Extraktion (Typ, Aussteller, Betrag, Diagnose)
- ✅ **Dokumente** — Filter nach Typ, Detailansicht, Download
- ✅ **Gesundheit** — Medikamente, Messwerte, Ereignisse/Zeitachse
- ✅ **Notfall-Ausweis** — Blutgruppe, Allergien, Medikamente pro Person
- ✅ **KI-Chat** — Ollama-basiert, kennt Familiendaten

---

## 🔴 Offen / Nächste Schritte

- [ ] Tailscale auf Pi installieren (Fernzugang)
- [ ] Caddy HTTPS auf Pi (für iOS PWA nötig)
- [ ] Personen-Profile befüllen (Blutgruppe, Allergien, Hausarzt)
- [ ] Erste echte Dokumente hochladen & testen
- [ ] Phase 2: SQLCipher Verschlüsselung
- [ ] Notfall-QR Code generieren (PDF/PNG)
- [ ] Beihilfe-Modul von PiAgent integrieren

---

## 💡 Slogan

> **"Democratize Health"**  
> Gegen Platform-Zwang. Für Gesundheits-Autonomie.

---

## 🔗 Links

- **Repo:** https://github.com/zentis666/healthledger-pi
- **App:** http://192.168.178.150:8086 (LAN)
- **AI-NAS Backlog:** P2-21 in zentis666/ai-nas-project
