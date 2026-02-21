# Beihilfe-Modul — Implementierungsstand

## Status: Beta-Ready 🟡

## Dateien

| Datei | Inhalt |
|-------|--------|
| `goae_datenbank.json` | 82 GOÄ-Ziffern, beihilfefähig ja/nein, alle Faktoren |
| `beihilfe_modul.py` | Berechnungslogik + KI-Prompt |
| `beihilfe_endpoints.py` | FastAPI Endpoints (in main.py einfügen) |
| `../frontend/beihilfe_modul.html` | UI-Komponente (in index.html einfügen) |

## Integration in main.py

```python
# Am Ende von main.py einfügen:
exec(open("beihilfe_endpoints.py").read())
```

Oder Endpoints manuell einkopieren (empfohlen).

## Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/beihilfe/goae/suche?q=` | GET | GOÄ-Datenbank durchsuchen |
| `/api/beihilfe/goae/{ziffer}` | GET | Details zu einer Ziffer |
| `/api/beihilfe/rechnung/analysieren` | POST | KI-Analyse + Berechnung |
| `/api/beihilfe/antraege` | GET | Offene/eingereichte Anträge |
| `/api/beihilfe/antraege/{id}/eingereicht` | POST | Als eingereicht markieren |

## GOÄ-Datenbank

- 82 häufigste Ziffern (~90% aller Arztabrechnungen)
- Vollständige Steigerungsfaktoren: 1,0 / 1,8 / 2,3 / 3,5
- Beihilfefähigkeit nach BBhV (Bund)
- Kategorien: Grundleistung, Labor, Labor M, Bildgebung, Funktionsdiagnostik, IGeL

## BBhV Beihilfesätze (Bund)

| Situation | Satz |
|-----------|------|
| Beamter ledig / 1 Kind | 50% |
| Beamter ≥ 2 Kinder | 70% |
| Versorgungsempfänger | 70% |
| Ehegatte | 70% |
| Kinder | 80% |

## Nächste Schritte (Beta → Release)

- [ ] PDF-Antrag automatisch befüllen (Bundesformular)
- [ ] Fristenüberwachung (1-Jahres-Frist)
- [ ] Mehr GOÄ-Ziffern (vollständig ~2800)
- [ ] PKV-Workflow
- [ ] OCR für eingescannte Rechnungen (Basis-Modell)
- [ ] Bundesländer: Bayern, BW, NRW...
