"""我的题库 SQLite 存储：题目、试卷与试卷题目顺序均按 course_id 隔离。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.exceptions import BadRequestException, NotFoundException


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class QuestionBankStore:
    """题库持久化；不承担出题逻辑，所有读写均显式带 course_id。"""

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS question_bank_questions (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                stem TEXT NOT NULL,
                question_type TEXT NOT NULL,
                options_json TEXT NOT NULL DEFAULT '[]',
                answer TEXT NOT NULL,
                analysis TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'medium',
                chapter TEXT NOT NULL DEFAULT '',
                citations_json TEXT NOT NULL DEFAULT '[]',
                scenario TEXT NOT NULL DEFAULT '',
                as_of TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                origin TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_question_bank_course
                ON question_bank_questions(course_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS question_bank_papers (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_question_papers_course
                ON question_bank_papers(course_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS question_bank_paper_items (
                paper_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                score REAL NOT NULL DEFAULT 1,
                PRIMARY KEY (paper_id, question_id),
                FOREIGN KEY(paper_id) REFERENCES question_bank_papers(id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES question_bank_questions(id) ON DELETE RESTRICT
            );
            """
        )
        self._conn.commit()

    @staticmethod
    def _question(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        result = dict(row)
        result["options"] = json.loads(result.pop("options_json") or "[]")
        result["citations"] = json.loads(result.pop("citations_json") or "[]")
        return result

    def create_question(self, payload: dict) -> dict:
        qid, now = _id("q"), _now()
        self._conn.execute(
            """INSERT INTO question_bank_questions
            (id,course_id,stem,question_type,options_json,answer,analysis,difficulty,chapter,
             citations_json,scenario,as_of,status,origin,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                qid, payload["course_id"], payload["stem"], payload["question_type"],
                json.dumps(payload.get("options") or [], ensure_ascii=False), payload["answer"],
                payload.get("analysis") or "", payload.get("difficulty") or "medium",
                payload.get("chapter") or "", json.dumps(payload.get("citations") or [], ensure_ascii=False),
                payload.get("scenario") or "", payload.get("as_of") or "",
                payload.get("status") or "draft", payload.get("origin") or "manual", now, now,
            ),
        )
        self._conn.commit()
        return self.get_question(qid, payload["course_id"]) or {}

    def get_question(self, question_id: str, course_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM question_bank_questions WHERE id=? AND course_id=?",
            (question_id, course_id),
        ).fetchone()
        return self._question(row)

    def require_question(self, question_id: str, course_id: str) -> dict:
        question = self.get_question(question_id, course_id)
        if question is None:
            raise NotFoundException("题目不存在或不属于当前课程")
        return question

    def list_questions(
        self, course_id: str, *, question_type: str | None = None,
        difficulty: str | None = None, chapter: str | None = None, status: str | None = None,
    ) -> list[dict]:
        sql, values = ["SELECT * FROM question_bank_questions WHERE course_id=?"], [course_id]
        for col, value in (("question_type", question_type), ("difficulty", difficulty), ("chapter", chapter), ("status", status)):
            if value:
                sql.append(f"AND {col}=?")
                values.append(value)
        sql.append("ORDER BY CASE status WHEN 'reviewed' THEN 0 ELSE 1 END, updated_at DESC, id DESC")
        rows = self._conn.execute(" ".join(sql), values).fetchall()
        return [self._question(row) for row in rows]

    def update_question(self, question_id: str, course_id: str, updates: dict) -> dict:
        self.require_question(question_id, course_id)
        allowed = {"stem", "question_type", "options", "answer", "analysis", "difficulty", "chapter", "status"}
        fields: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in allowed or value is None:
                continue
            column = "options_json" if key == "options" else key
            fields.append(f"{column}=?")
            values.append(json.dumps(value, ensure_ascii=False) if key == "options" else value)
        if not fields:
            return self.require_question(question_id, course_id)
        fields.append("updated_at=?")
        values.extend([_now(), question_id, course_id])
        self._conn.execute(
            f"UPDATE question_bank_questions SET {', '.join(fields)} WHERE id=? AND course_id=?", values
        )
        self._conn.commit()
        return self.require_question(question_id, course_id)

    def delete_question(self, question_id: str, course_id: str) -> bool:
        self.require_question(question_id, course_id)
        try:
            cur = self._conn.execute(
                "DELETE FROM question_bank_questions WHERE id=? AND course_id=?", (question_id, course_id)
            )
            self._conn.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError as exc:
            raise BadRequestException("题目已被试卷引用，请先从试卷中移除") from exc

    def create_paper(self, course_id: str, title: str, description: str, items: list[dict]) -> dict:
        if len({item["question_id"] for item in items}) != len(items):
            raise BadRequestException("同一份试卷不能重复加入同一道题")
        for item in items:
            self.require_question(item["question_id"], course_id)
        paper_id, now = _id("paper"), _now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO question_bank_papers(id,course_id,title,description,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (paper_id, course_id, title, description, now, now),
            )
            self._conn.executemany(
                "INSERT INTO question_bank_paper_items(paper_id,question_id,position,score) VALUES(?,?,?,?)",
                [(paper_id, item["question_id"], index, item.get("score", 1)) for index, item in enumerate(items, 1)],
            )
        return self.get_paper(paper_id, course_id) or {}

    def list_papers(self, course_id: str) -> list[dict]:
        rows = self._conn.execute(
            """SELECT p.*, COUNT(i.question_id) AS question_count, COALESCE(SUM(i.score), 0) AS total_score
            FROM question_bank_papers p LEFT JOIN question_bank_paper_items i ON p.id=i.paper_id
            WHERE p.course_id=? GROUP BY p.id ORDER BY p.updated_at DESC, p.id DESC""", (course_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_paper(self, paper_id: str, course_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM question_bank_papers WHERE id=? AND course_id=?", (paper_id, course_id)
        ).fetchone()
        if row is None:
            return None
        paper = dict(row)
        items = self._conn.execute(
            """SELECT i.position, i.score, q.* FROM question_bank_paper_items i
            JOIN question_bank_questions q ON q.id=i.question_id
            WHERE i.paper_id=? AND q.course_id=? ORDER BY i.position""", (paper_id, course_id)
        ).fetchall()
        paper["items"] = [{"position": item["position"], "score": item["score"], "question": self._question(item)} for item in items]
        paper["question_count"] = len(paper["items"])
        paper["total_score"] = sum(float(item["score"]) for item in paper["items"])
        return paper

    def delete_paper(self, paper_id: str, course_id: str) -> bool:
        if self.get_paper(paper_id, course_id) is None:
            raise NotFoundException("试卷不存在或不属于当前课程")
        cur = self._conn.execute(
            "DELETE FROM question_bank_papers WHERE id=? AND course_id=?", (paper_id, course_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()
