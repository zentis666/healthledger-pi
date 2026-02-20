# 🏥 HealthLedger Pi

> **Das Crypto-Wallet für deine Gesundheitsdaten.**  
> Lokal. Verschlüsselt. Auditierbar. DSGVO-konform by design.

---

## 💡 Konzept

Wie ein **Ledger Nano Hardware-Wallet** für Kryptowährungen — aber für deine privatesten Daten: Gesundheit.

| Krypto Ledger Nano | HealthLedger Pi |
|---|---|
| Private Keys lokal | Gesundheitsdaten lokal |
| Nur du hast Zugriff | Kein Cloud-Zwang |
| Backup via Seed Phrase | Backup auf neues Gerät |
| Selective Disclosure | Arzt-Freigabe via QR |
| Open Source | Vollständig auditierbar |

**Hardware:** Raspberry Pi 5 (8GB) + 128GB SD-Karte  
**Philosophie:** Deine Daten gehören dir. Punkt.

---

## 🏗️ Modularer Aufbau

```
Phase 1 — MVP (Core)
├── 📁 Dokumente-Safe      (Scans, OCR, KI-Extraktion)
├── 📊 Versicherungs-Hub   (PKV, Beihilfe, alle Policen)
├── 💊 Medikamenten-Log    (Dauermedikation, Allergien)
└── 📅 Gesundheits-Timeline (Laborwerte, Gewicht, Events)

Phase 2 — Sicherheit & Krypto
├── 🔐 SQLCipher AES-256   (verschlüsselte Datenbank)
├── 🔑 Age Encryption       (moderne Dokumenten-Verschlüsselung)
├── 🔒 YubiKey Support      (Hardware-Token optional)
└── 🔄 Restic Backup        (verschlüsselt auf NAS + Cloud)

Phase 3 — Vernetzung & Sharing
├── 📤 QR-Sharing           (selektive Arzt-Freigabe)
├── 🏥 FHIR R4 Export       (internationaler Medizinstandard)
├── 🔗 ePA Anbindung        (optional, DE-spezifisch)
└── 🌐 KIM Integration      (Arzt-Kommunikation DE)
```

---

## 🎯 Zielgruppe

- 🏛️ **Beamte mit Beihilfe** — komplexe Abrechnung, viele Dokumente
- 💼 **PKV-Versicherte** — aufwendige Rechnungsverwaltung
- 👨‍👩‍👧 **Familien** — Gesundheitsdaten aller Familienmitglieder zentral
- 🏥 **Chronisch Kranke** — viele Arztbesuche, viel Papier

---

## 🛠️ Tech Stack

```
Hardware:    Raspberry Pi 5 (8GB) + 128GB SD
OS:          Raspberry Pi OS Lite (headless)
Backend:     Python / FastAPI
Datenbank:   SQLite + SQLCipher (AES-256)
Verschlüs.:  age (https://age-encryption.org)
Frontend:    PWA (Progressive Web App, iOS/Android)
AI:          Ollama auf AI-NAS (lokal, kein Cloud-Zwang)
Backup:      Restic → verschlüsselt auf NAS
Zugang:      Tailscale VPN (von überall, sicher)
Audit:       Vollständiges Zugriffslog
```

---

## 📁 Repository-Struktur

```
healthledger-pi/
├── docs/               # Spezifikationen, Konzepte, Roadmap
│   ├── 01_CONCEPT.md   # Vollständiges Konzept
│   ├── 02_SPEC.md      # Technische Spezifikation
│   ├── 03_ROADMAP.md   # Entwicklungs-Roadmap
│   └── 04_STATUS.md    # Aktueller Entwicklungsstand
├── backend/            # FastAPI Backend
├── frontend/           # PWA Interface
├── crypto/             # Verschlüsselungs-Module
├── scripts/            # Setup & Deployment
└── tests/              # Tests
```

---

## 🚀 Status

**Phase:** 🟡 KONZEPT / SPEC  
**Nächster Meilenstein:** MVP Backend (Phase 1 — Core Module)  
**Basis:** Aufbau auf PiAgent (Beihilfe-Assistent) Architektur

---

## 📜 Lizenz

MIT License — Open Source, auditierbar, transparent.

---

*HealthLedger Pi — Built with privacy-first philosophy 🔐*
