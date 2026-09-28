"""One-time non-destructive FK migration for the initial local installation."""
import sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import inspect
from app import core
from app.schema import SCHEMA
from app.extra_schema import SCHEMA as AI_SCHEMA
engine=core._database.engine
assert engine.dialect.name=='mysql'
source=sqlite3.connect(':memory:');source.executescript(SCHEMA+'\n'+AI_SCHEMA);source.row_factory=sqlite3.Row
inspector=inspect(engine)
with engine.begin() as con:
    cols=[x['name'] for x in inspector.get_columns('generations')]
    if 'active_conversation_id' in cols:
        con.exec_driver_sql('ALTER TABLE generations DROP INDEX one_active_generation, DROP COLUMN active_conversation_id')
changes=[]
for table in inspector.get_table_names():
    rules=source.execute('PRAGMA foreign_key_list("'+table+'")').fetchall()
    current=inspect(engine).get_foreign_keys(table)
    for rule in rules:
        found=next((f for f in current if f['constrained_columns']==[rule['from']]),None)
        wanted=rule['on_delete']
        if found and found.get('options',{}).get('ondelete','NO ACTION').upper()==wanted.upper():continue
        name=found['name'] if found else f'fk_{table}_{rule["from"]}'
        # DROP+ADD in one atomic DDL statement; no temporarily missing constraint.
        drop=f'DROP FOREIGN KEY `{name}`, ' if found else ''
        sql=f'ALTER TABLE `{table}` {drop}ADD CONSTRAINT `{name}` FOREIGN KEY (`{rule["from"]}`) REFERENCES `{rule["table"]}` (`{rule["to"]}`) ON DELETE {wanted}'
        with engine.begin() as con:con.exec_driver_sql(sql)
        changes.append(table+'.'+rule['from']+' '+wanted)
print({'migrated_foreign_keys':changes})
with core.db() as c:
    found=c.execute('SELECT version FROM schema_versions WHERE version=?',(2,)).fetchone()
    if not found:c.execute('INSERT INTO schema_versions(version,applied_at) VALUES(?,?)',(2,core.now_iso()))
print('MIGRATION_OK')
