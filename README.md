# 🏥 HealthLedger Pi

> **"Democratize Health"**  
> *Gegen Platform-Zwang. Für Gesundheits-Autonomie.*

Deine Gesundheitsdaten gehören dir — nicht Google, nicht Apple, nicht deiner Krankenkasse.  
**HealthLedger Pi** ist das Ledger Nano für deine Gesundheit: Lokal. Verschlüsselt. Auditierbar.

---

## 💡 Warum?

Die großen Plattformen wollen deine Gesundheitsdaten.  
Apple Health, Google Fit, TK-App, Vivy — alle in der Cloud, alle auf fremden Servern.

**HealthLedger dreht das um:**

```
Platform-Modell          HealthLedger Pi
─────────────────────    ──────────────────────────
Daten auf Firmen-Server  Daten auf deinem Pi @ home
Vendor Lock-in           Open Source, exportierbar
Abo-Modell               Einmalig — dein Gerät
Datenschutz unklar       DSGVO by design, lokal
KI = OpenAI-Cloud        KI = Ollama, lokal, privat
Abgeschaltet 2022-2024   Läuft solange dein Pi läuft
```

---

## 🏗️ Module

```
Phase 1 — MVP (live)
├── 📁 Dokumente-Safe      Alle Arztbriefe, Befunde, Rechnungen
├── 📊 Versicherungs-Hub   PKV, Beihilfe, alle Policen
├── 💊 Medikamenten-Log    Dauermedikation, Allergien, Notfall-QR
├── 📅 Gesundheits-Timeline Laborwerte, Gewicht, Arztbesuche
└── 🚨 Notfall-Ausweis     Blutgruppe, Allergien, Medikamente

Phase 2 — Sicherheit
├── 🔐 SQLCipher AES-256
├── 🔑 Age Encryption
└── 🔄 Restic Backup

Phase 3 — Vernetzung
├── 📤 QR-Arzt-Sharing
├── 🏥 FHIR R4 Export
└── 🔗 ePA Anbindung (opt-in)
```

---

## 🛠️ Stack

```
Hardware:  Raspberry Pi 5 (8GB) + 128GB SD
Backend:   Python / FastAPI
DB:        SQLite (Phase 2: SQLCipher AES-256)
Frontend:  PWA — läuft nativ auf iOS & Android
KI:        Ollama (lokal, kein Cloud-Zwang)
Zugang:    Tailscale VPN
Audit:     Vollständiges Zugriffslog
```

---

## 🚀 Quick Deploy

```bash
mkdir -p ~/healthledger && cd ~/healthledger
curl -fsSL https://raw.githubusercontent.com/zentis666/healthledger-pi/main/scripts/deploy.sh | bash
```

---

## 📜 Lizenz

MIT — Open Source. Auditierbar. Für immer.

---

*"Democratize Health" — deine Daten, dein Pi, deine Autonomie. 🔐*
