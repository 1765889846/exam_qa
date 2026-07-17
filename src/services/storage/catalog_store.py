"""学院 / 课程目录（docs/04 4.2）"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COLLEGE_ID = "college-default"
DEFAULT_COLLEGE_NAME = "默认学院"
DEFAULT_COURSE_ID = "course-default"
DEFAULT_COURSE_NAME = "默认课程"

LEGACY_COURSE_IDS = ("course-signals-2025",)
LEGACY_COLLEGE_IDS = ("college-telecom",)


class CatalogStore:
    """colleges / courses CRUD."""

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._seed_defaults()
        self._migrate_legacy_seeds()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS colleges (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                college_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (college_id) REFERENCES colleges(id)
            );
            """
        )
        self._conn.commit()

    def _seed_defaults(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO colleges (id, name, created_at) VALUES (?, ?, ?)",
            (DEFAULT_COLLEGE_ID, DEFAULT_COLLEGE_NAME, now),
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO courses (id, college_id, name, created_at) "
            "VALUES (?, ?, ?, ?)",
            (DEFAULT_COURSE_ID, DEFAULT_COLLEGE_ID, DEFAULT_COURSE_NAME, now),
        )
        self._conn.execute(
            "UPDATE colleges SET name = ? WHERE id = ?",
            (DEFAULT_COLLEGE_NAME, DEFAULT_COLLEGE_ID),
        )
        self._conn.execute(
            "UPDATE courses SET name = ?, college_id = ? WHERE id = ?",
            (DEFAULT_COURSE_NAME, DEFAULT_COLLEGE_ID, DEFAULT_COURSE_ID),
        )
        self._conn.commit()

    def _migrate_legacy_seeds(self) -> None:
        tables = {
            r[0]
            for r in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "documents" in tables:
            for legacy_id in LEGACY_COURSE_IDS:
                cur = self._conn.execute(
                    "UPDATE documents SET course_id = ?, course = ? WHERE course_id = ?",
                    (DEFAULT_COURSE_ID, DEFAULT_COURSE_NAME, legacy_id),
                )
                if cur.rowcount:
                    logger.info(
                        "迁移 %d 条文档: %s -> %s",
                        cur.rowcount,
                        legacy_id,
                        DEFAULT_COURSE_ID,
                    )
        for legacy_id in LEGACY_COURSE_IDS:
            self._conn.execute("DELETE FROM courses WHERE id = ?", (legacy_id,))
        for legacy_id in LEGACY_COLLEGE_IDS:
            n = self._conn.execute(
                "SELECT COUNT(*) FROM courses WHERE college_id = ?",
                (legacy_id,),
            ).fetchone()[0]
            if n == 0:
                self._conn.execute("DELETE FROM colleges WHERE id = ?", (legacy_id,))
        self._conn.commit()

    def list_colleges(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, name, created_at FROM colleges ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_courses(self, college_id: str | None = None) -> list[dict]:
        if college_id:
            rows = self._conn.execute(
                "SELECT id, college_id, name, created_at FROM courses "
                "WHERE college_id = ? ORDER BY name",
                (college_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, college_id, name, created_at FROM courses ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_course(self, course_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, college_id, name, created_at FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        return dict(row) if row else None

    def require_course(self, course_id: str) -> dict:
        from src.exceptions import NotFoundException

        course = self.get_course(course_id)
        if course is None:
            raise NotFoundException(f"课程不存在: {course_id}")
        return course

    def close(self) -> None:
        self._conn.close()
