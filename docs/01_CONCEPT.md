# 🏥 HealthLedger Pi — Vollständiges Konzept

**Version:** 0.1 (Konzeptphase)  
**Datum:** 2026-02-20  
**Autor:** Sven Kurzberg  
**Inspiriert durch:** PiAgent (Beihilfe-Assistent) + Ledger Nano Hardware Wallet

---

## 🎯 Vision

Ein **privates Gesundheits-Ledger** auf einem Raspberry Pi — das digitale Pendant zum Ledger Nano Hardware Wallet, aber für Gesundheits- und Versicherungsdaten.

**Kernprinzipien:**
- 🏠 **Local-First:** Alle Daten bleiben auf deinem Gerät
- 🔐 **Encrypted-by-Default:** Alles verschlüsselt, auch im Ruhezustand
- 📖 **Open Source:** Vollständig auditierbar — kein "Trust me bro"
- 🇩🇪 **DSGVO-konform:** By design, kein nachträgliches Compliance-Patch
- 🤖 **KI-assistiert:** Aber lokal — keine Daten an OpenAI/Google

---

## 🔍 Marktanalyse

### Warum scheiterten bisherige Lösungen?

| Produkt | Problem | Ende |
|---------|---------|------|
| Vivy (Allianz/AXA) | Cloud-abhängig, Datenschutzbedenken | 2022 eingestellt |
| TK-Safe | Cloud, Vertrauensprobleme | 2021 eingestellt |
| HealthVault (Microsoft) | Cloud, kein Patientenkontrolle | 2019 eingestellt |
| ePA (Gematik) | Liegt bei Krankenkassen, nicht beim Patienten | Aktiv, aber umstritten |

### Das Muster: Cloud = Vertrauensverlust

**HealthLedger Pi** löst das durch radikale Dezentralisierung.  
Das Gerät ist das Produkt. Du bist der Admin.

---

## 👥 Zielgruppen & Pain Points

### 🏛️ Beamte mit Beihilfe (Primärzielgruppe)
- Beihilfesätze variieren (50-70%), komplexe Berechnung
- Papierflut: Rechnungen, Bescheide, Nachweise
- **Pain Point:** Welche Rechnung kann ich noch einreichen? Wann läuft die Frist?
- **Solution:** Automatische Beihilfe-Berechnung + Fristenverwaltung

### 💼 PKV-Versicherte
- Selbst-Verwaltung der Rechnungen (GKV macht das automatisch)
- Jahresbeitragsentwicklung, Beitragsrückerstattung
- Mehrere Tarife für Familie
- **Pain Point:** Überblick über alle Kosten, was erstattet wer?

### 👨‍👩‍👧 Familien
- Gesundheitsdaten für 2-5 Personen mit unterschiedlichen Profilen
- Kinder (Impfpass, Vorsorgeuntersuchungen, U-Hefte)
- Ältere Eltern (Pflegeleistungen, Hilfsmittel)
- **Pain Point:** Alles an einem Ort, für alle Familienmitglieder

### 🏥 Chronisch Kranke
- Viele Arztbesuche, viele Dokumente, viele Medikamente
- Wechselwirkungen zwischen Medikamenten
- Notfallausweis / Notfall-QR
- **Pain Point:** Im Notfall: Welche Medikamente nehme ich? Welche Allergien?

---

## 🏗️ Produktarchitektur

### Physisches Gerät
```
Raspberry Pi 5 (8GB)
├── 128GB SD-Karte (Haupt-Speicher)
│   ├── /data/db/          (SQLCipher Datenbank)
│   ├── /data/documents/   (verschlüsselte Dokumente)
│   └── /data/backups/     (lokale Backups)
├── USB-3 Port → Backup-Stick (Restic)
└── Tailscale VPN → Zugang von überall
```

### Software-Architektur
```
┌─────────────────────────────────────────┐
│         PWA Frontend (iOS/Android)       │
├─────────────────────────────────────────┤
│         FastAPI Backend (Python)         │
├────────────┬────────────┬───────────────┤
│  SQLCipher │  Age Enc.  │  Audit Log    │
│  (DB)      │  (Docs)    │  (Access)     │
├────────────┴────────────┴───────────────┤
│     Ollama AI (auf AI-NAS, lokal)       │
└─────────────────────────────────────────┘
```

---

## 🔐 Sicherheitskonzept

### Encryption at Rest
- **SQLCipher**: SQLite mit AES-256-CBC Verschlüsselung
  - Industrie-Standard, Open Source, auditiert
  - Passwort-deriviert via PBKDF2
- **Age Encryption**: Moderne Dokumenten-Verschlüsselung
  - Nachfolger von PGP, einfacher, sicherer
  - X25519 Elliptic Curve Cryptography
  - Jede Datei einzeln verschlüsselt

### Zugang
- **Primär**: Starkes Passwort (PBKDF2-SHA256, 600k Iterationen)
- **Optional**: YubiKey / FIDO2 Hardware Token (Phase 2)
- **Notfall**: Backup-Codes (wie Krypto Seed Phrase, offline aufbewahren)

### Audit Trail
- Jeder Datenzugriff wird geloggt (wer, was, wann)
- Logs selbst verschlüsselt
- Export möglich für externe Prüfung

### Netzwerk
- Kein direkter Internet-Eingang am Pi
- Zugang nur via **Tailscale VPN** (WireGuard-basiert)
- Lokales Netz: HTTP (intern), extern: Tailscale-verschlüsselt

---

## 💰 Vermarktungsstrategie

### Phase 1: Community / Open Source
- GitHub veröffentlichen, Community aufbauen
- Feedback von Beamten/PKV-Community einholen
- Dokumentation, Setup-Guide

### Phase 2: Hardware Bundle
- Pi 5 + SD + Gehäuse + vorinstalliert = "HealthLedger Box"
- Zielpreis: 150-200€ (Pi + Premium-SD + Setup-Service)
- Zertifiziertes Setup, kein Technik-Know-how nötig

### Phase 3: Software-as-a-Service (optional, opt-in)
- Verschlüsseltes Cloud-Backup (Nutzer hat Key, nicht wir)
- Premium: Arzt-Sharing Portal, FHIR-Export
- Subscription: 3-5€/Monat für Zusatz-Features

### Einzigartiger Wettbewerbsvorteil
- Einzige Lösung die **physisch** bei dir steht
- Einzige Lösung mit **vollständiger Offline-Funktion**
- Einzige Lösung die **KI ohne Cloud** nutzt

---

## ⚖️ Rechtliches

### DSGVO Compliance (Art. 25 — Privacy by Design)
- Datensparsamkeit: Nur was gebraucht wird
- Zweckbindung: Nur für Gesundheitsverwaltung
- **Art. 9 DSGVO**: Gesundheitsdaten = besonders schützenswert
  - Verarbeitung nur mit expliziter Einwilligung ✅
  - Lokale Verarbeitung = kein Dritter = DSGVO-konform ✅

### BSI Grundschutz
- AES-256 Verschlüsselung: BSI-empfohlen ✅
- Audit Logs: BSI-Anforderung für sensitive Daten ✅
- Open Source: Auditierbarkeit gegeben ✅

### Medizinprodukt?
- **Nein** — solange keine medizinischen Diagnosen/Empfehlungen
- Reine Verwaltungssoftware = kein MPG/MDR relevant
- Ärztliche Entscheidungen bleiben beim Arzt

---

## 🔗 Schnittstellen (Phase 3)

### FHIR R4 (Fast Healthcare Interoperability Resources)
- Internationaler Standard für Gesundheitsdaten
- Arzt-Software kann FHIR lesen
- Export als FHIR Bundle möglich

### KIM (Kommunikation im Gesundheitswesen)
- Offizieller DE-Standard für Arzt-Patient-Kommunikation
- Mittelfristig interessant für Befund-Import

### ePA (Elektronische Patientenakte)
- Opt-in Anbindung denkbar
- HealthLedger als "besseres Frontend" zur ePA

---

## 📝 Notizen

- Basis-Architektur direkt übertragbar von PiAgent (Beihilfe-Assistent)
- SQLite + FastAPI + PWA bereits bewährt im Kurzberg-Haushalt
- Ollama-Integration bereits vorhanden (AI-NAS)
- Tailscale-Zugang bereits eingerichtet
