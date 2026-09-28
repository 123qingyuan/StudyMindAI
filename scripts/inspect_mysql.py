from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import core
with core.db() as c:
    for t in ['conversations','generations','messages']:
        print(t,c.execute('SHOW CREATE TABLE '+t).fetchone())
