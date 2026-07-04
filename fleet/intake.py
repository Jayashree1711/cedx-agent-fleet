import os
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader

def get_db_connection(db_path: str = "out/pipeline.db") -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database, creating directories if needed.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection):
    """
    Initializes the raw records table.
    """
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_records (
                id TEXT,
                version INTEGER,
                source_format TEXT,
                source_version_hash TEXT,
                raw_json TEXT,
                owner TEXT,
                deadline TEXT,
                PRIMARY KEY (id, version)
            )
        """)

def compute_hash(content: str) -> str:
    """
    Computes a deterministic SHA-256 hash of the content.
    """
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()

def parse_txt_kv(text: str) -> Dict[str, Any]:
    """
    Parses key-value lines from a plain text block.
    Example:
      Id: REC-006
      Owner: f.haddad
    """
    record = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            # Convert values accordingly
            if key == "version":
                try:
                    record[key] = int(val)
                except ValueError:
                    record[key] = val
            elif key in ["amount", "value", "total", "amount_tbd"]:
                # Keep as string first, normalization handles conversions
                if val.lower() == "null" or val == "":
                    record[key] = None
                else:
                    try:
                        record[key] = int(val)
                    except ValueError:
                        try:
                            record[key] = float(val)
                        except ValueError:
                            record[key] = val
            else:
                record[key] = val
    return record

def parse_eml(file_path: Path) -> Dict[str, Any]:
    """
    Parses a simple EML file.
    """
    content = file_path.read_text(encoding="utf-8")
    # Separate headers from body
    parts = content.split("\n\n", 1)
    body = parts[1] if len(parts) > 1 else parts[0]
    record = parse_txt_kv(body)
    # Ensure ID matches filename if missing
    if "id" not in record:
        record["id"] = file_path.stem.split("_")[0]
    return record

def parse_pdf(file_path: Path) -> Dict[str, Any]:
    """
    Parses a PDF file using pypdf.
    """
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    record = parse_txt_kv(text)
    if "id" not in record:
        record["id"] = file_path.stem.split("_")[0]
    return record

def run_intake(seed_dir: str, db_path: str = "out/pipeline.db") -> List[Dict[str, Any]]:
    """
    Ingests all records from feed.json and seed/inbox/ EML/PDF files.
    """
    conn = get_db_connection(db_path)
    init_db(conn)
    
    seed_path = Path(seed_dir)
    feed_file = seed_path / "feed.json"
    inbox_dir = seed_path / "inbox"
    
    records_to_insert = []
    
    # 1. Parse feed.json
    if feed_file.exists():
        content = feed_file.read_text(encoding="utf-8")
        feed_hash = compute_hash(content)
        try:
            items = json.loads(content)
            for item in items:
                rec_id = item.get("id")
                version = item.get("version", 1)
                # Compute specific item hash based on its serialized form
                item_str = json.dumps(item, sort_keys=True)
                item_hash = compute_hash(item_str)
                records_to_insert.append({
                    "id": rec_id,
                    "version": version,
                    "source_format": "feed",
                    "source_version_hash": item_hash,
                    "raw_json": json.dumps(item),
                    "owner": item.get("owner"),
                    "deadline": item.get("deadline")
                })
        except Exception as e:
            print(f"Error parsing feed.json: {e}")

    # 2. Parse EML/PDF files in inbox
    if inbox_dir.exists():
        for file_path in inbox_dir.glob("*"):
            if file_path.suffix.lower() == ".eml":
                try:
                    raw_content = file_path.read_text(encoding="utf-8")
                    item_hash = compute_hash(raw_content)
                    record = parse_eml(file_path)
                    records_to_insert.append({
                        "id": record.get("id"),
                        "version": record.get("version", 1),
                        "source_format": "eml",
                        "source_version_hash": item_hash,
                        "raw_json": json.dumps(record),
                        "owner": record.get("owner"),
                        "deadline": record.get("deadline")
                    })
                except Exception as e:
                    print(f"Error parsing EML {file_path.name}: {e}")
            elif file_path.suffix.lower() == ".pdf":
                try:
                    # PDF is binary, hash the raw bytes
                    raw_bytes = file_path.read_bytes()
                    item_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
                    record = parse_pdf(file_path)
                    records_to_insert.append({
                        "id": record.get("id"),
                        "version": record.get("version", 1),
                        "source_format": "pdf",
                        "source_version_hash": item_hash,
                        "raw_json": json.dumps(record),
                        "owner": record.get("owner"),
                        "deadline": record.get("deadline")
                    })
                except Exception as e:
                    print(f"Error parsing PDF {file_path.name}: {e}")

    # 3. Persist to SQLite
    with conn:
        for rec in records_to_insert:
            conn.execute("""
                INSERT OR REPLACE INTO raw_records 
                (id, version, source_format, source_version_hash, raw_json, owner, deadline)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["id"],
                rec["version"],
                rec["source_format"],
                rec["source_version_hash"],
                rec["raw_json"],
                rec["owner"],
                rec["deadline"]
            ))
            
    # Return list of all stored raw records (latest versions first)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_records")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
