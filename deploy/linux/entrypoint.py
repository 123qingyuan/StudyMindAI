"""Fail early without logging keys; generate encryption key only in data volume."""
import os
import sys
from pathlib import Path

os.umask(0o077)
data = Path(os.environ['STUDYMIND_DATA_DIR'])
if not data.is_dir() or not os.access(data, os.W_OK):
    raise SystemExit('Data volume must be writable by UID/GID 10001. See docs/LINUX.md.')
# Import from /app/backend even when this file is invoked by absolute path.
sys.path.insert(0, '/app/backend')
from app.ai.service import cipher
cipher()
os.execvp(sys.argv[1], sys.argv[1:])
