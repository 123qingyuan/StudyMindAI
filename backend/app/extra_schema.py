"""Intelligence schema, owned by the modular AI router.

Core must execute SCHEMA once after its users/tasks/courses/exams/study_records
schema. Existing prototype AI tables remain compatible; new attributes live in
side tables, so no destructive migration/ALTER is required.
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'tutor', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'completed', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_settings (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 config_json TEXT NOT NULL, secret_encrypted TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_usage (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 purpose TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 status TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_generation_locks (
 conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
 generation_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_bases (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 original_name TEXT NOT NULL, storage_key TEXT NOT NULL, mime_type TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, status TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
 summary TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_links (
 document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
 knowledge_base_id TEXT REFERENCES knowledge_bases(id) ON DELETE SET NULL,
 course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
 folder TEXT NOT NULL DEFAULT '', extraction_method TEXT NOT NULL DEFAULT 'text',
 page_count INTEGER NOT NULL DEFAULT 1, index_mode TEXT NOT NULL DEFAULT 'not_indexed',
 embedding_fingerprint TEXT, error_code TEXT
);
CREATE TABLE IF NOT EXISTS document_chunks (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 page INTEGER, ordinal INTEGER NOT NULL, content TEXT NOT NULL,
 UNIQUE(document_id, ordinal)
);
CREATE TABLE IF NOT EXISTS document_actions (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, action TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_points (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', source_document_id TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject TEXT NOT NULL, type TEXT NOT NULL, difficulty TEXT NOT NULL, stem TEXT NOT NULL,
 options_json TEXT NOT NULL DEFAULT '[]', answer_json TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '',
 knowledge_points_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_rubrics (
 question_id TEXT PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
 rubric_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS question_records (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE, answer_json TEXT NOT NULL,
 is_correct INTEGER NOT NULL, score REAL NOT NULL, answered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_reviews (
 record_id TEXT PRIMARY KEY REFERENCES question_records(id) ON DELETE CASCADE,
 grading_method TEXT NOT NULL, feedback TEXT NOT NULL, rubric_scores_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS ai_reports (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, metrics_json TEXT NOT NULL, content TEXT NOT NULL,
 report_type TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_metadata (
 report_id TEXT PRIMARY KEY REFERENCES ai_reports(id) ON DELETE CASCADE,
 source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_tasks (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 goal TEXT NOT NULL, status TEXT NOT NULL, risk_level TEXT NOT NULL, plan_json TEXT NOT NULL,
 result_json TEXT, error_message TEXT, requires_confirmation INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_confirmations (
 agent_task_id TEXT PRIMARY KEY REFERENCES agent_tasks(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 plan_hash TEXT NOT NULL, token_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
 consumed_at TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS agent_tool_calls (
 id TEXT PRIMARY KEY, agent_task_id TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
 tool_name TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_step_results (
 agent_task_id TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
 step_index INTEGER NOT NULL, output_json TEXT NOT NULL,
 PRIMARY KEY(agent_task_id, step_index)
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_docs_user ON documents(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chunk_user ON document_chunks(user_id, document_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_user ON ai_usage(user_id, created_at);
"""
