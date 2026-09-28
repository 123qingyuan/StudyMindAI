"""Provision every existing account from controlled offline sources.

Output contains only hashed account identifiers; no email addresses or secrets.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")
sys.path.insert(0, str(ROOT / "backend"))
from app import core
from app.default_content import _copy_default_content

REPORT = ROOT / "data" / "provision_existing_users_report.json"


def account_tag(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def main() -> None:
    results = []
    with core.db() as db:
        users = db.execute("SELECT id FROM users").fetchall()
    for row in users:
        uid = row["id"]
        try:
            result = _copy_default_content(uid)
            results.append({"account": account_tag(uid), "result": result})
        except Exception as exc:
            results.append({"account": account_tag(uid), "error": type(exc).__name__})
    report = {
        "version": "builtin-v2",
        "accounts_seen": len(users),
        "completed": sum(1 for x in results if x.get("result", {}).get("status") in {"completed", "already_complete"}),
        "failed": sum(1 for x in results if "error" in x),
        "accounts": results,
        "emails_included": False,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "accounts"}, ensure_ascii=False))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
