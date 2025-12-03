# database/db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path(__file__).resolve().parent / "sales.db"


def get_connection() -> sqlite3.Connection:
    """
    SQLiteのConnectionオブジェクトを返すヘルパー関数。
    必ず row_factory を dict 風にしておく。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    アプリ起動時に1回だけ実行する用。
    slips テーブルが無ければ作成する。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS slips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slip_date TEXT NOT NULL,
            table_name TEXT,
            people INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def insert_slip(slip_date: str, table_name: str, people: int, amount: int, created_at: str) -> None:
    """
    1件の伝票データを登録する。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO slips (slip_date, table_name, people, amount, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (slip_date, table_name, people, amount, created_at),
    )

    conn.commit()
    conn.close()


def get_slips_by_date(slip_date: str) -> List[Dict[str, Any]]:
    """
    指定した日付（YYYY-MM-DD）の伝票一覧を返す。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, slip_date, table_name, people, amount, created_at
        FROM slips
        WHERE slip_date = ?
        ORDER BY id ASC
        """,
        (slip_date,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recent_dates(limit: int = 7) -> List[str]:
    """
    slipsテーブルから、直近の営業日（伝票のある日付）を新しい順に取得する。
    例: ["2025-12-03", "2025-12-02", ...]
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT slip_date
        FROM slips
        ORDER BY slip_date DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]