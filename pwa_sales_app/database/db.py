# database/db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

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
    slips テーブルなどが無ければ作成する。
    """
    conn = get_connection()
    cur = conn.cursor()

    # 伝票テーブル
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

    # 1日の中で複数の時間帯を担当する人を管理するテーブル
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slip_date  TEXT NOT NULL,
            start_time TEXT NOT NULL,   -- "HH:MM"
            end_time   TEXT NOT NULL,   -- "HH:MM"
            staff_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def insert_slip(
    slip_date: str,
    table_name: Optional[str],
    people: int,
    amount: int,
    created_at: str,
) -> None:
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

    return [row["slip_date"] for row in rows]


# ===== 伝票1件の取得・更新・削除 =====


def get_slip_by_id(slip_id: int) -> Optional[Dict[str, Any]]:
    """
    id で伝票1件を取得する。存在しなければ None。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, slip_date, table_name, people, amount, created_at
        FROM slips
        WHERE id = ?
        """,
        (slip_id,),
    )

    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    return dict(row)


def update_slip(
    slip_id: int,
    table_name: Optional[str],
    people: int,
    amount: int,
) -> None:
    """
    id 指定で table_name, people, amount を更新する。
    日付や作成時間はそのまま。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE slips
        SET table_name = ?, people = ?, amount = ?
        WHERE id = ?
        """,
        (table_name, people, amount, slip_id),
    )

    conn.commit()
    conn.close()


def delete_slip(slip_id: int) -> None:
    """
    id 指定で伝票を削除する。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM slips WHERE id = ?", (slip_id,))

    conn.commit()
    conn.close()


# ===== 日内の担当時間帯（segments） =====


def get_staff_segments_by_date(slip_date: str) -> List[Dict[str, Any]]:
    """
    指定日の担当時間帯一覧を返す。
    例: 18:00-21:00 张三 / 21:00-24:00 李四
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, slip_date, start_time, end_time, staff_name, created_at
        FROM staff_segments
        WHERE slip_date = ?
        ORDER BY start_time ASC, id ASC
        """,
        (slip_date,),
    )

    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_staff_segment(
    slip_date: str,
    start_time: str,
    end_time: str,
    staff_name: str,
    created_at: str,
) -> None:
    """
    指定日の「担当時間帯」を1件登録する。
    start_time / end_time は "HH:MM" 形式。
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO staff_segments (slip_date, start_time, end_time, staff_name, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (slip_date, start_time, end_time, staff_name, created_at),
    )

    conn.commit()
    conn.close()