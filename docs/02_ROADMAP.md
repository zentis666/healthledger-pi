# 🗺️ HealthLedger Pi — Entwicklungs-Roadmap

**Stand:** 2026-02-20  

---

## 🟢 Phase 0 — Konzept (AKTUELL)

- [x] Konzept ausarbeiten
- [x] GitHub Repository erstellen
- [x] Dokumentation starten
- [ ] Marktrecherche vertiefen
- [ ] Technische Spec finalisieren

---

## 🟡 Phase 1 — MVP Core (Nächster Schritt)

**Ziel:** Funktionierendes System für Familien-Eigennutz

### Modul 1.1: Dokumente-Safe
- [ ] Dokument-Upload (PDF, JPG, PNG)
- [ ] OCR-Extraktion (Tesseract)
- [ ] KI-Metadaten-Extraktion via Ollama
- [ ] Suche & Filterung
- [ ] Tags: Person, Datum, Arzt, Typ

### Modul 1.2: Versicherungs-Hub
- [ ] Personen-Verwaltung (Familie)
- [ ] PKV-Profile (Tarif, Beitrag, Leistungen)
- [ ] Beihilfe-Tracking (aus PiAgent übernehmen!)
- [ ] Policen-Verwaltung (Upload + Metadaten)
- [ ] Ablauffristen-Kalender

### Modul 1.3: Medikamenten-Log
- [ ] Dauermedikation erfassen
- [ ] Allergien & Unverträglichkeiten
- [ ] Notfall-QR Code generieren
- [ ] KI-Wechselwirkungscheck (lokal)

### Modul 1.4: Gesundheits-Timeline
- [ ] Manuelle Einträge (Arztbesuche, Diagnosen)
- [ ] Laborwerte (Import + Visualisierung)
- [ ] Gewicht, Blutdruck, Herzfrequenz
- [ ] Chronologische Ansicht

---

## 🔵 Phase 2 — Sicherheit & Krypto

- [ ] SQLCipher Integration (AES-256)
- [ ] Age Encryption für Dokumente
- [ ] YubiKey / FIDO2 Support
- [ ] Backup-System (Restic → NAS)
- [ ] Audit Log
- [ ] Passwort-Reset via Backup-Codes

---

## 🟣 Phase 3 — Vernetzung

- [ ] QR-Code Arzt-Sharing (selektiv)
- [ ] FHIR R4 Export
- [ ] Multi-Device Sync (verschlüsselt)
- [ ] ePA Anbindung (opt-in)
- [ ] API für externe Dienste

---

## 💡 Phase 4 — Produkt

- [ ] Hardware Bundle (Pi + SD vorinstalliert)
- [ ] Setup-Wizard (kein Tech-Know-how nötig)
- [ ] Dokumentation für Endnutzer
- [ ] Community aufbauen

---

## 🔄 Abhängigkeiten & Synergien

- **PiAgent (Beihilfe)**: Modul 1.2 direkt übertragbar
- **AI-NAS**: Ollama-Anbindung bereits vorhanden
- **Tailscale**: Sicherer Fernzugang bereits eingerichtet
- **Calibre-Web**: Dokumenten-Handling Patterns übertragbar
