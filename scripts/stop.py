"""Stop only this project's API process; never terminate MySQL or user apps."""
from pathlib import Path
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'

def owned(process):
    try:
        cmd = process.cmdline()
        return (process.name().lower() in {'python.exe', 'pythonw.exe'}
                and 'uvicorn' in cmd and 'app.main:app' in cmd
                and '8765' in cmd and Path(process.cwd()).resolve() == BACKEND.resolve())
    except (psutil.Error, OSError):
        return False

def stop():
    targets = [p for p in psutil.process_iter() if owned(p)]
    if not targets:
        print('StudyMind API is already stopped.')
    else:
        # Native Windows Python venv redirector and its child share the command.
        # Signal children first, then wait for the matching parents to exit.
        for process in sorted(targets, key=lambda p: p.pid, reverse=True):
            try: process.terminate()
            except psutil.NoSuchProcess: pass
        _, alive = psutil.wait_procs(targets, timeout=15)
        if alive:
            raise SystemExit('Some StudyMind processes did not stop; no force-kill was attempted.')
        print('StudyMind API stopped. MySQL and your data are retained.')
    (ROOT/'data'/'app.pid').unlink(missing_ok=True)

if __name__ == '__main__':
    stop()
