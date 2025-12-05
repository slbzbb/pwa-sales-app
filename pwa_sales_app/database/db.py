# database/db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "sales.db"


# ===========================
# 基础: 连接 & 初始化
# ===========================
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    整个应用只需要执行一次（如在 run.py 启动时），
    用来创建所有需要的表。
    """
    conn = get_connection()
    cur = conn.cursor()

    # 单据表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS slips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slip_date TEXT NOT NULL,         -- 营业日: YYYY-MM-DD
            table_name TEXT,                 -- 桌号
            people INTEGER NOT NULL,         -- 人数
            amount INTEGER NOT NULL,         -- 金额
            payment_method TEXT,             -- 支付方式: cash / credit / wechat / paypay / alipay
            created_at TEXT NOT NULL         -- 记录时间: YYYY-MM-DD HH:MM
        )
        """
    )

    # 食物统计表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS food_sales (
            business_date TEXT PRIMARY KEY,  -- 营业日
            steak INTEGER DEFAULT 0,
            beef_cube INTEGER DEFAULT 0,
            beef_skewer INTEGER DEFAULT 0,
            burger INTEGER DEFAULT 0,
            sandwich INTEGER DEFAULT 0,
            shrimp INTEGER DEFAULT 0
        )
        """
    )

    # 负责人时间段表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_date TEXT NOT NULL,
            start_time TEXT NOT NULL,        -- HH:MM
            end_time TEXT NOT NULL,          -- HH:MM
            staff_name TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


# ===========================
# slips: 单据相关
# ===========================
def insert_slip(
    slip_date: str,
    table_name: Optional[str],
    people: int,
    amount: int,
    payment_method: str,
    created_at: str,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO slips (slip_date, table_name, people, amount, payment_method, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (slip_date, table_name, people, amount, payment_method, created_at),
    )
    conn.commit()
    conn.close()


def update_slip(
    slip_id: int,
    table_name: Optional[str],
    people: int,
    amount: int,
    payment_method: str,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE slips
        SET table_name = ?, people = ?, amount = ?, payment_method = ?
        WHERE id = ?
        """,
        (table_name, people, amount, payment_method, slip_id),
    )
    conn.commit()
    conn.close()


def delete_slip(slip_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM slips WHERE id = ?", (slip_id,))
    conn.commit()
    conn.close()


def get_slip(slip_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM slips
        WHERE id = ?
        """,
        (slip_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_slips_by_date(slip_date: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM slips
        WHERE slip_date = ?
        ORDER BY id ASC
        """,
        (slip_date,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- 新增函数：用于 CSV 导出 ---
def get_all_slips() -> List[Dict[str, Any]]:
    """
    获取 slips 表中的所有单据，按日期和 ID 排序
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM slips
        ORDER BY slip_date DESC, id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
# ------------------------------


def get_recent_dates(limit: int = 7) -> List[str]:
    """
    最近有单据的营业日（新的在前）
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
    return [r["slip_date"] for r in rows]


def get_payment_summary_by_date(slip_date: str) -> List[Dict[str, Any]]:
    """
    某营业日的支付方式汇总 (用于首页“按支付方式统计”)
    返回: [{'method': 'cash', 'label': '现金', 'amount': 1000}, ...]
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT payment_method, SUM(amount) AS total_amount
        FROM slips
        WHERE slip_date = ?
        GROUP BY payment_method
        """,
        (slip_date,),
    )
    rows = cur.fetchall()
    conn.close()

    # 统一所有支付方式，没记录的用 0
    label_map = {
        "cash": "现金",
        "credit": "クレジットカード",
        "wechat": "WeChat Pay",
        "paypay": "PayPay",
        "alipay": "支付宝",
    }
    result_map = {r["payment_method"]: r["total_amount"] for r in rows}

    result: List[Dict[str, Any]] = []
    for key in ["cash", "credit", "wechat", "paypay", "alipay"]:
        result.append(
            {
                "method": key,
                "label": label_map[key],
                "amount": int(result_map.get(key, 0) or 0),
            }
        )
    return result


# ===========================
# food_sales: 食物贩卖
# ===========================
def get_food_sales(business_date: str) -> Dict[str, int]:
    """
    某一天的食物统计，没有记录时全部 0。
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT steak, beef_cube, beef_skewer, burger, sandwich, shrimp
        FROM food_sales
        WHERE business_date = ?
        """,
        (business_date,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "steak": 0,
            "beef_cube": 0,
            "beef_skewer": 0,
            "burger": 0,
            "sandwich": 0,
            "shrimp": 0,
        }

    return {
        "steak": row["steak"] or 0,
        "beef_cube": row["beef_cube"] or 0,
        "beef_skewer": row["beef_skewer"] or 0,
        "burger": row["burger"] or 0,
        "sandwich": row["sandwich"] or 0,
        "shrimp": row["shrimp"] or 0,
    }


def upsert_food_sales(
    business_date: str,
    steak: int,
    beef_cube: int,
    beef_skewer: int,
    burger: int,
    sandwich: int,
    shrimp: int,
) -> None:
    """
    有则更新，无则插入。
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO food_sales (
            business_date, steak, beef_cube, beef_skewer, burger, sandwich, shrimp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(business_date) DO UPDATE SET
            steak = excluded.steak,
            beef_cube = excluded.beef_cube,
            beef_skewer = excluded.beef_skewer,
            burger = excluded.burger,
            sandwich = excluded.sandwich,
            shrimp = excluded.shrimp
        """,
        (business_date, steak, beef_cube, beef_skewer, burger, sandwich, shrimp),
    )
    conn.commit()
    conn.close()


def get_food_totals_last_days(limit: int = 7) -> Dict[str, int]:
    """
    最近 limit 天内，各食物的累计总份数。
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            SUM(steak)        AS steak,
            SUM(beef_cube)    AS beef_cube,
            SUM(beef_skewer)  AS beef_skewer,
            SUM(burger)       AS burger,
            SUM(sandwich)     AS sandwich,
            SUM(shrimp)       AS shrimp
        FROM food_sales
        WHERE business_date IN (
            SELECT business_date
            FROM food_sales
            ORDER BY business_date DESC
            LIMIT ?
        )
        """,
        (limit,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "steak": 0,
            "beef_cube": 0,
            "beef_skewer": 0,
            "burger": 0,
            "sandwich": 0,
            "shrimp": 0,
        }

    return {
        "steak": row["steak"] or 0,
        "beef_cube": row["beef_cube"] or 0,
        "beef_skewer": row["beef_skewer"] or 0,
        "burger": row["burger"] or 0,
        "sandwich": row["sandwich"] or 0,
        "shrimp": row["shrimp"] or 0,
    }


# ===========================
# segments: 负责人时间段
# ===========================
def insert_segment(business_date: str, start_time: str, end_time: str, staff_name: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO segments (business_date, start_time, end_time, staff_name)
        VALUES (?, ?, ?, ?)
        """,
        (business_date, start_time, end_time, staff_name),
    )
    conn.commit()
    conn.close()


def get_segments_by_date(business_date: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, business_date, start_time, end_time, staff_name
        FROM segments
        WHERE business_date = ?
        ORDER BY start_time ASC
        """,
        (business_date,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_segment(segment_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, business_date, start_time, end_time, staff_name
        FROM segments
        WHERE id = ?
        """,
        (segment_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_segment(segment_id: int, start_time: str, end_time: str, staff_name: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE segments
        SET start_time = ?, end_time = ?, staff_name = ?
        WHERE id = ?
        """,
        (start_time, end_time, staff_name, segment_id),
    )
    conn.commit()
    conn.close()


def delete_segment(segment_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM segments WHERE id = ?", (segment_id,))
    conn.commit()
    conn.close()


# ===========================
# Performance: 趋势分析
# ===========================
def get_daily_sales_and_customers(limit: int = 7) -> List[Dict[str, Any]]:
    """
    最近 limit 天 每日的营业额 & 客数。
    返回时按日期升序（方便画折线图）。
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT slip_date,
               SUM(amount) AS total_sales,
               SUM(people) AS total_customers
        FROM slips
        GROUP BY slip_date
        ORDER BY slip_date DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    rows.reverse()
    return rows


# ===========================
# 清空所有业务数据（危险操作）
# ===========================
def clear_all_data() -> None:
    """
    删除所有 slips / food_sales / segments 的记录，但不删表结构。
    """
    conn = get_connection()
    cur = conn.cursor()

    # 按顺序清空
    cur.execute("DELETE FROM slips")
    cur.execute("DELETE FROM food_sales")
    cur.execute("DELETE FROM segments")

    conn.commit()

    # 可选：释放空间
    cur.execute("VACUUM")
    conn.commit()
    conn.close()