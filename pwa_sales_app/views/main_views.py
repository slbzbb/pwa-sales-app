# views/main_views.py
from datetime import datetime, date
from typing import Dict, List

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
)

from database.db import (
    get_slips_by_date,
    insert_slip,
    get_recent_dates,
    get_slip_by_id,
    update_slip,
    delete_slip,
    get_staff_segments_by_date,
    insert_staff_segment,
    get_food_sales_by_date,
    upsert_food_sale,
)

main_bp = Blueprint("main", __name__)

# 食物品项定义
FOOD_ITEMS: Dict[str, str] = {
    "steak": "牛排",
    "beef_cube": "牛肉粒",
    "beef_skewer": "牛肉串",
    "burger": "汉堡",
    "sandwich": "三明治",
    "shrimp": "虾",
}


def calculate_summary(slips: List[Dict]) -> Dict[str, int]:
    """
    slips のリストから集計値を計算する（売上・客数・卓数・客単価）
    """
    total_sales = sum(slip["amount"] for slip in slips)
    total_customers = sum(slip["people"] for slip in slips)
    total_tables = len(slips)

    avg_per_customer = (
        int(total_sales / total_customers) if total_customers > 0 else 0
    )

    summary = {
        "total_sales": total_sales,
        "total_customers": total_customers,
        "total_tables": total_tables,
        "avg_per_customer": avg_per_customer,
    }
    return summary


def calculate_payment_totals(slips: List[Dict]) -> Dict[str, int]:
    """
    支払い方法ごとの売上合計を計算する。
    """
    totals: Dict[str, int] = {}

    for slip in slips:
        method = slip.get("payment_method", "cash")
        amount = slip.get("amount", 0)
        totals[method] = totals.get(method, 0) + amount

    return totals


# -----------------------------
# ① 首页（今天的 Dashboard）
# -----------------------------
@main_bp.route("/")
def index():
    today_str = date.today().strftime("%Y-%m-%d")

    slips = get_slips_by_date(today_str)
    summary = calculate_summary(slips)

    # created_at → HH:MM
    for slip in slips:
        created_at: str = slip["created_at"]
        slip["time"] = created_at[11:16]

    # 今日の担当時間帯
    segments = get_staff_segments_by_date(today_str)

    # 支払い方法ごとの集計
    payment_totals = calculate_payment_totals(slips)
    payment_labels = {
        "cash": "现金",
        "credit": "クレジットカード",
        "wechat": "WeChat Pay",
        "paypay": "PayPay",
        "alipay": "支付宝",
    }
    payment_summary = [
        {
            "key": key,
            "label": label,
            "amount": payment_totals.get(key, 0),
        }
        for key, label in payment_labels.items()
    ]

    # 今日食物贩卖统计
    food_counts = get_food_sales_by_date(today_str)
    food_items = [
        {
            "key": key,
            "label": label,
            "quantity": food_counts.get(key, 0),
        }
        for key, label in FOOD_ITEMS.items()
    ]

    return render_template(
        "index.html",
        summary=summary,
        slips=slips,
        segments=segments,
        payment_summary=payment_summary,
        food_items=food_items,
        active_tab="home",
    )


# -----------------------------
# ② 今日の担当時間帯を追加
# -----------------------------
@main_bp.route("/segments/today", methods=["POST"])
def add_today_segment():
    """
    ホーム画面の「今日の担当時間帯」フォームから送信される。
    例: 18:00-21:00 张三
    """
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    staff_name = request.form.get("staff_name", "").strip()

    if not (start_time and end_time and staff_name):
        return redirect(url_for("main.index"))

    today_str = date.today().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    insert_staff_segment(
        slip_date=today_str,
        start_time=start_time,
        end_time=end_time,
        staff_name=staff_name,
        created_at=now_str,
    )

    return redirect(url_for("main.index"))


# -----------------------------
# ③ 新建单据 input
# -----------------------------
@main_bp.route("/input", methods=["GET", "POST"])
def input_slip():
    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method", "cash")

        table_name = table_raw or None

        try:
            people = int(people_raw)
        except ValueError:
            people = 0

        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 0

        today_str = date.today().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        insert_slip(
            slip_date=today_str,
            table_name=table_name,
            people=people,
            amount=amount,
            created_at=now_str,
            payment_method=payment_method,
        )

        return redirect(url_for("main.index"))

    return render_template("input.html", active_tab="input")


# -----------------------------
# ④ 营业日报 report
# -----------------------------
@main_bp.route("/report")
def report():
    # URL 参数 date=YYYY-MM-DD
    query_date = request.args.get("date")

    if query_date:
        slip_date = query_date
    else:
        slip_date = date.today().strftime("%Y-%m-%d")

    slips = get_slips_by_date(slip_date)
    summary = calculate_summary(slips)

    for slip in slips:
        created_at: str = slip["created_at"]
        slip["time"] = created_at[11:16]

    recent_dates = get_recent_dates()

    return render_template(
        "report.html",
        slip_date=slip_date,
        slips=slips,
        summary=summary,
        recent_dates=recent_dates,
        active_tab="report",
    )


# -----------------------------
# ⑤ 编辑单据 edit
# -----------------------------
@main_bp.route("/slip/<int:slip_id>/edit", methods=["GET", "POST"])
def edit_slip(slip_id: int):
    slip = get_slip_by_id(slip_id)
    if slip is None:
        abort(404)

    slip_date = slip["slip_date"]

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

        update_slip(
            slip_id=slip_id,
            table_name=table_name,
            people=people,
            amount=amount,
        )

        return redirect(url_for("main.report", date=slip_date))

    return render_template("edit.html", slip=slip, active_tab="report")


# -----------------------------
# ⑥ 删除单据 delete
# -----------------------------
@main_bp.route("/slip/<int:slip_id>/delete", methods=["POST"])
def delete_slip_route(slip_id: int):
    slip = get_slip_by_id(slip_id)
    if slip is None:
        abort(404)

    slip_date = slip["slip_date"]
    delete_slip(slip_id)

    return redirect(url_for("main.report", date=slip_date))


# -----------------------------
# ⑦ 今日食物贩卖编辑页面
# -----------------------------
@main_bp.route("/food", methods=["GET", "POST"])
def edit_food_sales():
    """
    今日の食物贩卖数をまとめて入力・保存する画面。
    """
    today_str = date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        for key in FOOD_ITEMS.keys():
            raw = request.form.get(key, "").strip()
            try:
                qty = int(raw) if raw else 0
            except ValueError:
                qty = 0

            upsert_food_sale(
                slip_date=today_str,
                item_key=key,
                quantity=qty,
                updated_at=now_str,
            )

        return redirect(url_for("main.index"))

    # GET: 读取当前数据，填到表单里
    food_counts = get_food_sales_by_date(today_str)
    items = [
        {
            "key": key,
            "label": label,
            "quantity": food_counts.get(key, 0),
        }
        for key, label in FOOD_ITEMS.items()
    ]

    return render_template(
        "food.html",
        items=items,
        active_tab="home",
    )


# -----------------------------
# ⑧ 设置页面
# -----------------------------
@main_bp.route("/settings")
def settings():
    return render_template("settings.html", active_tab="settings")