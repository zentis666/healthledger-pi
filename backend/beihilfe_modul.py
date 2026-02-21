"""
HealthLedger — Beihilfe-Modul
Enthält:
  - GOÄ-Lookup
  - Rechnungsanalyse via KI
  - Erstattungsberechnung (BBhV Bund)
  - API-Endpoints (zum Einfügen in main.py)
"""
import json, re, os
from pathlib import Path

# ── BEIHILFESÄTZE BBhV (Bund) ────────────────────────────────────────────────
# §46 BBhV — Beihilfebemessungssätze
BEIHILFESAETZE_BUND = {
    "beamter_ledig":          0.50,
    "beamter_1_kind":         0.50,
    "beamter_2_kinder":       0.70,
    "beamter_3_kinder":       0.70,
    "versorgungsempfaenger":  0.70,
    "ehegatten":              0.70,
    "kinder":                 0.80,
    "schwerpflegebed":        0.70,
}

# ── KI-PROMPT FÜR RECHNUNGSERKENNUNG ─────────────────────────────────────────
RECHNUNG_PROMPT = """Du analysierst eine ärztliche Abrechnung (GOÄ).
Extrahiere ALLE Rechnungspositionen als JSON-Array.

Für jede Position:
{
  "ziffer": "GOÄ-Ziffer als String (z.B. '1', '3500')",
  "anzahl": Anzahl (Integer, meist 1),
  "faktor": Multiplikationsfaktor (Float, z.B. 1.0, 1.8, 2.3, 3.5),
  "betrag": Betrag in Euro (Float),
  "datum": "Datum der Leistung YYYY-MM-DD oder null",
  "beschreibung_rechnung": "Beschreibungstext aus der Rechnung"
}

Extrahiere außerdem:
{
  "arzt_name": "Name des Arztes/der Praxis",
  "arzt_fachrichtung": "Fachrichtung wenn erkennbar",
  "patient_name": "Name des Patienten",
  "rechnungsdatum": "YYYY-MM-DD",
  "rechnungsnummer": "Rechnungsnummer wenn vorhanden",
  "gesamtbetrag": Gesamtbetrag Float,
  "positionen": [... Array der Positionen ...]
}

Antworte NUR mit validem JSON, ohne Erklärungen.
Falls eine GOÄ-Ziffer nicht erkennbar ist, setze "ziffer": null.
"""

# ── ERSTATTUNGSBERECHNUNG ─────────────────────────────────────────────────────
def berechne_erstattung(positionen: list, goae_db: dict, beihilfesatz: float) -> dict:
    """
    Berechnet den beihilfefähigen Betrag und die Erstattung.
    
    BBhV §6: Beihilfefähig sind angemessene Aufwendungen.
    GOÄ-Faktor bis 2,3 gilt als angemessen (§5 Abs. 2 GOÄ).
    Faktor >2,3 nur mit schriftlicher Begründung beihilfefähig.
    """
    PUNKTWERT = 0.0582873
    MAX_FAKTOR_OHNE_BEGRUENDUNG = 2.3

    ergebnis = {
        "positionen": [],
        "gesamt_rechnung": 0.0,
        "gesamt_beihilfefaehig": 0.0,
        "erstattung": 0.0,
        "nicht_beihilfefaehig": 0.0,
        "hinweise": [],
    }

    for pos in positionen:
        ziffer = str(pos.get("ziffer", "")).strip()
        betrag = float(pos.get("betrag", 0))
        faktor = float(pos.get("faktor", 1.0))
        anzahl = int(pos.get("anzahl", 1))

        ergebnis["gesamt_rechnung"] += betrag

        if not ziffer or ziffer == "null":
            ergebnis["positionen"].append({**pos,
                "beihilfefaehig": False,
                "beihilfefaehiger_betrag": 0.0,
                "hinweis": "GOÄ-Ziffer nicht erkannt"})
            ergebnis["nicht_beihilfefaehig"] += betrag
            continue

        goae_pos = goae_db.get(ziffer)

        if not goae_pos:
            ergebnis["positionen"].append({**pos,
                "beihilfefaehig": False,
                "beihilfefaehiger_betrag": 0.0,
                "hinweis": f"GOÄ {ziffer} nicht in Datenbank — bitte manuell prüfen"})
            ergebnis["hinweise"].append(f"GOÄ {ziffer} unbekannt — manuelle Prüfung empfohlen")
            ergebnis["nicht_beihilfefaehig"] += betrag
            continue

        if not goae_pos["beihilfefaehig_bund"]:
            ergebnis["positionen"].append({**pos,
                "beschreibung_goae": goae_pos["beschreibung"],
                "beihilfefaehig": False,
                "beihilfefaehiger_betrag": 0.0,
                "hinweis": "IGeL-Leistung — nicht beihilfefähig"})
            ergebnis["nicht_beihilfefaehig"] += betrag
            continue

        # Angemessener Betrag: max Faktor 2,3 ohne Begründung
        einfachsatz = goae_pos["einfachsatz"]
        angemessener_betrag = round(einfachsatz * min(faktor, MAX_FAKTOR_OHNE_BEGRUENDUNG) * anzahl, 2)
        beihilfefaehiger_betrag = min(betrag, angemessener_betrag)

        hinweis = None
        if faktor > MAX_FAKTOR_OHNE_BEGRUENDUNG:
            hinweis = f"Faktor {faktor} > 2,3: Nur {angemessener_betrag:.2f}€ beihilfefähig (Differenz {betrag-angemessener_betrag:.2f}€ selbst tragen)"
            ergebnis["hinweise"].append(f"GOÄ {ziffer}: {hinweis}")

        ergebnis["gesamt_beihilfefaehig"] += beihilfefaehiger_betrag
        ergebnis["positionen"].append({**pos,
            "beschreibung_goae": goae_pos["beschreibung"],
            "kategorie": goae_pos["kategorie"],
            "einfachsatz": einfachsatz,
            "beihilfefaehig": True,
            "beihilfefaehiger_betrag": round(beihilfefaehiger_betrag, 2),
            "hinweis": hinweis})

    ergebnis["gesamt_beihilfefaehig"] = round(ergebnis["gesamt_beihilfefaehig"], 2)
    ergebnis["erstattung"] = round(ergebnis["gesamt_beihilfefaehig"] * beihilfesatz, 2)
    ergebnis["nicht_beihilfefaehig"] = round(ergebnis["nicht_beihilfefaehig"], 2)
    ergebnis["beihilfesatz_prozent"] = int(beihilfesatz * 100)
    ergebnis["eigenanteil"] = round(ergebnis["gesamt_rechnung"] - ergebnis["erstattung"], 2)

    return ergebnis


# ── TEST ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    with open("/home/claude/goae_datenbank.json") as f:
        goae_db = json.load(f)

    # Beispiel-Rechnung (Hausarzt)
    test_rechnung = [
        {"ziffer": "3",   "anzahl": 1, "faktor": 2.3, "betrag": 20.24, "datum": "2026-02-10"},
        {"ziffer": "250", "anzahl": 1, "faktor": 1.8, "betrag": 5.23,  "datum": "2026-02-10"},
        {"ziffer": "3501","anzahl": 1, "faktor": 1.0, "betrag": 2.91,  "datum": "2026-02-10"},
        {"ziffer": "3516","anzahl": 1, "faktor": 1.0, "betrag": 3.50,  "datum": "2026-02-10"},
        {"ziffer": "3561","anzahl": 1, "faktor": 1.0, "betrag": 15.15, "datum": "2026-02-10"},
        {"ziffer": "3573","anzahl": 1, "faktor": 1.0, "betrag": 16.91, "datum": "2026-02-10"},
        {"ziffer": "70",  "anzahl": 1, "faktor": 2.3, "betrag": 20.24, "datum": "2026-02-10"},  # IGeL
    ]

    result = berechne_erstattung(test_rechnung, goae_db, beihilfesatz=0.70)

    print("═" * 60)
    print("BEIHILFE-BERECHNUNG — Testrechnung Hausarzt")
    print("═" * 60)
    for pos in result["positionen"]:
        status = "✅" if pos["beihilfefaehig"] else "❌"
        print(f"  {status} GOÄ {pos.get('ziffer','?'):6s} {pos.get('beschreibung_goae', pos.get('beschreibung_rechnung',''))[:35]:35s} {pos['betrag']:6.2f}€  →  {pos.get('beihilfefaehiger_betrag',0):6.2f}€")
        if pos.get("hinweis"):
            print(f"     ⚠️  {pos['hinweis']}")
    print("─" * 60)
    print(f"  Gesamtrechnung:          {result['gesamt_rechnung']:8.2f} €")
    print(f"  Beihilfefähig:           {result['gesamt_beihilfefaehig']:8.2f} €")
    print(f"  Erstattung ({result['beihilfesatz_prozent']}%):        {result['erstattung']:8.2f} €")
    print(f"  Eigenanteil:             {result['eigenanteil']:8.2f} €")
    print(f"  Nicht beihilfefähig:     {result['nicht_beihilfefaehig']:8.2f} €")
    if result["hinweise"]:
        print("\n  HINWEISE:")
        for h in result["hinweise"]:
            print(f"  ⚠️  {h}")
    print("═" * 60)
