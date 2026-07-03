"""SQLite 文档元数据存储。"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class SQLiteDocStore:
    """文档元数据 CRUD：create、update_status、get、list、delete。"""

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                course TEXT NOT NULL DEFAULT '信号与系统',
                created_at TEXT NOT NULL,
                file_mtime REAL
            )
        """)
        self._conn.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(documents)")}
        if "file_mtime" not in cols:
            self._conn.execute("ALTER TABLE documents ADD COLUMN file_mtime REAL")
            self._conn.commit()

    def create(self, filename: str, file_path: str, course: str = "信号与系统") -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO documents (filename, file_path, status, chunk_count, course, created_at) "
            "VALUES (?, ?, 'pending', 0, ?, ?)",
            (filename, file_path, course, now),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get(self, doc_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT id, filename, file_path, status, chunk_count, course, created_at, file_mtime "
            "FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_status(self, doc_id: int, status: str, chunk_count: int | None = None) -> None:
        if chunk_count is None:
            self._conn.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                (status, doc_id),
            )
        else:
            self._conn.execute(
                "UPDATE documents SET status = ?, chunk_count = ? WHERE id = ?",
                (status, chunk_count, doc_id),
            )
        self._conn.commit()

    def list(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, filename, file_path, status, chunk_count, course, created_at, file_mtime "
            "FROM documents ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, doc_id: int) -> None:
        self._conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        self._conn.commit()

    def find_by_path(self, file_path: str) -> dict | None:
        """按绝对路径查找文档（取最新一条）。"""
        row = self._conn.execute(
            "SELECT id, filename, file_path, status, chunk_count, course, created_at, file_mtime "
            "FROM documents WHERE file_path = ? ORDER BY id DESC LIMIT 1",
            (file_path,),
        ).fetchone()
        return dict(row) if row else None

    def update_file_mtime(self, doc_id: int, mtime: float) -> None:
        self._conn.execute(
            "UPDATE documents SET file_mtime = ? WHERE id = ?",
            (mtime, doc_id),
        )
        self._conn.commit()

    def recover_stale_processing(self) -> int:
        """将中断留下的 processing 标记为 failed，便于重新入库。"""
        cur = self._conn.execute(
            "UPDATE documents SET status = 'failed', chunk_count = 0 WHERE status = 'processing'"
        )
        self._conn.commit()
        return cur.rowcount

    def health_check(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.error("SQLite 健康检查失败: %s", e)
            return False

    def close(self) -> None:
        self._conn.close()
