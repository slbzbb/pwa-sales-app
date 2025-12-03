# views/main_views.py
from datetime import datetime, date
from typing import Dict, List

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
)

from database.db import get_slips_by_date, insert_slip, get_connection

main_bp = Blueprint("main", __name__)


def calculate_summary(slips: List[Dict]) -> Dict[str, int]:
    """
    slips のリストからトップ画面用の集計値を計算する。
    """
    total_sales = sum(slip["amount"] for slip in slips)
    total_customers = sum(slip["people"] for slip in slips)
    total_tables = len(slips)

    if total_customers > 0:
        avg_per_customer = int(total_sales / total_customers)
    else:
        avg_per_customer = 0

    summary = {
        "total_sales": total_sales,
        "total_customers": total_customers,
        "total_tables": total_tables,
        "avg_per_customer": avg_per_customer,
    }
    return summary


@main_bp.route("/")
def index():
    # 今日の日付文字列
    today_str = date.today().strftime("%Y-%m-%d")

    # DBから今日の伝票を取得
    slips = get_slips_by_date(today_str)

    # 集計を計算
    summary = calculate_summary(slips)

    # 時刻だけ抜き出し（created_at は "YYYY-MM-DD HH:MM" の想定）
    for slip in slips:
        created_at: str = slip["created_at"]
        slip["time"] = created_at[11:16]  # "HH:MM"

    return render_template("index.html", summary=summary, slips=slips)


@main_bp.route("/input", methods=["GET", "POST"])
def input_slip():
    """
    新建单据画面。
    - GET: 表单画面を表示
    - POST: データをDBに保存してトップへリダイレクト
    """
    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()

        table_name = table_raw or None

        try:
            people = int(people_raw)
        except ValueError:
            people = 0

        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 0

        # 今日の日付と現在時刻
        today_str = date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # DBに保存
        insert_slip(
            slip_date=today_str,
            table_name=table_name,
            people=people,
            amount=amount,
            created_at=now_str,
        )

        return redirect(url_for("main.index"))

    # GET
    return render_template("input.html")


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


@main_bp.route("/report")
def report():
    """
    日報画面。
    ?date=YYYY-MM-DD で任意の日付を指定可能。
    未指定の場合は「今日」を対象とする。
    """
    # 1. URL パラメータ ?date=...
    date_str = request.args.get("date")

    # 2. 指定されていなければ今日
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")

    # 3. 日付フォーマットの簡易チェック
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        date_str = date.today().strftime("%Y-%m-%d")

    # 4. 指定日の伝票一覧
    slips = get_slips_by_date(date_str)

    for slip in slips:
        created_at: str = slip["created_at"]
        slip["time"] = created_at[11:16]

    # 5. 集計
    summary = calculate_summary(slips)

    # 6. 直近の日付リスト
    recent_dates = get_recent_dates(limit=7)

    return render_template(
        "report.html",
        selected_date=date_str,
        summary=summary,
        slips=slips,
        recent_dates=recent_dates,
    )


@main_bp.route("/settings")
def settings():
    return render_template("settings.html")