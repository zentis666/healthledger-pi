"""
Apple Health Importer für HealthLedger Pi
=========================================
Importiert export.xml aus dem Apple Health Export ZIP

Apple Health XML Struktur:
  <HealthData locale="de_DE">
    <Record type="HKQuantityTypeIdentifierBodyMass"
            sourceName="Sven's iPhone"
            unit="kg"
            startDate="2024-01-15 08:30:00 +0100"
            endDate="2024-01-15 08:30:00 +0100"
            value="82.4"/>
    <Record type="HKQuantityTypeIdentifierBloodPressureSystolic" .../>
    <Record type="HKQuantityTypeIdentifierBloodPressureDiastolic" .../>
    ...
  </HealthData>

HealthKit → HealthLedger Mapping:
  HKQuantityTypeIdentifierBodyMass           → gewicht  (kg)
  HKQuantityTypeIdentifierBloodPressureSystolic  → blutdruck systolisch
  HKQuantityTypeIdentifierBloodPressureDiastolic → blutdruck diastolisch
  HKQuantityTypeIdentifierBloodGlucose       → blutzucker (mmol/L oder mg/dL)
  HKQuantityTypeIdentifierBodyTemperature    → temperatur (°C)
  HKQuantityTypeIdentifierHeartRate          → puls (BPM)
  HKQuantityTypeIdentifierOxygenSaturation   → laborwert SpO2 (%)
  HKQuantityTypeIdentifierBodyMassIndex      → laborwert BMI
  HKQuantityTypeIdentifierStepCount          → (optional, Aktivität)
  HKQuantityTypeIdentifierRestingHeartRate   → puls (Ruhepuls)
  HKCategoryTypeIdentifierSleepAnalysis      → (Skip - kein HealthLedger-Typ)
  HKQuantityTypeIdentifierActiveEnergyBurned → (Skip)
"""

import xml.etree.ElementTree as ET
import zipfile, json, sqlite3, os, sys
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent / "data" / "healthledger.db"

# ── MAPPING ──────────────────────────────────────────────────────────────
# HKType → (hl_typ, einheit_override, umrechnung_fn)
HK_MAP = {
    # Gewicht
    "HKQuantityTypeIdentifierBodyMass": {
        "typ": "gewicht", "feld": "wert", "einheit": "kg",
        "conv": lambda v, u: (round(float(v), 1), None)
    },
    # Blutdruck (werden zusammengeführt)
    "HKQuantityTypeIdentifierBloodPressureSystolic": {
        "typ": "blutdruck", "feld": "wert", "einheit": "mmHg",
        "conv": lambda v, u: (int(float(v)), None)
    },
    "HKQuantityTypeIdentifierBloodPressureDiastolic": {
        "typ": "blutdruck", "feld": "wert2", "einheit": "mmHg",
        "conv": lambda v, u: (int(float(v)), None)
    },
    # Blutzucker
    "HKQuantityTypeIdentifierBloodGlucose": {
        "typ": "blutzucker", "feld": "wert", "einheit": "mmol/L",
        "conv": lambda v, u: (
            round(float(v), 1) if u in ("mmol/L","mmol/l")
            else round(float(v) / 18.0, 1),  # mg/dL → mmol/L
            None
        )
    },
    # Temperatur
    "HKQuantityTypeIdentifierBodyTemperature": {
        "typ": "temperatur", "feld": "wert", "einheit": "°C",
        "conv": lambda v, u: (
            round(float(v), 1) if u in ("°C","degC","C")
            else round((float(v) - 32) * 5/9, 1),  # °F → °C
            None
        )
    },
    # Puls / Herzfrequenz
    "HKQuantityTypeIdentifierHeartRate": {
        "typ": "puls", "feld": "wert", "einheit": "BPM",
        "conv": lambda v, u: (int(float(v)), None)
    },
    "HKQuantityTypeIdentifierRestingHeartRate": {
        "typ": "puls", "feld": "wert", "einheit": "BPM",
        "conv": lambda v, u: (int(float(v)), None)
    },
    # SpO2 / Sauerstoffsättigung
    "HKQuantityTypeIdentifierOxygenSaturation": {
        "typ": "laborwert", "feld": "wert", "einheit": "%",
        "name": "SpO2",
        "conv": lambda v, u: (round(float(v) * 100, 1) if float(v) <= 1.0
                              else round(float(v), 1), None)
    },
    # BMI
    "HKQuantityTypeIdentifierBodyMassIndex": {
        "typ": "laborwert", "feld": "wert", "einheit": "BMI",
        "name": "BMI",
        "conv": lambda v, u: (round(float(v), 1), None)
    },
    # Körperfett
    "HKQuantityTypeIdentifierBodyFatPercentage": {
        "typ": "laborwert", "feld": "wert", "einheit": "%",
        "name": "Körperfett",
        "conv": lambda v, u: (round(float(v) * 100, 1) if float(v) <= 1.0
                              else round(float(v), 1), None)
    },
}

# Diese Types komplett ignorieren (zu viel Rauschen)
HK_SKIP = {
    "HKQuantityTypeIdentifierStepCount",
    "HKQuantityTypeIdentifierDistanceWalkingRunning",
    "HKQuantityTypeIdentifierActiveEnergyBurned",
    "HKQuantityTypeIdentifierBasalEnergyBurned",
    "HKQuantityTypeIdentifierFlightsClimbed",
    "HKQuantityTypeIdentifierDistanceCycling",
    "HKCategoryTypeIdentifierSleepAnalysis",
    "HKCategoryTypeIdentifierAppleStandHour",
    "HKQuantityTypeIdentifierAppleExerciseTime",
    "HKQuantityTypeIdentifierAppleStandTime",
    "HKQuantityTypeIdentifierWalkingSpeed",
    "HKQuantityTypeIdentifierWalkingStepLength",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage",
    "HKQuantityTypeIdentifierStairAscentSpeed",
    "HKQuantityTypeIdentifierStairDescentSpeed",
    "HKQuantityTypeIdentifierVO2Max",
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure",
    "HKCategoryTypeIdentifierHandwashingEvent",
    "HKCategoryTypeIdentifierMindfulSession",
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance",
}

def parse_date(dt_str: str) -> str:
    """Apple Health Datum → YYYY-MM-DD"""
    if not dt_str: return date.today().isoformat()
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str[:19], fmt[:len(dt_str[:19])]).strftime("%Y-%m-%d")
        except: pass
    return dt_str[:10]

def get_person_id(db, person_name: str) -> int | None:
    if not person_name: return None
    row = db.execute("SELECT id FROM personen WHERE name=?", (person_name,)).fetchone()
    if row: return row[0]
    row = db.execute("SELECT id FROM personen WHERE name LIKE ?", (person_name.split()[0]+"%",)).fetchone()
    return row[0] if row else None

def import_apple_health(source_path: str, person_name: str,
                        dry_run: bool = False,
                        deduplicate: bool = True,
                        max_per_day: int = 3) -> dict:
    """
    Hauptfunktion: Importiert Apple Health Export in HealthLedger

    Args:
        source_path:  Pfad zur export.zip oder export.xml
        person_name:  Familienname (z.B. "Sven")
        dry_run:      Nur analysieren, nicht schreiben
        deduplicate:  Doppelte Messungen pro Tag überspringen
        max_per_day:  Max. Messungen pro Typ pro Tag (verhindert Watch-Spam)

    Returns:
        dict mit Statistiken
    """
    source = Path(source_path)
    stats = defaultdict(int)
    stats["person"] = person_name
    stats["source"] = str(source)

    # ── XML laden ────────────────────────────────────────────────────────
    if source.suffix.lower() == ".zip":
        print(f"📦 Entpacke {source.name}…")
        with zipfile.ZipFile(source) as z:
            # Suche export.xml
            xml_files = [f for f in z.namelist() if "export.xml" in f and "cda" not in f.lower()]
            if not xml_files:
                raise FileNotFoundError("export.xml nicht in ZIP gefunden")
            xml_file = xml_files[0]
            print(f"   → {xml_file} ({z.getinfo(xml_file).file_size / 1024 / 1024:.1f} MB)")
            xml_data = z.read(xml_file)
    elif source.suffix.lower() == ".xml":
        xml_data = source.read_bytes()
    else:
        raise ValueError(f"Unbekanntes Format: {source.suffix}")

    # Apple Health DTD-Bug umgehen (iOS 16+)
    # Entferne die problematische DOCTYPE-Zeile
    if b"<!DOCTYPE" in xml_data[:2000]:
        lines = xml_data.split(b"\n")
        cleaned = []
        skip = False
        for line in lines:
            if b"<!DOCTYPE" in line:
                skip = True
            if skip:
                if b"]>" in line or (b">" in line and b"<!ATTLIST" not in line and b"<!ELEMENT" not in line):
                    skip = False
                continue
            cleaned.append(line)
        xml_data = b"\n".join(cleaned)

    print(f"🔍 Parse XML…")
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        # Fallback: iterparse mit Error-Recovery
        print(f"   ⚠️ Parse-Fehler: {e} — versuche Fallback…")
        import io
        root = ET.parse(io.BytesIO(xml_data)).getroot()

    # ── Records sammeln ──────────────────────────────────────────────────
    records_raw = defaultdict(list)  # date → [(typ, wert, wert2, einheit, notiz)]
    bp_buffer = defaultdict(dict)    # date+time → {systolic: x, diastolic: y}

    total_records = 0
    skipped_types = set()

    for record in root.iter("Record"):
        hk_type = record.get("type", "")
        total_records += 1

        if hk_type in HK_SKIP:
            continue
        if hk_type not in HK_MAP:
            skipped_types.add(hk_type)
            continue

        mapping = HK_MAP[hk_type]
        value_str = record.get("value", "")
        unit_str  = record.get("unit", "")
        dt_str    = record.get("startDate", record.get("endDate", ""))
        datum     = parse_date(dt_str)

        if not value_str:
            continue

        try:
            conv_val, _ = mapping["conv"](value_str, unit_str)
        except (ValueError, ZeroDivisionError):
            stats["fehler"] += 1
            continue

        entry = {
            "typ":    mapping["typ"],
            "einheit": mapping.get("einheit", unit_str),
            "datum":  datum,
            "notiz":  mapping.get("name", ""),
            "feld":   mapping["feld"],
            "wert":   None,
            "wert2":  None,
            "hk_type": hk_type,
        }
        entry[mapping["feld"]] = conv_val

        # Blutdruck: Systolisch + Diastolisch zusammenführen
        if hk_type in ("HKQuantityTypeIdentifierBloodPressureSystolic",
                       "HKQuantityTypeIdentifierBloodPressureDiastolic"):
            key = dt_str[:16]  # Minuten-genau für Pairing
            if "Systolic" in hk_type:
                bp_buffer[key]["sys"]   = conv_val
                bp_buffer[key]["datum"] = datum
            else:
                bp_buffer[key]["dia"] = conv_val
                bp_buffer[key]["datum"] = datum
            # Wenn beide vorhanden → als eine Messung speichern
            if "sys" in bp_buffer[key] and "dia" in bp_buffer[key]:
                bp = bp_buffer.pop(key)
                records_raw[datum].append({
                    "typ": "blutdruck", "wert": bp["sys"], "wert2": bp["dia"],
                    "einheit": "mmHg", "datum": datum, "notiz": ""
                })
                stats["blutdruck"] += 1
        else:
            records_raw[datum].append(entry)
            stats[mapping["typ"]] += 1

    stats["total_raw"] = total_records
    stats["unbekannte_typen"] = len(skipped_types)

    # ── Deduplizierung ────────────────────────────────────────────────────
    # Pro Tag + Typ max. max_per_day Messungen (Watch sendet oft stündlich)
    records_final = []
    day_type_count = defaultdict(int)

    for datum in sorted(records_raw.keys()):
        for entry in records_raw[datum]:
            key = f"{datum}_{entry['typ']}"
            if deduplicate and day_type_count[key] >= max_per_day:
                stats["dedupliziert"] += 1
                continue
            day_type_count[key] += 1
            records_final.append(entry)

    stats["zu_importieren"] = len(records_final)

    if dry_run:
        print(f"\n📊 DRY RUN — Analyse für {person_name}:")
        print(f"   Records in XML:     {total_records:,}")
        print(f"   Gemappt:            {sum(v for k,v in stats.items() if k in ['gewicht','blutdruck','blutzucker','temperatur','puls','laborwert']):,}")
        print(f"   Nach Deduplizierung: {len(records_final):,}")
        print(f"   Übersprungen (Typ): {stats['unbekannte_typen']} unbekannte Typen")
        if skipped_types:
            print(f"\n   Nicht importierte Typen (erste 10):")
            for t in sorted(skipped_types)[:10]:
                print(f"     - {t.replace('HKQuantityTypeIdentifier','').replace('HKCategoryTypeIdentifier','')}")
        return dict(stats)

    # ── In DB schreiben ───────────────────────────────────────────────────
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    person_id = get_person_id(db, person_name)
    if not person_id:
        db.close()
        raise ValueError(f"Person '{person_name}' nicht in HealthLedger gefunden. "
                         f"Verfügbare Personen: " +
                         str([r[0] for r in db.execute("SELECT name FROM personen").fetchall()]))

    # Bestehende Messungen laden für Deduplizierung
    existing = set()
    if deduplicate:
        for row in db.execute(
            "SELECT typ, datum FROM messwerte WHERE person_id=?", (person_id,)
        ).fetchall():
            existing.add(f"{row['typ']}_{row['datum']}")

    imported = 0
    skipped_existing = 0

    for entry in records_final:
        # Bereits vorhanden?
        if deduplicate:
            day_key = f"{entry['typ']}_{entry['datum']}"
            if day_key in existing:
                skipped_existing += 1
                continue

        notiz = f"Apple Health Import"
        if entry.get("notiz"): notiz += f" ({entry['notiz']})"

        db.execute("""
            INSERT INTO messwerte (person_id, person, typ, wert, wert2, einheit, datum, notiz)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            person_id, person_name,
            entry["typ"], entry.get("wert"), entry.get("wert2"),
            entry["einheit"], entry["datum"], notiz
        ))
        imported += 1

    db.execute("""
        INSERT INTO audit_log (aktion, tabelle, datensatz_id, details, user)
        VALUES ('IMPORT', 'messwerte', ?, ?, 'apple_health')
    """, (person_id, f"Apple Health Import: {imported} Messungen für {person_name}"))

    db.commit()
    db.close()

    stats["importiert"]        = imported
    stats["bereits_vorhanden"] = skipped_existing

    return dict(stats)


def main():
    """CLI-Interface"""
    import argparse
    parser = argparse.ArgumentParser(
        description="Apple Health → HealthLedger Importer"
    )
    parser.add_argument("source", help="Pfad zur export.zip oder export.xml")
    parser.add_argument("person", help="Familienname (z.B. 'Sven')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur analysieren, nicht schreiben")
    parser.add_argument("--max-per-day", type=int, default=3,
                        help="Max. Messungen pro Typ pro Tag (default: 3)")
    parser.add_argument("--no-dedup", action="store_true",
                        help="Keine Deduplizierung")
    args = parser.parse_args()

    print(f"\n🏥 HealthLedger — Apple Health Importer")
    print(f"{'─'*45}")
    print(f"Quelle: {args.source}")
    print(f"Person: {args.person}")
    print(f"Modus:  {'DRY RUN' if args.dry_run else 'IMPORT'}")
    print(f"{'─'*45}\n")

    try:
        stats = import_apple_health(
            source_path=args.source,
            person_name=args.person,
            dry_run=args.dry_run,
            deduplicate=not args.no_dedup,
            max_per_day=args.max_per_day,
        )

        print(f"\n{'─'*45}")
        print(f"✅ Fertig!\n")
        if args.dry_run:
            print(f"   Würde importieren: {stats.get('zu_importieren', 0):,} Messungen")
        else:
            print(f"   ✅ Importiert:      {stats.get('importiert', 0):,}")
            print(f"   ⏭️  Übersprungen:   {stats.get('bereits_vorhanden', 0):,} (bereits vorhanden)")
            print(f"   📊 Dedupliziert:    {stats.get('dedupliziert', 0):,}")

        typen = {k: v for k, v in stats.items()
                 if k in ('gewicht','blutdruck','blutzucker','temperatur','puls','laborwert') and v > 0}
        if typen:
            print(f"\n   Typen:")
            for t, n in sorted(typen.items()):
                print(f"     {t:15} {n:>6,}x")

    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
