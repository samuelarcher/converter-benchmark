import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "benchmark.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    converter_name TEXT NOT NULL,
    output_format TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    error TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, converter_name, output_format)
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversion_id INTEGER NOT NULL REFERENCES conversions(id),
    scorer TEXT NOT NULL,
    score INTEGER,
    notes TEXT,
    rubric TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(conversion_id, scorer)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SEED_SETTINGS = [
    ("default_output_format", "markdown"),
]


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for key, value in SEED_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# --- documents ---

def insert_document(filename: str, file_path: str, file_ext: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, file_path, file_ext) VALUES (?, ?, ?)",
            (filename, file_path, file_ext),
        )
        conn.commit()
        return cur.lastrowid


def get_document(doc_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()


def list_documents():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()


def document_exists(file_path: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM documents WHERE file_path = ?", (file_path,)
        ).fetchone()
        return row is not None


# --- conversions ---

def upsert_conversion(
    document_id: int,
    converter_name: str,
    output_format: str,
    content: str,
    error,
    duration_ms: int,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO conversions
               (document_id, converter_name, output_format, content, error, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(document_id, converter_name, output_format)
               DO UPDATE SET content=excluded.content, error=excluded.error,
                             duration_ms=excluded.duration_ms,
                             created_at=CURRENT_TIMESTAMP""",
            (document_id, converter_name, output_format, content, error, duration_ms),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM conversions WHERE document_id=? AND converter_name=? AND output_format=?",
            (document_id, converter_name, output_format),
        ).fetchone()
        return row["id"]


def get_conversions_for_doc(doc_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM conversions WHERE document_id = ? ORDER BY output_format, converter_name",
            (doc_id,),
        ).fetchall()


def get_conversion(conv_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM conversions WHERE id = ?", (conv_id,)).fetchone()


# --- scores ---

def upsert_score(conversion_id: int, scorer: str, score, notes: str, rubric: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO scores (conversion_id, scorer, score, notes, rubric)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(conversion_id, scorer)
               DO UPDATE SET score=excluded.score, notes=excluded.notes,
                             rubric=excluded.rubric, created_at=CURRENT_TIMESTAMP""",
            (conversion_id, scorer, score, notes, rubric),
        )
        conn.commit()


def get_scores_for_conversion(conv_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM scores WHERE conversion_id = ?", (conv_id,)
        ).fetchall()


def get_scores_for_doc(doc_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT s.*, c.converter_name, c.output_format
               FROM scores s
               JOIN conversions c ON s.conversion_id = c.id
               WHERE c.document_id = ?""",
            (doc_id,),
        ).fetchall()


# --- settings ---

def get_setting_raw(key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting_raw(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


# --- delete ---

def delete_document(doc_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM scores WHERE conversion_id IN (SELECT id FROM conversions WHERE document_id = ?)",
            (doc_id,),
        )
        conn.execute("DELETE FROM conversions WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()


def delete_all_documents():
    with get_conn() as conn:
        conn.execute("DELETE FROM scores")
        conn.execute("DELETE FROM conversions")
        conn.execute("DELETE FROM documents")
        conn.commit()


# --- doc summary helpers ---

def get_doc_summary():
    """Return documents with counts and avg LLM score."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT d.*,
                      COUNT(DISTINCT c.output_format || '|' || c.converter_name) AS conversion_count,
                      GROUP_CONCAT(DISTINCT c.output_format) AS formats_run,
                      AVG(s.score) AS avg_llm_score
               FROM documents d
               LEFT JOIN conversions c ON c.document_id = d.id
               LEFT JOIN scores s ON s.conversion_id = c.id AND s.scorer = 'llm'
               GROUP BY d.id
               ORDER BY d.created_at DESC"""
        ).fetchall()
