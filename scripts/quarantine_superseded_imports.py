"""Quarantine superseded imported rows, preserving records and attempt FKs."""
import import_open_question_bank as bank
import json
manifest=json.loads((bank.ROOT/'data/question_bank_manifest.json').read_text(encoding='utf8'))
keep={(s,bank.normalize(r['stem'])) for s,rs in manifest.items() for r in rs}
with bank.core.db() as db:
 rows=db.execute("SELECT q.* FROM questions q JOIN question_sources s ON s.question_id=q.id WHERE q.stem NOT LIKE '【内置日练%'").fetchall()
 remove=[dict(r) for r in rows if r['subject'] in manifest and (r['subject'],bank.normalize(r['stem'])) not in keep]
 path=bank.ROOT/'data/superseded_import_backup.json'
 if remove and not path.exists():path.write_text(json.dumps(remove,ensure_ascii=False,indent=2),encoding='utf8')
 for r in remove:db.execute('UPDATE questions SET stem=? WHERE id=?',('【内置日练隔离：来源去重或缺上下文】'+r['stem'],r['id']))
 print('Quarantined',len(remove))
with bank.core.db() as db:
 active=db.execute("SELECT q.subject,q.stem FROM questions q JOIN question_sources s ON s.question_id=q.id WHERE q.stem NOT LIKE '【内置日练%'").fetchall()
 assert all((r['subject'],bank.normalize(r['stem'])) in keep for r in active)
 print('Active sourced rows verified',len(active))
