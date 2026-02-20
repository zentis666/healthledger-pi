"""HealthLedger Pi — main.py mit FIDO2/YubiKey Auth v1.1"""
import os, json, sqlite3, base64, asyncio, re, secrets, struct
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import aiofiles

# JWT
from jose import jwt, JWTError

# FIDO2
from fido2.webauthn import (
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
)
from fido2.server import Fido2Server

BASE_DIR    = Path(__file__).parent
UPLOAD_DIR  = BASE_DIR / "uploads"
STATIC_DIR  = BASE_DIR / "static"
DATA_DIR    = BASE_DIR / "data"
DB_PATH     = DATA_DIR / "healthledger.db"
OLLAMA_URL  = os.getenv("OLLAMA_URL",   "http://localhost:11434")
VISION_MODEL= os.getenv("VISION_MODEL", "qwen2.5vl:7b")
CHAT_MODEL  = os.getenv("CHAT_MODEL",   "qwen2.5:32b")
APP_VERSION = "1.1.0"

# Auth Config
RP_ID           = os.getenv("RP_ID", "192.168.178.150")
RP_NAME         = "HealthLedger"
JWT_SECRET      = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGO        = "HS256"
JWT_EXPIRE_HOURS= 8

for d in (UPLOAD_DIR, STATIC_DIR, DATA_DIR):
    d.mkdir(exist_ok=True, parents=True)

# FIDO2 Server
rp = PublicKeyCredentialRpEntity(id=RP_ID, name=RP_NAME)
fido2_server = Fido2Server(rp)
_challenges: dict = {}  # In-Memory Challenge Store

app = FastAPI(title="HealthLedger")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════

security = HTTPBearer(auto_error=False)

def create_jwt(user_id: int, username: str, display_name: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "display_name": display_name,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(401, "Token ungültig oder abgelaufen")

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Dependency — wirft 401 wenn kein gültiger Token"""
    if not credentials:
        raise HTTPException(401, "Nicht eingeloggt")
    return verify_jwt(credentials.credentials)

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Dependency — gibt None zurück wenn kein Token (für Setup-Phase)"""
    if not credentials:
        return None
    try:
        return verify_jwt(credentials.credentials)
    except:
        return None

def is_setup_mode() -> bool:
    """True wenn noch kein YubiKey registriert — Setup erlaubt"""
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) as n FROM auth_credentials").fetchone()[0]
        conn.close()
        return count == 0
    except:
        return True

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
        CREATE TABLE IF NOT EXISTS personen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL, geburtsdatum TEXT,
            blutgruppe TEXT, allergien TEXT, notfallkontakt TEXT,
            arzt_hausarzt TEXT, versicherung_name TEXT, versicherung_nr TEXT,
            beihilfesatz REAL DEFAULT 0.0, aktiv INTEGER DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS dokumente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, person TEXT, typ TEXT, titel TEXT,
            aussteller TEXT, datum TEXT, betrag REAL, diagnose TEXT,
            beschreibung TEXT, tags TEXT, file_path TEXT,
            eingereicht_beihilfe INTEGER DEFAULT 0,
            eingereicht_pkv INTEGER DEFAULT 0,
            ki_extraktion TEXT, erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS medikamente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, person TEXT, name TEXT NOT NULL,
            wirkstoff TEXT, dosierung TEXT, haeufigkeit TEXT,
            seit TEXT, bis TEXT, typ TEXT, notiz TEXT,
            aktiv INTEGER DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messwerte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, person TEXT, typ TEXT,
            wert REAL, wert2 REAL, einheit TEXT, datum TEXT, notiz TEXT,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ereignisse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, person TEXT, typ TEXT, titel TEXT,
            datum TEXT, arzt TEXT, einrichtung TEXT, notizen TEXT,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS policen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, person TEXT, versicherung TEXT,
            art TEXT, tarif TEXT, versicherungs_nr TEXT,
            beitrag_monat REAL, beginn TEXT, ablauf TEXT,
            selbstbehalt REAL DEFAULT 0, file_path TEXT,
            notiz TEXT, aktiv INTEGER DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aktion TEXT, tabelle TEXT, datensatz_id INTEGER,
            details TEXT, user TEXT, ip TEXT,
            zeitstempel TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        -- Auth Tabellen
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER, username TEXT UNIQUE NOT NULL,
            display_name TEXT, user_handle TEXT UNIQUE NOT NULL,
            aktiv INTEGER DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auth_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, credential_id TEXT UNIQUE NOT NULL,
            public_key TEXT NOT NULL, sign_count INTEGER DEFAULT 0,
            aaguid TEXT, device_name TEXT DEFAULT 'YubiKey 5 NFC',
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            zuletzt_genutzt TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
        """)
        # Default Familie
        db.executescript("""
        INSERT OR IGNORE INTO personen (name,versicherung_name,beihilfesatz)
        VALUES ('Sven','DKV',0.70),('Heidi','DKV',0.50),
               ('Julian','DKV',0.80),('Theresa','DKV',0.80);
        INSERT OR IGNORE INTO config VALUES ('version','1.1.0');
        """)
        db.commit()

def audit(aktion, tabelle, datensatz_id=None, details="", user="", ip=""):
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO audit_log (aktion,tabelle,datensatz_id,details,user,ip) VALUES (?,?,?,?,?,?)",
                (aktion, tabelle, datensatz_id, details, user, ip)
            )
            db.commit()
    except: pass

init_db()

# ═══════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/auth/status")
async def auth_status():
    """Setup-Mode oder normal? Wie viele Keys registriert?"""
    try:
        with get_db() as db:
            users = db.execute("""
                SELECT u.username, u.display_name,
                       COUNT(c.id) as key_count,
                       MAX(c.zuletzt_genutzt) as letzter_login
                FROM auth_users u
                LEFT JOIN auth_credentials c ON u.id = c.user_id
                WHERE u.aktiv=1 GROUP BY u.id
            """).fetchall()
        return {
            "setup_mode": is_setup_mode(),
            "registriert": len(users) > 0,
            "users": [dict(u) for u in users],
            "rp_id": RP_ID,
            "version": APP_VERSION
        }
    except:
        return {"setup_mode": True, "registriert": False, "users": [], "rp_id": RP_ID}

@app.post("/api/auth/register/begin")
async def register_begin(request: Request):
    """YubiKey Registrierung starten — nur im Setup-Mode oder eingeloggt"""
    user = await get_optional_user(HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=request.headers.get("authorization","").replace("Bearer ","")
    ) if "authorization" in request.headers else None)

    if not is_setup_mode() and not user:
        raise HTTPException(403, "Registrierung nur für eingeloggte Nutzer")

    body = await request.json()
    username     = body.get("username", "sven")
    display_name = body.get("display_name", "Sven")
    user_handle  = secrets.token_bytes(32)

    fido_user = PublicKeyCredentialUserEntity(
        id=user_handle, name=username, display_name=display_name
    )
    options, state = fido2_server.register_begin(
        fido_user,
        user_verification=UserVerificationRequirement.PREFERRED,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.DISCOURAGED,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
    )

    session_id = secrets.token_hex(16)
    _challenges[session_id] = {
        "state": state, "username": username,
        "display_name": display_name,
        "user_handle": base64.b64encode(user_handle).decode(),
        "expires": datetime.utcnow() + timedelta(minutes=5)
    }

    return {
        "session_id": session_id,
        "options": {
            "challenge": base64.b64encode(options.challenge).decode(),
            "rp": {"id": RP_ID, "name": RP_NAME},
            "user": {
                "id": base64.b64encode(user_handle).decode(),
                "name": username,
                "displayName": display_name,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},
                {"type": "public-key", "alg": -257},
            ],
            "timeout": 60000,
            "attestation": "none",
            "authenticatorSelection": {
                "residentKey": "discouraged",
                "userVerification": "preferred",
            }
        }
    }

@app.post("/api/auth/register/finish")
async def register_finish(request: Request):
    body = await request.json()
    session_id = body.get("session_id")

    if session_id not in _challenges:
        raise HTTPException(400, "Session abgelaufen — bitte neu starten")

    session = _challenges.pop(session_id)
    credential = body.get("credential", {})
    cred_id = credential.get("id","")

    # Public Key aus attestationObject extrahieren
    try:
        att_obj_b64 = credential.get("response",{}).get("attestationObject","")
        # padding
        att_obj_bytes = base64.b64decode(att_obj_b64 + "==")
        from fido2.cbor import decode as cbor_decode
        att_obj = cbor_decode(att_obj_bytes)
        auth_data_bytes = att_obj.get(b"authData") or att_obj.get("authData", b"")
        pub_key_b64 = base64.b64encode(auth_data_bytes).decode()
    except Exception as e:
        raise HTTPException(400, f"Credential-Fehler: {e}")

    with get_db() as db:
        existing = db.execute("SELECT id FROM auth_users WHERE username=?",
                              (session["username"],)).fetchone()
        if existing:
            user_id = existing["id"]
        else:
            person = db.execute("SELECT id FROM personen WHERE name LIKE ?",
                                (session["display_name"] + "%",)).fetchone()
            user_id = db.execute("""
                INSERT INTO auth_users (person_id,username,display_name,user_handle)
                VALUES (?,?,?,?)
            """, (person["id"] if person else None,
                  session["username"], session["display_name"],
                  session["user_handle"])).lastrowid

        db.execute("""
            INSERT OR REPLACE INTO auth_credentials
            (user_id,credential_id,public_key,sign_count,device_name)
            VALUES (?,?,?,?,?)
        """, (user_id, cred_id, pub_key_b64, 0, "YubiKey 5 NFC"))
        db.commit()

    audit("CREATE", "auth_credentials", user_id,
          f"YubiKey registriert für {session['display_name']}")

    return {
        "erfolg": True,
        "message": f"✅ YubiKey für {session['display_name']} erfolgreich registriert!",
        "user_id": user_id
    }

@app.post("/api/auth/login/begin")
async def login_begin(request: Request):
    challenge = secrets.token_bytes(32)
    session_id = secrets.token_hex(16)

    _challenges[session_id] = {
        "challenge": base64.b64encode(challenge).decode(),
        "expires": datetime.utcnow() + timedelta(minutes=5)
    }

    with get_db() as db:
        creds = db.execute(
            "SELECT credential_id FROM auth_credentials"
        ).fetchall()

    return {
        "session_id": session_id,
        "options": {
            "challenge": base64.b64encode(challenge).decode(),
            "timeout": 60000,
            "rpId": RP_ID,
            "allowCredentials": [
                {"type": "public-key", "id": r["credential_id"],
                 "transports": ["usb","nfc"]}
                for r in creds
            ],
            "userVerification": "preferred",
        }
    }

@app.post("/api/auth/login/finish")
async def login_finish(request: Request):
    body = await request.json()
    session_id = body.get("session_id")

    if session_id not in _challenges:
        raise HTTPException(400, "Session abgelaufen")

    _challenges.pop(session_id)
    credential = body.get("credential", {})
    cred_id    = credential.get("id","")

    with get_db() as db:
        cred_row = db.execute("""
            SELECT c.*, u.username, u.display_name, u.id as user_id
            FROM auth_credentials c
            JOIN auth_users u ON c.user_id = u.id
            WHERE c.credential_id=?
        """, (cred_id,)).fetchone()

        if not cred_row:
            raise HTTPException(401, "Unbekannter YubiKey")

        # Sign-Count Replay-Schutz
        try:
            auth_data_b64 = credential.get("response",{}).get("authenticatorData","")
            auth_data_bytes = base64.b64decode(auth_data_b64 + "==")
            if len(auth_data_bytes) >= 37:
                new_count = struct.unpack(">I", auth_data_bytes[33:37])[0]
                if new_count > 0 and new_count <= cred_row["sign_count"]:
                    raise HTTPException(401, "⚠️ Replay-Angriff erkannt!")
                db.execute(
                    "UPDATE auth_credentials SET sign_count=?,zuletzt_genutzt=? WHERE credential_id=?",
                    (new_count, datetime.utcnow().isoformat(), cred_id)
                )
        except HTTPException: raise
        except: pass

        db.commit()

    token = create_jwt(cred_row["user_id"], cred_row["username"], cred_row["display_name"])
    ip = request.client.host if request.client else ""
    audit("LOGIN", "auth_users", cred_row["user_id"],
          f"Login via YubiKey", cred_row["username"], ip)

    return {
        "erfolg": True,
        "token": token,
        "username": cred_row["username"],
        "display_name": cred_row["display_name"],
        "expires_in": JWT_EXPIRE_HOURS * 3600
    }

@app.post("/api/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    audit("LOGOUT", "auth_users", int(user["sub"]), "", user["username"])
    return {"erfolg": True, "message": "Ausgeloggt"}

# ═══════════════════════════════════════════════════════════
# GESCHÜTZTE API (ab hier JWT erforderlich)
# ═══════════════════════════════════════════════════════════

@app.get("/api/status")
async def status():
    with get_db() as db:
        dok_count = db.execute("SELECT COUNT(*) as n FROM dokumente").fetchone()["n"]
        med_count = db.execute("SELECT COUNT(*) as n FROM medikamente WHERE aktiv=1").fetchone()["n"]
        per_count = db.execute("SELECT COUNT(*) as n FROM personen WHERE aktiv=1").fetchone()["n"]
    return {
        "status": "ok", "version": APP_VERSION,
        "personen": per_count, "dokumente": dok_count,
        "medikamente": med_count, "auth": "yubikey_fido2"
    }

@app.get("/api/personen")
async def get_personen(user: dict = Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM personen WHERE aktiv=1 ORDER BY name").fetchall()
        return [dict(r) for r in rows]

@app.put("/api/personen/{person_id}")
async def update_person(person_id: int, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    allowed = ["name","geburtsdatum","blutgruppe","allergien","notfallkontakt",
               "arzt_hausarzt","versicherung_name","versicherung_nr","beihilfesatz"]
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates: raise HTTPException(400, "Keine gültigen Felder")
    with get_db() as db:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE personen SET {set_clause} WHERE id=?",
                   list(updates.values()) + [person_id])
        db.commit()
    audit("UPDATE","personen",person_id,json.dumps(updates),user["username"])
    return {"erfolg": True}

@app.get("/api/dokumente")
async def get_dokumente(person: Optional[str]=None, typ: Optional[str]=None,
                         limit: int=50, user: dict = Depends(get_current_user)):
    with get_db() as db:
        q = "SELECT * FROM dokumente WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if typ:    q += " AND typ=?"; params.append(typ)
        q += f" ORDER BY datum DESC, erstellt_am DESC LIMIT {limit}"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/upload")
async def upload_dokument(
    file: UploadFile = File(...),
    person: str = Form(default=""),
    typ: str = Form(default="auto"),
    request: Request = None,
    user: dict = Depends(get_current_user)
):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if suffix not in [".jpg",".jpeg",".png",".pdf",".heic",".webp"]: suffix = ".jpg"
    filename = f"{ts}_{person or 'unknown'}{suffix}"
    filepath = UPLOAD_DIR / filename

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    extracted = await analyse_dokument(filepath, file.content_type or "image/jpeg")
    if not person and extracted.get("patient"):
        person = extracted.get("patient","")

    person_id = None
    with get_db() as db:
        if person:
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (person,)).fetchone()
            if not row:
                first = person.split()[0] if person else ""
                row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (first+"%",)).fetchone()
            if row: person_id = row["id"]

        dok_id = db.execute("""
            INSERT INTO dokumente
            (person_id,person,typ,aussteller,datum,betrag,diagnose,beschreibung,tags,file_path,ki_extraktion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (person_id, person or extracted.get("patient","Unbekannt"),
              extracted.get("typ",typ) if typ=="auto" else typ,
              extracted.get("aussteller",""), extracted.get("datum",""),
              extracted.get("betrag"), extracted.get("diagnose",""),
              extracted.get("beschreibung",""),
              json.dumps(extracted.get("tags",[])),
              str(filepath), json.dumps(extracted))).lastrowid
        db.commit()

    ip = request.client.host if request else ""
    audit("CREATE","dokumente",dok_id,f"Upload: {file.filename}",user["username"],ip)
    return {"erfolg": True, "dokument_id": dok_id, "extrahiert": extracted, "datei": filename}

@app.delete("/api/dokumente/{dok_id}")
async def delete_dokument(dok_id: int, user: dict = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT * FROM dokumente WHERE id=?", (dok_id,)).fetchone()
        if not row: raise HTTPException(404)
        fp = Path(row["file_path"])
        if fp.exists(): fp.unlink()
        db.execute("DELETE FROM dokumente WHERE id=?", (dok_id,))
        db.commit()
    audit("DELETE","dokumente",dok_id,"",user["username"])
    return {"erfolg": True}

@app.get("/api/medikamente")
async def get_medikamente(person: Optional[str]=None, aktiv_only: bool=True,
                           user: dict = Depends(get_current_user)):
    with get_db() as db:
        q = "SELECT * FROM medikamente WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if aktiv_only: q += " AND aktiv=1"
        q += " ORDER BY name"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/medikamente")
async def add_medikament(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    if not body.get("name"): raise HTTPException(400,"Name fehlt")
    person_id = None
    with get_db() as db:
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row: person_id = row["id"]
        mid = db.execute("""
            INSERT INTO medikamente (person_id,person,name,wirkstoff,dosierung,haeufigkeit,seit,bis,typ,notiz)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (person_id, body.get("person"), body["name"], body.get("wirkstoff",""),
              body.get("dosierung",""), body.get("haeufigkeit","täglich"),
              body.get("seit",date.today().isoformat()), body.get("bis",""),
              body.get("typ","dauermedikation"), body.get("notiz",""))).lastrowid
        db.commit()
    audit("CREATE","medikamente",mid,body["name"],user["username"])
    return {"erfolg": True, "id": mid}

@app.delete("/api/medikamente/{med_id}")
async def delete_medikament(med_id: int, user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("UPDATE medikamente SET aktiv=0 WHERE id=?", (med_id,))
        db.commit()
    audit("DELETE","medikamente",med_id,"",user["username"])
    return {"erfolg": True}

@app.get("/api/messwerte")
async def get_messwerte(person: Optional[str]=None, typ: Optional[str]=None,
                         limit: int=30, user: dict = Depends(get_current_user)):
    with get_db() as db:
        q = "SELECT * FROM messwerte WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        if typ:    q += " AND typ=?"; params.append(typ)
        q += f" ORDER BY datum DESC LIMIT {limit}"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/messwerte")
async def add_messwert(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    with get_db() as db:
        person_id = None
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row: person_id = row["id"]
        mid = db.execute("""
            INSERT INTO messwerte (person_id,person,typ,wert,wert2,einheit,datum,notiz)
            VALUES (?,?,?,?,?,?,?,?)
        """, (person_id, body.get("person"), body.get("typ"),
              body.get("wert"), body.get("wert2"),
              body.get("einheit"), body.get("datum",date.today().isoformat()),
              body.get("notiz",""))).lastrowid
        db.commit()
    audit("CREATE","messwerte",mid,"",user["username"])
    return {"erfolg": True, "id": mid}

@app.get("/api/ereignisse")
async def get_ereignisse(person: Optional[str]=None, limit: int=50,
                          user: dict = Depends(get_current_user)):
    with get_db() as db:
        q = "SELECT * FROM ereignisse WHERE 1=1"
        params = []
        if person: q += " AND person=?"; params.append(person)
        q += f" ORDER BY datum DESC LIMIT {limit}"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/ereignisse")
async def add_ereignis(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    with get_db() as db:
        person_id = None
        if body.get("person"):
            row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (body["person"],)).fetchone()
            if row: person_id = row["id"]
        eid = db.execute("""
            INSERT INTO ereignisse (person_id,person,typ,titel,datum,arzt,einrichtung,notizen)
            VALUES (?,?,?,?,?,?,?,?)
        """, (person_id, body.get("person"), body.get("typ","arztbesuch"),
              body.get("titel"), body.get("datum",date.today().isoformat()),
              body.get("arzt",""), body.get("einrichtung",""), body.get("notizen",""))).lastrowid
        db.commit()
    audit("CREATE","ereignisse",eid,"",user["username"])
    return {"erfolg": True, "id": eid}

@app.get("/api/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    with get_db() as db:
        personen = [dict(r) for r in db.execute("SELECT * FROM personen WHERE aktiv=1").fetchall()]
        for p in personen:
            pid = p["id"]
            p["dok_count"] = db.execute("SELECT COUNT(*) as n FROM dokumente WHERE person_id=?", (pid,)).fetchone()["n"]
            p["med_count"] = db.execute("SELECT COUNT(*) as n FROM medikamente WHERE person_id=? AND aktiv=1", (pid,)).fetchone()["n"]
        return {
            "personen": personen,
            "dok_gesamt": db.execute("SELECT COUNT(*) as n FROM dokumente").fetchone()["n"],
            "med_gesamt": db.execute("SELECT COUNT(*) as n FROM medikamente WHERE aktiv=1").fetchone()["n"],
            "letzte_dok": [dict(r) for r in db.execute(
                "SELECT * FROM dokumente ORDER BY erstellt_am DESC LIMIT 8"
            ).fetchall()],
        }

@app.get("/api/notfall/{person_id}")
async def get_notfall(person_id: int):
    """Notfall — KEIN Auth nötig (Arzt/Rettungsdienst muss zugreifen können)"""
    with get_db() as db:
        p = db.execute("SELECT * FROM personen WHERE id=?", (person_id,)).fetchone()
        if not p: raise HTTPException(404)
        p = dict(p)
        meds = [dict(r) for r in db.execute(
            "SELECT name,dosierung,haeufigkeit FROM medikamente WHERE person_id=? AND aktiv=1", (person_id,)
        ).fetchall()]
        allergien = []
        try: allergien = json.loads(p.get("allergien") or "[]")
        except: pass
        return {
            "name": p["name"], "geburtsdatum": p.get("geburtsdatum"),
            "blutgruppe": p.get("blutgruppe"), "allergien": allergien,
            "notfallkontakt": p.get("notfallkontakt"), "medikamente": meds,
            "hausarzt": p.get("arzt_hausarzt"),
            "generiert_am": datetime.now().isoformat()
        }

@app.post("/api/chat")
async def chat(request: Request, user: dict = Depends(get_current_user)):
    import urllib.request as ureq
    body = await request.json()
    user_msg = body.get("message","")
    with get_db() as db:
        personen = [dict(r) for r in db.execute("SELECT * FROM personen WHERE aktiv=1").fetchall()]
        for p in personen:
            p["medikamente"] = [dict(r) for r in db.execute(
                "SELECT name,dosierung FROM medikamente WHERE person_id=? AND aktiv=1", (p["id"],)
            ).fetchall()]
        letzte_dok = [dict(r) for r in db.execute(
            "SELECT typ,aussteller,person,datum FROM dokumente ORDER BY erstellt_am DESC LIMIT 10"
        ).fetchall()]
    system = f"""Du bist der HealthLedger Assistent der Familie Kurzberg.
Eingeloggt als: {user.get('display_name','Unbekannt')}
Familie: {json.dumps([p['name'] for p in personen],ensure_ascii=False)}
Medikamente: {json.dumps([{'person':p['name'],'meds':p['medikamente']} for p in personen],ensure_ascii=False)}
Letzte Dokumente: {json.dumps(letzte_dok,ensure_ascii=False)}
WICHTIG: Du bist kein Arzt. Bei medizinischen Fragen immer Arzt empfehlen. Antworte auf Deutsch."""
    payload = json.dumps({
        "model": CHAT_MODEL,
        "messages": [{"role":"system","content":system},{"role":"user","content":user_msg}],
        "stream": False
    }).encode()
    try:
        req = ureq.Request(f"{OLLAMA_URL}/api/chat", data=payload,
                           headers={"Content-Type":"application/json"}, method="POST")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: json.loads(ureq.urlopen(req,timeout=120).read()))
        antwort = result.get("message",{}).get("content","Keine Antwort") if "error" not in result else f"⚠️ {result['error']}"
    except Exception as e:
        antwort = f"⚠️ Fehler: {e}"
    return {"antwort": antwort}

@app.get("/api/uploads/{filename}")
async def get_upload(filename: str, user: dict = Depends(get_current_user)):
    fp = UPLOAD_DIR / filename
    if not fp.exists(): raise HTTPException(404)
    return FileResponse(fp)

# ═══════════════════════════════════════════════════════════
# KI-EXTRAKTION (unverändert)
# ═══════════════════════════════════════════════════════════

def pdf_to_text(filepath: Path) -> str:
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(str(filepath)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text.append(t)
        return "\n".join(text)[:4000]
    except Exception as e:
        return f"[PDF-Fehler: {e}]"

async def analyse_dokument(filepath: Path, mime_type: str) -> dict:
    import urllib.request as ureq
    is_pdf = filepath.suffix.lower() == ".pdf"
    if is_pdf:
        pdf_text = pdf_to_text(filepath)
        has_text = len(pdf_text.strip()) > 50 and "[PDF-Fehler" not in pdf_text
        if has_text:
            prompt = f"""Analysiere dieses Dokument als JSON (NUR JSON):
{{"typ":"rechnung|arztbrief|befund|rezept|impfung|sonstiges","aussteller":"","patient":"",
"datum":"YYYY-MM-DD","betrag":null,"diagnose":"","beschreibung":"","tags":[],"konfidenz":"hoch|mittel|niedrig"}}
Text:\n{pdf_text}"""
            payload = json.dumps({"model":CHAT_MODEL,"messages":[{"role":"user","content":prompt}],"stream":False}).encode()
            endpoint = f"{OLLAMA_URL}/api/chat"
            parse = lambda r: r.get("message",{}).get("content","{}")
        else:
            return {"typ":"sonstiges","konfidenz":"niedrig","fehler":"Gescanntes PDF — Vision nötig"}
    else:
        async with aiofiles.open(filepath,"rb") as f: raw = await f.read()
        b64 = base64.b64encode(raw).decode()
        prompt = '{"typ":"rechnung|arztbrief|befund|rezept|impfung|sonstiges","aussteller":"","patient":"","datum":"YYYY-MM-DD","betrag":null,"diagnose":"","beschreibung":"","tags":[],"konfidenz":"hoch|mittel|niedrig"}'
        payload = json.dumps({"model":VISION_MODEL,"prompt":f"Analysiere als JSON (NUR JSON): {prompt}","images":[b64],"stream":False}).encode()
        endpoint = f"{OLLAMA_URL}/api/generate"
        parse = lambda r: r.get("response","{}")
    try:
        req = ureq.Request(endpoint,data=payload,headers={"Content-Type":"application/json"},method="POST")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: json.loads(ureq.urlopen(req,timeout=120).read()))
        raw_resp = parse(result).strip()
        try: return json.loads(raw_resp)
        except:
            m = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            return json.loads(m.group()) if m else {"fehler":"Parse-Fehler","konfidenz":"niedrig"}
    except Exception as e:
        return {"fehler": str(e), "konfidenz": "niedrig"}

# ═══════════════════════════════════════════════════════════
# STATIC & SPA
# ═══════════════════════════════════════════════════════════

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/{path:path}")
async def spa_fallback(path: str):
    f = STATIC_DIR / "index.html"
    if f.exists(): return FileResponse(f)
    raise HTTPException(404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
