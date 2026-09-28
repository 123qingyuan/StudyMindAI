"""Controlled, per-user provisioning of built-in content.

This module never reads another user's rows.  The only sources are the checked-in
manifest and the two seed-script constants; every account gets independent rows.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from . import core
from .document.parser import Page, chunks

ROOT = core.ROOT
VERSION = "builtin-v2"
MANIFEST = ROOT / "data" / "question_bank_manifest.json"


def _load_constants(path: Path, names: tuple[str, ...]) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("studymind_seed_constants", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load controlled seed source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: getattr(module, name) for name in names}


_COMPUTER = _load_constants(ROOT / "scripts" / "seed_computer_library.py", ("TOPICS",))
_MULTI = _load_constants(ROOT / "scripts" / "seed_multidisciplinary_library.py", ("LIBRARIES",))


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _schema_compat(conn) -> None:
    """Create/migrate provenance and completion tables on old SQLite/MySQL DBs."""
    # MySQL cannot index TEXT as a PRIMARY KEY and its FK columns must match
    # the referenced VARCHAR(36) UUID column.  SQLite accepts TEXT here, but
    # the live deployment is MySQL, so keep the portable declaration indexable.
    conn.execute("""CREATE TABLE IF NOT EXISTS question_sources (
        question_id VARCHAR(36) PRIMARY KEY,
        source_key CHAR(64) NOT NULL,
        dataset TEXT NOT NULL, config_name TEXT NOT NULL, split_name TEXT NOT NULL,
        source_url TEXT NOT NULL, license_name TEXT NOT NULL, imported_at TEXT NOT NULL,
        FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS builtin_provisioning (
        user_id VARCHAR(36) PRIMARY KEY, version VARCHAR(32) NOT NULL, status VARCHAR(16) NOT NULL,
        completed_at VARCHAR(40), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    # Older installations may have the table without the new fixed-width key.
    try:
        conn.execute("ALTER TABLE question_sources ADD COLUMN source_key CHAR(64)")
    except Exception:
        pass


def _controlled_documents() -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for name, text in _COMPUTER["TOPICS"].items():
        result.append(("计算机知识体系", name, text))
    for library, topics in _MULTI["LIBRARIES"].items():
        for name, text in topics.items():
            result.append((library, name, text))
    if len(result) != 24 or len({name for _, name, _ in result}) != 24:
        raise RuntimeError("controlled seed documents must contain exactly 24 unique documents")
    return result


def _manifest() -> dict[str, list[dict[str, Any]]]:
    bank = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(bank) != 28 or any(len(rows) != 100 for rows in bank.values()):
        raise RuntimeError("question manifest must contain 28 subjects with 100 rows each")
    for subject, rows in bank.items():
        if len({_normalize(row["stem"]) for row in rows}) != 100:
            raise RuntimeError(f"manifest contains duplicate stems: {subject}")
    return bank


def _insert_doc(conn, user_id: str, kb_id: str, domain: str, name: str, text: str, ts: str) -> None:
    filename = f"[内置] {name}.md"
    old = conn.execute("SELECT id FROM documents WHERE user_id=? AND original_name=?", (user_id, filename)).fetchone()
    if old:
        return
    document_id = core.uid()
    storage_key = f"{user_id}_{document_id}.md"
    path = Path(core.UPLOAD_DIR) / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.write_file(path, text.encode("utf-8"))
    conn.execute("""INSERT INTO documents
        (id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (document_id, user_id, filename, storage_key,
        "text/markdown", len(text.encode()), "ready", text, f"{name}（内置资料）", ts, ts))
    conn.execute("""INSERT INTO document_links
        (document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode)
        VALUES(?,?,?,?,?,?)""", (document_id, kb_id, "内置资料", "text", 1, "keyword"))
    for chunk in chunks([Page(1, text, "text")]):
        conn.execute("INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)",
                     (core.uid(), document_id, user_id, chunk["page"], chunk["ordinal"], chunk["content"]))
    for title in (line[3:] for line in text.splitlines() if line.startswith("## ")):
        conn.execute("INSERT INTO knowledge_points(id,user_id,title,description,source_document_id,created_at) VALUES(?,?,?,?,?,?)",
                     (core.uid(), user_id, title, f"{name}中的内置知识点", document_id, ts))


def _insert_questions(conn, user_id: str, bank: dict[str, list[dict[str, Any]]], ts: str) -> None:
    for subject, rows in bank.items():
        for row in rows:
            source_key = hashlib.sha256(f"{user_id}|{subject}|{row['dataset']}|{row['config']}|{row['source_item']}".encode()).hexdigest()
            existing = conn.execute("SELECT q.id FROM questions q JOIN question_sources s ON s.question_id=q.id WHERE q.user_id=? AND s.source_key=?",
                                    (user_id, source_key)).fetchone()
            if existing:
                continue
            question_id = core.uid()
            explanation = f"来源：{row['dataset']}；{row['license']}；条目 {row['source_item']}\n{row['url']}\n{row.get('explanation', '')}"
            conn.execute("""INSERT INTO questions
                (id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (question_id, user_id, subject, row["type"], "中等",
                row["stem"], _dumps(row["options"]), _dumps(row["answer"]), explanation,
                _dumps([row["config"], "公开来源题库"]), ts))
            conn.execute("""INSERT INTO question_sources
                (question_id,source_key,dataset,config_name,split_name,source_url,license_name,imported_at)
                VALUES(?,?,?,?,?,?,?,?)""", (question_id, source_key, row["dataset"], row["config"],
                "public", row["url"], row["license"], ts))


def _is_complete(conn, user_id: str, bank: dict[str, list[dict[str, Any]]]) -> bool:
    marker = conn.execute("SELECT version,status FROM builtin_provisioning WHERE user_id=?", (user_id,)).fetchone()
    if not marker or marker["version"] != VERSION or marker["status"] != "completed":
        return False
    # A committed completion marker respects subsequent deliberate user deletions.
    return True


def _expected_source_keys(user_id: str, bank: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [hashlib.sha256(f"{user_id}|{subject}|{row['dataset']}|{row['config']}|{row['source_item']}".encode()).hexdigest()
            for subject, rows in bank.items() for row in rows]


def _count_expected_sources(conn, keys: list[str]) -> int:
    if not keys:
        return 0
    placeholders = ",".join("?" for _ in keys)
    return conn.execute(f"SELECT COUNT(*) AS n FROM question_sources WHERE source_key IN ({placeholders})", keys).fetchone()["n"]


def _copy_default_content(user_id: str, conn=None) -> dict[str, Any]:
    """Provision one isolated account; completion marker is written last.

    Passing an existing connection lets registration atomically include the user
    row and provisioning.  Standalone callers get the same transaction boundary.
    """
    owns_connection = conn is None
    connection = conn or core.db()
    created_files: list[Path] = []
    try:
        bank = _manifest()
        if _is_complete(connection, user_id, bank):
            return {"status": "already_complete", "version": VERSION}
        # The user_id primary key serializes concurrent provisioning for the same account.
        connection.execute("INSERT INTO builtin_provisioning(user_id,version,status) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET version=excluded.version,status=excluded.status",
                           (user_id, VERSION, "running"))
        ts = core.now_iso()
        kb_ids: dict[str, str] = {}
        for domain, _, _ in _controlled_documents():
            if domain not in kb_ids:
                row = connection.execute("SELECT id FROM knowledge_bases WHERE user_id=? AND name=?", (user_id, domain)).fetchone()
                kb_ids[domain] = row["id"] if row else core.uid()
                if not row:
                    connection.execute("INSERT INTO knowledge_bases(id,user_id,name,description,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                                       (kb_ids[domain], user_id, domain, "内置资料（每个账户独立副本）", ts, ts))
        for domain, name, text in _controlled_documents():
            _insert_doc(connection, user_id, kb_ids[domain], domain, name, text, ts)
        _insert_questions(connection, user_id, bank, ts)
        if not _is_complete_after_rows(connection, user_id, bank):
            raise RuntimeError("built-in provisioning readback failed")
        connection.execute("UPDATE builtin_provisioning SET status='completed',completed_at=? WHERE user_id=? AND version=?",
                           (ts, user_id, VERSION))
        result = {"status": "completed", "version": VERSION, "documents": 24, "questions": 2800}
        if owns_connection:
            connection.commit()
        return result
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def _is_complete_after_rows(conn, user_id: str, bank: dict[str, list[dict[str, Any]]]) -> bool:
    docs = conn.execute("SELECT COUNT(*) AS n FROM documents WHERE user_id=? AND original_name LIKE '[内置] %'", (user_id,)).fetchone()["n"]
    expected = _expected_source_keys(user_id, bank)
    placeholders = ",".join("?" for _ in expected)
    subjects = conn.execute(f"SELECT q.subject,COUNT(*) AS n FROM questions q JOIN question_sources s ON s.question_id=q.id WHERE q.user_id=? AND s.source_key IN ({placeholders}) GROUP BY q.subject", [user_id, *expected]).fetchall()
    return docs == 24 and {r["subject"]: r["n"] for r in subjects} == {s: 100 for s in bank}
