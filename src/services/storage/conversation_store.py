"""对话持久化存储（SQLite），按 course_id 隔离。

表结构：
  conversations: id, course_id, title, created_at, updated_at
  messages: id, conversation_id, role, content, citations, intent, grounded, mode, created_at
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20  # 拼入 LLM 上下文的最大历史消息数


def _uid() -> str:
    """生成短唯一 ID：毫秒时间戳前缀（便于排序）+ 随机段（避免同一毫秒冲突）。"""
    t = int(time.time() * 1000)
    return f"msg_{t:x}_{secrets.token_hex(4)}"


class ConversationStore:
    """对话与消息的 SQLite 持久化。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    citations TEXT NOT NULL DEFAULT '[]',
                    intent TEXT NOT NULL DEFAULT '{}',
                    grounded INTEGER NOT NULL DEFAULT 1,
                    mode TEXT NOT NULL DEFAULT 'qa',
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conv
                    ON messages(conversation_id, created_at);
            """)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
            if "intent" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN intent TEXT NOT NULL DEFAULT '{}'")

    # ── conversations ──────────────────────────────────────────────

    def create_conversation(self, course_id: str, title: str = "新对话") -> dict:
        import uuid
        cid = f"conv_{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations(id,course_id,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                (cid, course_id, title, now, now),
            )
        return self.get_conversation(cid) or {}

    def get_conversation(self, conv_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=?", (conv_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_conversations(self, course_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE course_id=? ORDER BY updated_at DESC",
                (course_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_conversation(self, conv_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            return cur.rowcount > 0

    def touch_conversation(self, conv_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (_now(), conv_id),
            )

    # ── messages ───────────────────────────────────────────────────

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: list | None = None,
        intent: dict | None = None,
        grounded: bool = True,
        mode: str = "qa",
    ) -> dict:
        mid = _uid()
        cit = json.dumps(citations or [], ensure_ascii=False)
        now = _now()
        with self._conn() as conn:
            conn.execute(
            """INSERT INTO messages(id,conversation_id,role,content,citations,intent,grounded,mode,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (mid, conversation_id, role, content, cit, json.dumps(intent or {}, ensure_ascii=False), int(grounded), mode, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (now, conversation_id),
            )
        return {"id": mid, "role": role, "content": content, "created_at": now}

    def get_history(
        self, conversation_id: str, max_messages: int = MAX_HISTORY_MESSAGES
    ) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? "
                "ORDER BY created_at ASC, id ASC LIMIT -1 OFFSET "
                "(SELECT MAX(0, COUNT(*)-?) FROM messages WHERE conversation_id=?)",
                (conversation_id, max_messages, conversation_id),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def get_latest_user_intent(self, conversation_id: str) -> dict | None:
        """读取最近一轮用户确认的路由状态，供指代性追问继承。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT intent FROM messages WHERE conversation_id=? AND role='user' "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row["intent"] or "{}")
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) and data else None
    def count_messages(self, conversation_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        return row["cnt"] if row else 0


    def ensure_conversation(self, conv_id: str, course_id: str, title: str = "新对话") -> None:
        """确保对话存在，不存在则创建。"""
        existing = self.get_conversation(conv_id)
        if existing:
            return
        now = _now()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations(id,course_id,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                (conv_id, course_id, title, now, now),
            )


    def close(self) -> None:
        pass


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
