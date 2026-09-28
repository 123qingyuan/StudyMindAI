"""Relational source schema. SQLite development and MySQL production share it."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 display_name TEXT NOT NULL, avatar_url TEXT, timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'todo',
 priority INTEGER NOT NULL DEFAULT 2, due_date TEXT, category TEXT NOT NULL DEFAULT '学习',
 tags TEXT NOT NULL DEFAULT '[]', estimated_minutes INTEGER NOT NULL DEFAULT 30,
 completed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, teacher TEXT NOT NULL DEFAULT '', classroom TEXT NOT NULL DEFAULT '',
 weekday INTEGER, start_time TEXT, end_time TEXT,
 start_week INTEGER NOT NULL DEFAULT 1, end_week INTEGER NOT NULL DEFAULT 20,
 week_pattern TEXT NOT NULL DEFAULT 'all', term_start_date TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exams (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject TEXT NOT NULL, exam_date TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_records (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject TEXT NOT NULL, minutes INTEGER NOT NULL, studied_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS focus_sessions (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, record_id TEXT
);
CREATE TABLE IF NOT EXISTS study_plans (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, goal TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 daily_minutes INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', source TEXT NOT NULL DEFAULT 'manual',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_plan_items (
 id TEXT PRIMARY KEY, study_plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
 plan_date TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 estimated_minutes INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'todo', task_id TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks(user_id,due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id,status);
CREATE INDEX IF NOT EXISTS idx_records_user_date ON study_records(user_id,studied_at);
CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id,expires_at);
CREATE INDEX IF NOT EXISTS idx_course_user ON courses(user_id,weekday);
CREATE INDEX IF NOT EXISTS idx_exam_user ON exams(user_id,exam_date);
'''
