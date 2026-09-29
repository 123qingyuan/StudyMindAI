"""Run via compose exec after registration; output only hashes/counts, no keys."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

assert os.getuid() == 10001, 'Application must run without root'
data = Path('/var/lib/studymind')
with sqlite3.connect(data / 'studymind.sqlite3') as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1, 'Dedicated test volume required'
    subjects = dict(db.execute('SELECT subject,COUNT(*) FROM questions GROUP BY subject'))
    assert len(subjects) == 28 and set(subjects.values()) == {100}
    docs = list(db.execute('SELECT storage_key FROM documents'))
    assert len(docs) == 31
    for (key,) in docs:
        assert (data / 'uploads' / key).is_file()
    assert db.execute("SELECT COUNT(*) FROM builtin_provisioning WHERE status='completed'").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM builtin_expansion_runs WHERE status='completed'").fetchone()[0] == 1
keys = {}
for name in ('.jwt-key', '.ai-settings.key'):
    path = data / name
    assert path.stat().st_mode & 0o777 == 0o600
    keys[name] = hashlib.sha256(path.read_bytes()).hexdigest()
from cryptography.fernet import Fernet
cipher = Fernet((data / '.ai-settings.key').read_bytes())
probe = data / '.acceptance-encryption-probe'
if probe.exists():
    assert cipher.decrypt(probe.read_bytes()) == b'disposable persistence probe'
else:
    probe.write_bytes(cipher.encrypt(b'disposable persistence probe'))
print(json.dumps({'uid': os.getuid(), 'subjects': len(subjects), 'questions': sum(subjects.values()), 'documents': len(docs), 'keys_sha256': keys}, sort_keys=True))
