"""Small SQLAlchemy bridge with bound parameters and transactional connections.

The existing service queries use DB-API qmark placeholders. This module adapts
those to MySQL without interpolating values. Schema is reflected through an
in-memory SQLite database into SQLAlchemy metadata; MySQL gets actual InnoDB
foreign keys and indexes, not a silently substituted local database.
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, MetaData, String, Column, Computed, Index, event, text, inspect
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.exc import IntegrityError


class Result:
    def __init__(self, result):
        self.rowcount = result.rowcount
        self._rows = [dict(x) for x in result.mappings().all()] if result.returns_rows else []
        self._index = 0
    def fetchone(self):
        if self._index >= len(self._rows): return None
        value = self._rows[self._index]; self._index += 1; return value
    def fetchall(self):
        value = self._rows[self._index:]; self._index = len(self._rows); return value
    def __iter__(self): return iter(self.fetchall())


def mysql_sql(sql):
    sql = re.sub(r'ON CONFLICT\([^)]*\) DO UPDATE SET', 'ON DUPLICATE KEY UPDATE', sql, flags=re.I)
    sql = re.sub(r'excluded\.([A-Za-z_][A-Za-z0-9_]*)', r'VALUES(\1)', sql, flags=re.I)
    sql = re.sub(r'INSERT OR IGNORE', 'INSERT IGNORE', sql, flags=re.I)
    # Preserve quoted question marks, and escape literal percent for pymysql.
    out, quote = [], None
    for char in sql:
        if char in ('\"', "'"):
            quote = None if quote == char else char if quote is None else quote
        out.append('%s' if char == '?' and quote is None else '%%' if char == '%' else char)
    return ''.join(out)


class Connection:
    def __init__(self, engine):
        self.engine = engine
        self.conn = engine.connect()
        self.closed = False
        self._file_originals = {}
    def write_file(self, path, data):
        """Atomic replacement, restored on SQL rollback; safe for retried provisioning."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path not in self._file_originals:
            self._file_originals[path] = path.read_bytes() if path.exists() else None
        temp = path.with_name(path.name + '.provisioning-part')
        try:
            temp.write_bytes(data)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    def _restore_files(self):
        for path, previous in self._file_originals.items():
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        self._file_originals.clear()
    def execute(self, sql, parameters=()):
        if sql.strip().upper() in ('BEGIN IMMEDIATE','BEGIN EXCLUSIVE','BEGIN'):
            if self.engine.dialect.name == 'sqlite':
                return Result(self.conn.exec_driver_sql('BEGIN IMMEDIATE'))
            if not self.conn.in_transaction(): self.conn.begin()
            return None
        if self.engine.dialect.name == 'mysql': sql = mysql_sql(sql)
        try: return Result(self.conn.exec_driver_sql(sql, tuple(parameters)))
        except IntegrityError as exc: raise sqlite3.IntegrityError('Constraint violation') from exc
    def executescript(self, script):
        for statement in script.split(';'):
            if statement.strip(): self.execute(statement)
    def commit(self):
        self.conn.commit()
        self._file_originals.clear()
    def rollback(self):
        self.conn.rollback()
        self._restore_files()
    def close(self):
        if not self.closed:
            try:
                self.conn.close()
                self._restore_files()
            finally:
                self.closed = True
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        try:
            self.rollback() if exc_type else self.commit()
        finally: self.close()


class Database:
    def __init__(self, url):
        kwargs = {'pool_pre_ping': True}
        if url.startswith('sqlite'):
            kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 30}
        self.engine = create_engine(url, **kwargs)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def configure(dbapi_connection, _):
                dbapi_connection.execute('PRAGMA foreign_keys=ON')
                dbapi_connection.execute('PRAGMA busy_timeout=30000')
    def connect(self): return Connection(self.engine)
    def initialize(self, schema):
        if self.engine.dialect.name == 'sqlite':
            with self.engine.connect() as con:
                con.connection.driver_connection.executescript(schema)
                con.commit()
            return
        if self.engine.dialect.name != 'mysql': raise ValueError('Only MySQL and SQLite supported')
        source = create_engine('sqlite://')
        with source.connect() as con:
            con.connection.driver_connection.executescript(schema)
            con.commit()
        metadata = MetaData()
        metadata.reflect(bind=source)
        # SQLite reflection omits inline ON DELETE clauses in some releases.
        # Restore these from PRAGMA rather than silently losing cascade semantics.
        with source.connect() as con:
            for table in metadata.tables.values():
                rules = con.exec_driver_sql(f'PRAGMA foreign_key_list("{table.name}")').mappings().all()
                for constraint in table.foreign_key_constraints:
                    local = next(iter(constraint.columns)).name
                    rule = next((r for r in rules if r['from'] == local), None)
                    if rule and rule['on_delete'] not in ('NO ACTION', 'RESTRICT'):
                        constraint.ondelete = rule['on_delete']
                        for element in constraint.elements: element.ondelete = rule['on_delete']
        large = {'content','description','summary','goal','note','notes','feedback','error_message','stem','explanation','secret_encrypted','password_hash'}
        for table in metadata.tables.values():
            table.dialect_options['mysql']['engine'] = 'InnoDB'
            table.dialect_options['mysql']['charset'] = 'utf8mb4'
            table.dialect_options['mysql']['collate'] = 'utf8mb4_unicode_ci'
            for column in table.columns:
                if isinstance(column.type, String):
                    if column.name == 'id' or column.name.endswith('_id'): column.type = String(36)
                    elif column.name == 'email': column.type = String(254)
                    elif column.name in large or column.name.endswith('_json'): column.type = LONGTEXT()
                    else: column.type = String(512 if column.name in {'title','name','original_name','storage_key','avatar_url'} else 255)
                    if isinstance(column.type, LONGTEXT) and column.server_default is not None:
                        column.server_default.arg = text('(' + str(column.server_default.arg) + ')')
            for idx in list(table.indexes):
                if idx.name == 'one_active_generation': table.indexes.remove(idx)
        # A dedicated conversation_generation_locks primary key serializes generation.
        # MySQL cannot cascade through FK columns used by stored generated columns.
        metadata.create_all(self.engine)
        # Repair databases created by an older prototype. Drop and add constraints
        # separately: MySQL rejects a same-name drop+add in one ALTER statement.
        inspector = inspect(self.engine)
        for table in metadata.tables.values():
            existing = inspector.get_foreign_keys(table.name)
            for constraint in table.foreign_key_constraints:
                wanted = (constraint.ondelete or 'NO ACTION').upper()
                local_columns = [column.name for column in constraint.columns]
                target = next(iter(constraint.elements)).target_fullname.split('.')
                target_table, target_column = target[-2], target[-1]
                found = next((item for item in existing if item['constrained_columns'] == local_columns and item['referred_table'] == target_table), None)
                current = (found.get('options', {}).get('ondelete') if found else None) or 'NO ACTION'
                if found and current.upper() == wanted:
                    continue
                if found:
                    with self.engine.begin() as con:
                        con.exec_driver_sql(f"ALTER TABLE `{table.name}` DROP FOREIGN KEY `{found['name']}`")
                name = f"sm_fk_{table.name}_{local_columns[0]}"
                with self.engine.begin() as con:
                    columns = ','.join(f'`{column}`' for column in local_columns)
                    clause = '' if wanted == 'NO ACTION' else f' ON DELETE {wanted}'
                    con.exec_driver_sql(f"ALTER TABLE `{table.name}` ADD CONSTRAINT `{name}` FOREIGN KEY ({columns}) REFERENCES `{target_table}` (`{target_column}`){clause}")
                existing = inspect(self.engine).get_foreign_keys(table.name)
        source.dispose()
