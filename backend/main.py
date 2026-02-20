"""HealthLedger Pi — Privates Gesundheits-Ledger v1.0
Lokal. Verschlüsselt. Auditierbar.
Aufbauend auf PiAgent-Architektur (FastAPI + SQLite + PWA)
"""
import os, json, sqlite3, base64, asyncio, hashlib, re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

BASE_DIR    = Path(__file__).parent
UPLOAD_DIR  = BASE_DIR / "uploads"
STATIC_DIR  = BASE_DIR / "static"
DATA_DIR    = BASE_DIR / "data"
DB_PATH     = DATA_DIR / "healthledger.db"
OLLAMA_URL  = os.getenv("OLLAMA_URL",   "http://localhost:11434")
VISION_MODEL= os.getenv("VISION_MODEL", "qwen2.5vl:7b")
CHAT_MODEL  = os.getenv("CHAT_MODEL",   "qwen2.5:32b")
APP_VERSION = "1.0.0"

for d in (UPLOAD_DIR, STATIC_DIR, DATA_DIR):
    d.mkdir(exist_ok=True, parents=True)

app = FastAPI(title="HealthLedger")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════════════════
# DATENBANK
# ═══════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        -- Familienmitglieder
        CREATE TABLE IF NOT EXISTS personen (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            geburtsdatum TEXT,
            blutgruppe  TEXT,
            allergien   TEXT,          -- JSON Array
            notfallkontakt TEXT,
            arzt_hausarzt  TEXT,
            versicherung_name TEXT,
            versicherung_nr   TEXT,
            beihilfesatz  REAL DEFAULT 0.0,
            aktiv         INTEGER DEFAULT 1,
            erstellt_am   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Alle Gesundheits-Dokumente (Arztbriefe, Befunde, Rechnungen, Rezepte...)
        CREATE TABLE IF NOT EXISTS dokumente (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id       INTEGER REFERENCES personen(id),
            person          TEXT,
            typ             TEXT,  -- rechnung|arztbrief|befund|rezept|impfung|sonstiges
            titel           TEXT,
            aussteller      TEXT,
            datum           TEXT,
            betrag          REAL,
            diagnose        TEXT,
            beschreibung    TEXT,
            tags            TEXT,  -- JSON Array
            file_path       TEXT,
            eingereicht_beihilfe INTEGER DEFAULT 0,
            eingereicht_pkv      INTEGER DEFAULT 0,
            ki_extraktion   TEXT,  -- JSON: KI-extrahierte Daten
            erstellt_am     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Medikamenten-Log
        CREATE TABLE IF NOT EXISTS medikamente (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id   INTEGER REFERENCES personen(id),
            person      TEXT,
            name        TEXT NOT NULL,
            wirkstoff   TEXT,
            dosierung   TEXT,
            haeufigkeit TEXT,    -- täglich|wöchentlich|bei Bedarf
            seit        TEXT,    -- Datum
            bis         TEXT,    -- leer = Dauermedikation
            typ         TEXT,    -- dauermedikation|bedarfsmedikation|impfung
            notiz       TEXT,
            aktiv       INTEGER DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Gesundheits-Messwerte (Gewicht, Blutdruck, Laborwerte...)
        CREATE TABLE IF NOT EXISTS messwerte (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id   INTEGER REFERENCES personen(id),
            person      TEXT,
            typ         TEXT,    -- gewicht|blutdruck|blutzucker|laborwert|temperatur|puls
            wert        REAL,
            wert2       REAL,    -- für Blutdruck: diastolisch
            einheit     TEXT,    -- kg|mmHg|mg/dl|°C|bpm
            datum       TEXT,
            notiz       TEXT,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Arztbesuche & Ereignisse (Zeitachse)
        CREATE TABLE IF NOT EXISTS ereignisse (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id   INTEGER REFERENCES personen(id),
            person      TEXT,
            typ         TEXT,    -- arztbesuch|krankenhausaufenthalt|operation|impfung|diagnose
            titel       TEXT,
            datum       TEXT,
            arzt        TEXT,
            einrichtung TEXT,
            notizen     TEXT,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Versicherungspolicen
        CREATE TABLE IF NOT EXISTS policen (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id       INTEGER REFERENCES personen(id),
            person          TEXT,
            versicherung    TEXT,
            art             TEXT,    -- pkv|zusatz|lebens|unfall|pflege
            tarif           TEXT,
            versicherungs_nr TEXT,
            beitrag_monat   REAL,
            beginn          TEXT,
            ablauf          TEXT,
            selbstbehalt    REAL DEFAULT 0,
            file_path       TEXT,
            notiz           TEXT,
            aktiv           INTEGER DEFAULT 1,
            erstellt_am     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Audit Log: jeder Datenzugriff wird protokolliert
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            aktion      TEXT,    -- CREATE|READ|UPDATE|DELETE
            tabelle     TEXT,
            datensatz_id INTEGER,
            details     TEXT,
            ip          TEXT,
            zeitstempel TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
        """)

        # Default-Familie einrichten (aus PiAgent bekannt)
        db.executescript("""
        INSERT OR IGNORE INTO personen (name, versicherung_name, beihilfesatz)
        VALUES
            ('Sven',    'DKV', 0.70),
            ('Heidi',   'DKV', 0.50),
            ('Julian',  'DKV', 0.80),
            ('Theresa', 'DKV', 0.80);
        INSERT OR IGNORE INTO config VALUES ('version', '1.0.0');
        INSERT OR IGNORE INTO config VALUES ('familie', 'Kurzberg');
        """)
        db.commit()

def audit(aktion: str, tabelle: str, datensatz_id: int = None, details: str = "", ip: str = ""):
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO audit_log (aktion,tabelle,datensatz_id,details,ip) VALUES (?,?,?,?,?)",
                (aktion, tabelle, datensatz_id, details, ip)
            )
            db.commit()
    except:
        pass

init_db()

# ═══════════════════════════════════════════════════════════
# KI-EXTRAKTION
# ═══════════════════════════════════════════════════════════

def pdf_to_text(filepath: Path) -> str:
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(str(filepath)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
        return "\n".join(text)[:4000]
    except Exception as e:
        return f"[PDF-Fehler: {e}]"

async def analyse_dokument(filepath: Path, mime_type: str) -> dict:
    import urllib.request

    is_pdf = filepath.suffix.lower() == ".pdf"

    if is_pdf:
        pdf_text = pdf_to_text(filepath)
        has_text = len(pdf_text.strip()) > 50 and "[PDF-Fehler" not in pdf_text

        if has_text:
            prompt = f"""Analysiere dieses medizinische Dokument und extrahiere als JSON (NUR JSON, kein Text davor/danach):
{{"typ":"rechnung|arztbrief|befund|rezept|impfung|sonstiges",
"aussteller":"Name der Praxis/Klinik/Apotheke",
"patient":"Patientenname",
"datum":"YYYY-MM-DD",
"betrag":0.00,
"diagnose":"ICD-Code oder Beschreibung wenn vorhanden",
"beschreibung":"kurze Zusammenfassung des Inhalts",
"tags":["tag1","tag2"],
"konfidenz":"hoch|mittel|niedrig"}}
Fehlende Werte: null. Betrag nur bei Rechnungen, sonst null.

Dokumenttext:
{pdf_text}"""
            payload = json.dumps({
                "model": CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }).encode()
            endpoint = f"{OLLAMA_URL}/api/chat"
            def parse_resp(result):
                return result.get("message", {}).get("content", "{}")
        else:
            try:
                from pdf2image import convert_from_path
                imgs = convert_from_path(str(filepath), dpi=200, first_page=1, last_page=1)
                if imgs:
                    import io
                    buf = io.BytesIO()
                    imgs[0].save(buf, format="JPEG", quality=85)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                else:
                    return {"fehler": "PDF-Konvertierung fehlgeschlagen", "konfidenz": "niedrig"}
            except Exception as e:
                return {"fehler": f"PDF-Fehler: {e}", "konfidenz": "niedrig"}

            prompt = """Analysiere dieses medizinische Dokument als JSON (NUR JSON):
{"typ":"rechnung|arztbrief|befund|rezept|impfung|sonstiges",
"aussteller":"Name","patient":"Name","datum":"YYYY-MM-DD",
"betrag":0.00,"diagnose":"","beschreibung":"Kurze Zusammenfassung",
"tags":[],"konfidenz":"hoch|mittel|niedrig"}"""
            payload = json.dumps({
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [b64],
                "stream": False
            }).encode()
            endpoint = f"{OLLAMA_URL}/api/generate"
            def parse_resp(result):
                return result.get("response", "{}")
    else:
        async with aiofiles.open(filepath, "rb") as f:
            raw = await f.read()
        b64 = base64.b64encode(raw).decode()
        prompt = """Analysiere dieses medizinische Dokument als JSON (NUR JSON):
{"typ":"rechnung|arztbrief|befund|rezept|impfung|sonstiges",
"aussteller":"Name","patient":"Name","datum":"YYYY-MM-DD",
"betrag":0.00,"diagnose":"","beschreibung":"Kurze Zusammenfassung",
"tags":[],"konfidenz":"hoch|mittel|niedrig"}"""
        payload = json.dumps({
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [b64],
            "stream": False
        }).encode()
        endpoint = f"{OLLAMA_URL}/api/generate"
        def parse_resp(result):
            return result.get("response", "{}")

    try:
        req = urllib.request.Request(
            endpoint, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        loop = asyncio.get_event_loop()
        def do_req():
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read())
            except Exception as e:
                return {"error": str(e)}
        result = await loop.run_in_executor(None, do_req)
        if "error" in result:
            return {"fehler": result["error"], "konfidenz": "niedrig"}
        raw_resp = parse_resp(result).strip()
        try:
            return json.loads(raw_resp)
        except:
            m = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            return json.loads(m.group()) if m else {"fehler": "Parse-Fehler", "konfidenz": "niedrig"}
    except Exception as e:
        return {"fehler": str(e), "konfidenz": "niedrig"}

# ═══════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/status")
async def status():
    with get_db() as db:
        dok_count = db.execute("SELECT COUNT(*) as n FROM dokumente").fetchone()["n"]
        med_count = db.execute("SELECT COUNT(*) as n FROM medikamente WHERE aktiv=1").fetchone()["n"]
        per_count = db.execute("SELECT COUNT(*) as n FROM personen WHERE aktiv=1").fetchone()["n"]
    return {
        "status": "ok",
        "version": APP_VERSION,
        "personen": per_count,
        "dokumente": dok_count,
        "medikamente": med_count
    }

# ── PERSONEN ──────────────────────────────────────────────

@app.get("/api/personen")
async def get_personen():
    with get_db() as db:
        rows = db.execute("SELECT * FROM personen WHERE aktiv=1 ORDER BY name").fetchall()
        return [dict(r) for r in rows]

@app.get("/api/personen/{person_id}")
async def get_person(person_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM personen WHERE id=?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        p = dict(row)
        # Statistiken
        p["dok_count"] = db.execute("SELECT COUNT(*) as n FROM dokumente WHERE person_id=?", (person_id,)).fetchone()["n"]
        p["med_count"] = db.execute("SELECT COUNT(*) as n FROM medikamente WHERE person_id=? AND aktiv=1", (person_id,)).fetchone()["n"]
        return p

@app.put("/api/personen/{person_id}")
async def update_person(person_id: int, request: Request):
    body = await request.json()
    allowed = ["name","geburtsdatum","blutgruppe","allergien","notfallkontakt",
               "arzt_hausarzt","versicherung_name","versicherung_nr","beihilfesatz"]
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "Keine gültigen Felder")
    with get_db() as db:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE personen SET {set_clause} WHERE id=?",
                   list(updates.values()) + [person_id])
        db.commit()
    audit("UPDATE", "personen", person_id, json.dumps(updates))
    return {"erfolg": True}

# ── DOKUMENTE ─────────────────────────────────────────────

@app.get("/api/dokumente")
async def get_dokumente(
    person: Optional[str] = None,
    typ: Optional[str] = None,
    limit: int = 50
):
    with get_db() as db:
        q = "SELECT * FROM dokumente WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if typ:    q += " AND typ=?"; params.append(typ)
        q += f" ORDER BY datum DESC, erstellt_am DESC LIMIT {limit}"
        rows = db.execute(q, params).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/upload")
async def upload_dokument(
    file: UploadFile = File(...),
    person: str = Form(default=""),
    typ: str = Form(default="auto"),
    request: Request = None
):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if suffix not in [".jpg", ".jpeg", ".png", ".pdf", ".heic", ".webp"]:
        suffix = ".jpg"
    filename = f"{ts}_{person or 'unknown'}{suffix}"
    filepath = UPLOAD_DIR / filename

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    # KI-Extraktion
    extracted = await analyse_dokument(filepath, file.content_type or "image/jpeg")

    # Person bestimmen
    if not person and extracted.get("patient"):
        person = extracted.get("patient", "")

    # Lookup person_id
    person_id = None
    with get_db() as db:
        if person:
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (person,)).fetchone()
            if not row:
                first = person.split()[0] if person else ""
                row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (first + "%",)).fetchone()
            if row:
                person_id = row["id"]

    # Dokument speichern
    with get_db() as db:
        dok_id = db.execute("""
            INSERT INTO dokumente
            (person_id, person, typ, aussteller, datum, betrag, diagnose, beschreibung, tags, file_path, ki_extraktion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            person_id,
            person or extracted.get("patient", "Unbekannt"),
            extracted.get("typ", typ) if typ == "auto" else typ,
            extracted.get("aussteller", ""),
            extracted.get("datum", ""),
            extracted.get("betrag"),
            extracted.get("diagnose", ""),
            extracted.get("beschreibung", ""),
            json.dumps(extracted.get("tags", [])),
            str(filepath),
            json.dumps(extracted)
        )).lastrowid
        db.commit()

    ip = request.client.host if request else ""
    audit("CREATE", "dokumente", dok_id, f"Upload: {file.filename}", ip)

    return {
        "erfolg": True,
        "dokument_id": dok_id,
        "extrahiert": extracted,
        "datei": filename
    }

@app.delete("/api/dokumente/{dok_id}")
async def delete_dokument(dok_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM dokumente WHERE id=?", (dok_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        fp = Path(row["file_path"])
        if fp.exists():
            fp.unlink()
        db.execute("DELETE FROM dokumente WHERE id=?", (dok_id,))
        db.commit()
    audit("DELETE", "dokumente", dok_id)
    return {"erfolg": True}

# ── MEDIKAMENTE ───────────────────────────────────────────

@app.get("/api/medikamente")
async def get_medikamente(person: Optional[str] = None, aktiv_only: bool = True):
    with get_db() as db:
        q = "SELECT * FROM medikamente WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if aktiv_only: q += " AND aktiv=1"
        q += " ORDER BY name"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/medikamente")
async def add_medikament(request: Request):
    body = await request.json()
    required = ["person", "name"]
    for f in required:
        if not body.get(f):
            raise HTTPException(400, f"Feld '{f}' fehlt")

    person_id = None
    with get_db() as db:
        row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
        if row:
            person_id = row["id"]

        med_id = db.execute("""
            INSERT INTO medikamente (person_id,person,name,wirkstoff,dosierung,haeufigkeit,seit,bis,typ,notiz)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            person_id, body["person"], body["name"],
            body.get("wirkstoff",""), body.get("dosierung",""),
            body.get("haeufigkeit","täglich"),
            body.get("seit", date.today().isoformat()),
            body.get("bis",""),
            body.get("typ","dauermedikation"),
            body.get("notiz","")
        )).lastrowid
        db.commit()
    audit("CREATE", "medikamente", med_id, body["name"])
    return {"erfolg": True, "id": med_id}

@app.delete("/api/medikamente/{med_id}")
async def delete_medikament(med_id: int):
    with get_db() as db:
        db.execute("UPDATE medikamente SET aktiv=0 WHERE id=?", (med_id,))
        db.commit()
    audit("DELETE", "medikamente", med_id)
    return {"erfolg": True}

# ── MESSWERTE ─────────────────────────────────────────────

@app.get("/api/messwerte")
async def get_messwerte(person: Optional[str] = None, typ: Optional[str] = None, limit: int = 30):
    with get_db() as db:
        q = "SELECT * FROM messwerte WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if typ:    q += " AND typ=?"; params.append(typ)
        q += f" ORDER BY datum DESC LIMIT {limit}"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/messwerte")
async def add_messwert(request: Request):
    body = await request.json()
    with get_db() as db:
        person_id = None
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row:
                person_id = row["id"]
        mid = db.execute("""
            INSERT INTO messwerte (person_id,person,typ,wert,wert2,einheit,datum,notiz)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            person_id, body.get("person"), body.get("typ"),
            body.get("wert"), body.get("wert2"),
            body.get("einheit"), body.get("datum", date.today().isoformat()),
            body.get("notiz","")
        )).lastrowid
        db.commit()
    audit("CREATE", "messwerte", mid)
    return {"erfolg": True, "id": mid}

# ── EREIGNISSE ────────────────────────────────────────────

@app.get("/api/ereignisse")
async def get_ereignisse(person: Optional[str] = None, limit: int = 50):
    with get_db() as db:
        q = "SELECT * FROM ereignisse WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        q += f" ORDER BY datum DESC LIMIT {limit}"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/ereignisse")
async def add_ereignis(request: Request):
    body = await request.json()
    with get_db() as db:
        person_id = None
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row:
                person_id = row["id"]
        eid = db.execute("""
            INSERT INTO ereignisse (person_id,person,typ,titel,datum,arzt,einrichtung,notizen)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            person_id, body.get("person"), body.get("typ","arztbesuch"),
            body.get("titel"), body.get("datum", date.today().isoformat()),
            body.get("arzt",""), body.get("einrichtung",""), body.get("notizen","")
        )).lastrowid
        db.commit()
    audit("CREATE", "ereignisse", eid)
    return {"erfolg": True, "id": eid}

# ── POLICEN ───────────────────────────────────────────────

@app.get("/api/policen")
async def get_policen(person: Optional[str] = None):
    with get_db() as db:
        q = "SELECT * FROM policen WHERE aktiv=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        q += " ORDER BY person, art"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/policen")
async def add_police(request: Request):
    body = await request.json()
    with get_db() as db:
        person_id = None
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row:
                person_id = row["id"]
        pid = db.execute("""
            INSERT INTO policen (person_id,person,versicherung,art,tarif,versicherungs_nr,beitrag_monat,beginn,ablauf,selbstbehalt,notiz)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            person_id, body.get("person"), body.get("versicherung"),
            body.get("art","pkv"), body.get("tarif",""),
            body.get("versicherungs_nr",""), body.get("beitrag_monat",0),
            body.get("beginn",""), body.get("ablauf",""),
            body.get("selbstbehalt",0), body.get("notiz","")
        )).lastrowid
        db.commit()
    audit("CREATE", "policen", pid)
    return {"erfolg": True, "id": pid}

# ── DASHBOARD ─────────────────────────────────────────────

@app.get("/api/dashboard")
async def get_dashboard():
    with get_db() as db:
        personen = [dict(r) for r in db.execute("SELECT * FROM personen WHERE aktiv=1").fetchall()]

        # Statistiken pro Person
        for p in personen:
            pid = p["id"]
            p["dok_count"]  = db.execute("SELECT COUNT(*) as n FROM dokumente WHERE person_id=?", (pid,)).fetchone()["n"]
            p["med_count"]  = db.execute("SELECT COUNT(*) as n FROM medikamente WHERE person_id=? AND aktiv=1", (pid,)).fetchone()["n"]
            p["letzte_rechnungen"] = [dict(r) for r in db.execute(
                "SELECT * FROM dokumente WHERE person_id=? AND typ='rechnung' ORDER BY datum DESC LIMIT 3",
                (pid,)
            ).fetchall()]

        return {
            "personen": personen,
            "dok_gesamt": db.execute("SELECT COUNT(*) as n FROM dokumente").fetchone()["n"],
            "med_gesamt": db.execute("SELECT COUNT(*) as n FROM medikamente WHERE aktiv=1").fetchone()["n"],
            "letzte_dok": [dict(r) for r in db.execute(
                "SELECT * FROM dokumente ORDER BY erstellt_am DESC LIMIT 8"
            ).fetchall()],
        }

# ── NOTFALL-QR ────────────────────────────────────────────

@app.get("/api/notfall/{person_id}")
async def get_notfall(person_id: int):
    """Notfall-Daten für QR-Code (kein Auth nötig — Notfall!)"""
    with get_db() as db:
        p = db.execute("SELECT * FROM personen WHERE id=?", (person_id,)).fetchone()
        if not p:
            raise HTTPException(404)
        p = dict(p)
        meds = [dict(r) for r in db.execute(
            "SELECT name,dosierung,haeufigkeit,typ FROM medikamente WHERE person_id=? AND aktiv=1",
            (person_id,)
        ).fetchall()]
        # Allergien parsen
        allergien = []
        try:
            allergien = json.loads(p.get("allergien") or "[]")
        except:
            pass

        return {
            "name": p["name"],
            "geburtsdatum": p.get("geburtsdatum"),
            "blutgruppe": p.get("blutgruppe"),
            "allergien": allergien,
            "notfallkontakt": p.get("notfallkontakt"),
            "medikamente": meds,
            "hausarzt": p.get("arzt_hausarzt"),
            "generiert_am": datetime.now().isoformat()
        }

# ── KI-CHAT ───────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: Request):
    import urllib.request
    body = await request.json()
    user_msg = body.get("message", "")

    with get_db() as db:
        personen = [dict(r) for r in db.execute("SELECT * FROM personen WHERE aktiv=1").fetchall()]
        for p in personen:
            pid = p["id"]
            p["medikamente"] = [dict(r) for r in db.execute(
                "SELECT name,dosierung,haeufigkeit FROM medikamente WHERE person_id=? AND aktiv=1", (pid,)
            ).fetchall()]
        letzte_dok = [dict(r) for r in db.execute(
            "SELECT typ,aussteller,person,datum,betrag FROM dokumente ORDER BY erstellt_am DESC LIMIT 10"
        ).fetchall()]

    system = f"""Du bist der HealthLedger Assistent der Familie Kurzberg.
Du hilfst beim Verwalten privater Gesundheitsdaten, Versicherungen und Medikamente.
Alle Daten sind lokal und privat auf dem Raspberry Pi gespeichert.

Familienmitglieder: {json.dumps([p['name'] for p in personen], ensure_ascii=False)}
Aktuelle Medikamente: {json.dumps([{'person': p['name'], 'meds': p['medikamente']} for p in personen], ensure_ascii=False)}
Letzte Dokumente: {json.dumps(letzte_dok, ensure_ascii=False)}

Du kannst helfen bei:
- Fragen zu Medikamenten und Dosierungen
- Beihilfe- und PKV-Abrechnungen
- Übersicht über gespeicherte Dokumente
- Gesundheitstrends und Messwerten
- Allgemeinen Gesundheitsfragen (kein Arzt-Ersatz!)

WICHTIG: Du bist kein Arzt. Bei medizinischen Fragen immer auf einen Arzt verweisen.
Antworte auf Deutsch, präzise und hilfreich."""

    payload = json.dumps({
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
        "stream": False
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        loop = asyncio.get_event_loop()
        def do_chat():
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read())
            except Exception as e:
                return {"error": str(e)}
        result = await loop.run_in_executor(None, do_chat)
        antwort = (
            result.get("message", {}).get("content", "Keine Antwort")
            if "error" not in result
            else f"⚠️ KI nicht erreichbar: {result['error']}"
        )
    except Exception as e:
        antwort = f"⚠️ Fehler: {str(e)}"

    return {"antwort": antwort}

# ── DATEIZUGRIFF ──────────────────────────────────────────

@app.get("/api/uploads/{filename}")
async def get_upload(filename: str):
    fp = UPLOAD_DIR / filename
    if not fp.exists():
        raise HTTPException(404)
    audit("READ", "uploads", None, filename)
    return FileResponse(fp)

# ── STATISCHE DATEIEN & SPA ───────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/{path:path}")
async def spa_fallback(path: str):
    f = STATIC_DIR / "index.html"
    if f.exists():
        return FileResponse(f)
    raise HTTPException(404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
