"""
Neue Endpoints für main.py — Beihilfe-Modul
Zum Einfügen nach den bestehenden Routen.
"""

BEIHILFE_ENDPOINTS = '''
# ═══════════════════════════════════════════════════════════════
# BEIHILFE-MODUL
# ═══════════════════════════════════════════════════════════════

import json as _json
from pathlib import Path as _Path

def _lade_goae_db():
    """Lädt GOÄ-Datenbank (wird gecacht nach erstem Laden)"""
    if not hasattr(_lade_goae_db, "_cache"):
        db_path = _Path(__file__).parent / "goae_datenbank.json"
        if db_path.exists():
            with open(db_path, encoding="utf-8") as f:
                _lade_goae_db._cache = _json.load(f)
        else:
            _lade_goae_db._cache = {}
    return _lade_goae_db._cache

def _berechne_erstattung(positionen: list, goae_db: dict, beihilfesatz: float) -> dict:
    MAX_FAKTOR = 2.3
    res = {"positionen": [], "gesamt_rechnung": 0.0,
           "gesamt_beihilfefaehig": 0.0, "erstattung": 0.0,
           "nicht_beihilfefaehig": 0.0, "hinweise": []}
    for pos in positionen:
        ziffer  = str(pos.get("ziffer", "")).strip()
        betrag  = float(pos.get("betrag", 0))
        faktor  = float(pos.get("faktor", 1.0))
        anzahl  = int(pos.get("anzahl", 1))
        res["gesamt_rechnung"] += betrag
        goae = goae_db.get(ziffer) if ziffer and ziffer != "null" else None
        if not goae:
            res["positionen"].append({**pos, "beihilfefaehig": False,
                "beihilfefaehiger_betrag": 0.0,
                "hinweis": "Ziffer unbekannt — bitte manuell prüfen" if ziffer else "Ziffer nicht erkannt"})
            res["nicht_beihilfefaehig"] += betrag
            continue
        if not goae["beihilfefaehig_bund"]:
            res["positionen"].append({**pos, "beschreibung_goae": goae["beschreibung"],
                "beihilfefaehig": False, "beihilfefaehiger_betrag": 0.0,
                "hinweis": "IGeL / nicht beihilfefähig"})
            res["nicht_beihilfefaehig"] += betrag
            continue
        angemessen = round(goae["einfachsatz"] * min(faktor, MAX_FAKTOR) * anzahl, 2)
        bh_betrag  = min(betrag, angemessen)
        hinweis    = None
        if faktor > MAX_FAKTOR:
            hinweis = f"Faktor {faktor} > 2,3: nur {angemessen:.2f}€ beihilfefähig"
            res["hinweise"].append(f"GOÄ {ziffer}: {hinweis}")
        res["gesamt_beihilfefaehig"] += bh_betrag
        res["positionen"].append({**pos, "beschreibung_goae": goae["beschreibung"],
            "kategorie": goae["kategorie"], "beihilfefaehig": True,
            "beihilfefaehiger_betrag": round(bh_betrag, 2), "hinweis": hinweis})
    res["gesamt_beihilfefaehig"] = round(res["gesamt_beihilfefaehig"], 2)
    res["erstattung"]            = round(res["gesamt_beihilfefaehig"] * beihilfesatz, 2)
    res["nicht_beihilfefaehig"] = round(res["nicht_beihilfefaehig"], 2)
    res["beihilfesatz_prozent"]  = int(beihilfesatz * 100)
    res["eigenanteil"]           = round(res["gesamt_rechnung"] - res["erstattung"], 2)
    return res

# ── GOÄ Suche ────────────────────────────────────────────────────────────────
@app.get("/api/beihilfe/goae/suche")
async def goae_suche(q: str = "", user: dict = Depends(get_current_user)):
    """Suche in der GOÄ-Datenbank"""
    goae_db = _lade_goae_db()
    q = q.lower().strip()
    if not q:
        return {"ziffern": list(goae_db.values())[:20]}
    treffer = [v for v in goae_db.values()
               if q in v["ziffer"] or q in v["beschreibung"].lower()
               or q in v["kategorie"].lower()]
    return {"ziffern": treffer[:30]}

@app.get("/api/beihilfe/goae/{ziffer}")
async def goae_details(ziffer: str, user: dict = Depends(get_current_user)):
    """Details zu einer GOÄ-Ziffer"""
    goae_db = _lade_goae_db()
    pos = goae_db.get(ziffer)
    if not pos:
        raise HTTPException(404, f"GOÄ-Ziffer {ziffer} nicht gefunden")
    return pos

# ── Rechnung analysieren ──────────────────────────────────────────────────────
@app.post("/api/beihilfe/rechnung/analysieren")
async def rechnung_analysieren(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Analysiert eine Rechnung via KI und berechnet Beihilfe.
    Erwartet: { "dokument_id": int, "person": str }
    Oder:     { "freitext": str, "person": str }
    """
    data = await request.json()
    person   = data.get("person", "")
    goae_db  = _lade_goae_db()

    # Person und Beihilfesatz ermitteln
    with get_db() as db:
        row = db.execute(
            "SELECT beihilfesatz FROM personen WHERE name=?", (person,)
        ).fetchone()
        beihilfesatz = float(row["beihilfesatz"]) if row else 0.50

    # KI-Extraktion
    ki_text = data.get("freitext", "")
    if data.get("dokument_id"):
        with get_db() as db:
            dok = db.execute(
                "SELECT ki_extraktion, beschreibung FROM dokumente WHERE id=?",
                (data["dokument_id"],)
            ).fetchone()
        if dok:
            ki_text = dok["ki_extraktion"] or dok["beschreibung"] or ""

    # Ollama aufrufen für GOÄ-Extraktion
    prompt = f"""Analysiere diese ärztliche Abrechnung und extrahiere alle GOÄ-Positionen.

RECHNUNG:
{ki_text}

Antworte NUR mit diesem JSON (keine Erklärungen):
{{
  "arzt_name": "...",
  "rechnungsdatum": "YYYY-MM-DD oder null",
  "rechnungsnummer": "... oder null",
  "gesamtbetrag": 0.00,
  "positionen": [
    {{
      "ziffer": "GOÄ-Ziffer",
      "anzahl": 1,
      "faktor": 2.3,
      "betrag": 0.00,
      "datum": "YYYY-MM-DD oder null",
      "beschreibung_rechnung": "Text aus Rechnung"
    }}
  ]
}}"""

    ki_result = {}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:7b", "prompt": prompt,
                      "stream": False, "format": "json"}
            )
        ki_result = resp.json().get("response", "{}")
        if isinstance(ki_result, str):
            ki_result = _json.loads(ki_result)
    except Exception as e:
        ki_result = {"fehler": str(e), "positionen": []}

    positionen = ki_result.get("positionen", [])

    # Beihilfe berechnen
    berechnung = _berechne_erstattung(positionen, goae_db, beihilfesatz)
    berechnung["ki_extraktion"] = ki_result
    berechnung["person"]        = person
    berechnung["beihilfesatz"]  = beihilfesatz

    return berechnung

# ── Beihilfe-Anträge verwalten ────────────────────────────────────────────────
@app.get("/api/beihilfe/antraege")
async def beihilfe_antraege(
    person: str = "",
    user: dict = Depends(get_current_user)
):
    """Alle Beihilfe-relevanten Dokumente mit Status"""
    with get_db() as db:
        query = """
            SELECT d.id, d.person, d.titel, d.aussteller, d.datum,
                   d.betrag, d.eingereicht_beihilfe, d.ki_extraktion,
                   d.erstellt_am
            FROM dokumente d
            WHERE d.typ IN ('rechnung', 'arztrechnung', 'Rechnung')
        """
        params = []
        if person:
            query += " AND d.person = ?"
            params.append(person)
        query += " ORDER BY d.datum DESC"
        rows = db.execute(query, params).fetchall()

    antraege = []
    for r in rows:
        ki = {}
        try:
            ki = _json.loads(r["ki_extraktion"] or "{}")
        except Exception:
            pass
        antraege.append({
            "id":                  r["id"],
            "person":              r["person"],
            "titel":               r["titel"],
            "aussteller":          r["aussteller"],
            "datum":               r["datum"],
            "betrag":              r["betrag"],
            "eingereicht":         bool(r["eingereicht_beihilfe"]),
            "erstattung_erwartet": ki.get("erstattung"),
            "erstellt_am":         r["erstellt_am"],
        })

    offen     = [a for a in antraege if not a["eingereicht"]]
    eingereicht = [a for a in antraege if a["eingereicht"]]

    return {
        "antraege": antraege,
        "offen":    len(offen),
        "eingereicht": len(eingereicht),
        "summe_offen": round(sum(a["betrag"] or 0 for a in offen), 2),
    }

@app.post("/api/beihilfe/antraege/{dok_id}/eingereicht")
async def beihilfe_eingereicht(
    dok_id: int,
    user: dict = Depends(get_current_user)
):
    """Rechnung als 'eingereicht bei Beihilfe' markieren"""
    with get_db() as db:
        db.execute(
            "UPDATE dokumente SET eingereicht_beihilfe=1 WHERE id=?",
            (dok_id,)
        )
        db.commit()
    return {"ok": True, "dok_id": dok_id}
'''

print("✅ Beihilfe-Endpoints bereit")
print(f"   {BEIHILFE_ENDPOINTS.count('async def') + BEIHILFE_ENDPOINTS.count('def ')} Funktionen/Endpoints")
