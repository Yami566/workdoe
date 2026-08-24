CREATE TABLE IF NOT EXISTS thread_reads (
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_message_id INTEGER NOT NULL DEFAULT 0,
    last_read_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_unread
ON messages(thread_id, is_hidden, id, sender_id);

CREATE INDEX IF NOT EXISTS idx_thread_reads_user
ON thread_reads(user_id, last_read_message_id DESC);

PRAGMA optimize;
