from __future__ import annotations

MESSAGE_PAGE_SIZE = 50
_MAX_MESSAGE_ID = (1 << 53) - 1
_INVALID_HISTORY = "Invalid message history link."

# Each range uses the existing (thread_id, is_hidden, id, sender_id) index.
_PARTICIPANT_SQL = """
    WITH page_ids AS (
        SELECT id FROM messages WHERE thread_id = ?1 AND is_hidden = 0 AND id <= CAST(?2 AS INTEGER)
        ORDER BY id DESC LIMIT ?3
    )
    SELECT messages.id, messages.sender_id, messages.body, messages.is_hidden,
           messages.created_at, users.display_name
    FROM page_ids
    JOIN messages ON messages.id = page_ids.id
    JOIN users ON users.id = messages.sender_id
    ORDER BY messages.id DESC
"""

# Bound each visibility range before combining them in one SQLite snapshot.
_MODERATION_SQL = """
    WITH visible_ids AS (
        SELECT id FROM messages WHERE thread_id = ?1 AND is_hidden = 0 AND id <= CAST(?2 AS INTEGER)
        ORDER BY id DESC LIMIT ?3
    ), hidden_ids AS (
        SELECT id FROM messages WHERE thread_id = ?1 AND is_hidden = 1 AND id <= CAST(?2 AS INTEGER)
        ORDER BY id DESC LIMIT ?3
    ), page_ids AS (
        SELECT id FROM visible_ids UNION ALL SELECT id FROM hidden_ids ORDER BY id DESC LIMIT ?3
    )
    SELECT messages.id, messages.sender_id, messages.body, messages.is_hidden,
           messages.created_at, users.display_name
    FROM page_ids
    JOIN messages ON messages.id = page_ids.id
    JOIN users ON users.id = messages.sender_id
    ORDER BY messages.id DESC
"""


def parse_message_through(values: list[str]) -> int | None:
    if not values:
        return None
    raw = values[0]
    if len(values) != 1 or not 0 < len(raw) <= len(str(_MAX_MESSAGE_ID)) or not raw.isascii() or not raw.isdecimal():
        raise ValueError(_INVALID_HISTORY)
    boundary = int(raw)
    if not 0 < boundary <= _MAX_MESSAGE_ID:
        raise ValueError(_INVALID_HISTORY)
    return boundary


def message_window_query(thread_id: int, through: int | None, *, include_hidden: bool = False) -> tuple[str, tuple]:
    boundary = through if through is not None else _MAX_MESSAGE_ID
    # Decimal text keeps large validated IDs out of the Python-to-JS BigInt conversion.
    return (_MODERATION_SQL if include_hidden else _PARTICIPANT_SQL), (thread_id, str(boundary), MESSAGE_PAGE_SIZE + 1)


def message_history_page(rows: list) -> tuple[list, int | None]:
    next_through = rows[MESSAGE_PAGE_SIZE]["id"] if len(rows) > MESSAGE_PAGE_SIZE else None
    return rows[:MESSAGE_PAGE_SIZE][::-1], next_through
