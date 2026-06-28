import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "quiz_history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT    NOT NULL,
                questions_json  TEXT    NOT NULL,
                answer_key_json TEXT    NOT NULL,
                created_at      TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id      INTEGER NOT NULL REFERENCES quizzes(id),
                answers_json TEXT    NOT NULL,
                score        INTEGER NOT NULL,
                total        INTEGER NOT NULL,
                submitted_at TEXT    NOT NULL
            )
        """)


def save_quiz(topic: str, questions: list, answer_key: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO quizzes (topic, questions_json, answer_key_json, created_at) VALUES (?, ?, ?, ?)",
            (topic, json.dumps(questions), json.dumps(answer_key), datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_quiz(quiz_id: int) -> tuple[list, dict] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT questions_json, answer_key_json FROM quizzes WHERE id = ?",
            (quiz_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["questions_json"]), json.loads(row["answer_key_json"])


def save_attempt(quiz_id: int, answers: dict, score: int, total: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO attempts (quiz_id, answers_json, score, total, submitted_at) VALUES (?, ?, ?, ?, ?)",
            (quiz_id, json.dumps(answers), score, total, datetime.utcnow().isoformat()),
        )


def list_history() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("""
            SELECT q.id, q.topic, q.created_at,
                   a.score, a.total, a.submitted_at
            FROM quizzes q
            LEFT JOIN attempts a
                ON a.quiz_id = q.id
                AND a.submitted_at = (
                    SELECT MAX(submitted_at) FROM attempts WHERE quiz_id = q.id
                )
            ORDER BY q.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


_init_db()
