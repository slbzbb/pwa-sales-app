# views/main_views.py
from datetime import datetime, time, timedelta
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

# ---------------------------
# 食物列表
# ---------------------------
FOOD_ITEMS: Dict[str, str] = {
    "steak": "牛排",
    "beef_cube": "牛肉粒",
    "beef_skewer": "牛肉串",
    "burger": "汉堡",
    "sandwich": "三明治",
    "shrimp": "虾",
}

# ---------------------------
# 营业日逻辑（默认 + 可覆盖）
# ---------------------------
def get_default_business_date() -> str:
    """
    默认营业日：
    - 凌晨 00:00 - 05:00 → 算昨天
    - 其他时间 → 算今天
    """
    now = datetime.now()
    if now.time() < time(5, 0):
        biz = now.date() - timedelta(days=1)
    else:
        biz = now.date()
    return biz.strftime("%Y-%m-%d")


def get_business_date_from_request() -> str:
    """
    优先使用用户选择的营业日。
    POST: form['business_date']
    GET : args['date']
    """
    form_date = request.form.get("business_date")
    query_date = request.args.get("date")

    if form_date:
        return form_date
    if query_date:
        return query_date
    return get_default_business_date()

# ---------------------------
# 集计相关
# ---------------------------
def calculate_summary(slips: List[Dict]) -> Dict[str, int]:
    total_sales = sum(s["amount"] for s in slips)
    total_customers = sum(s["people"] for s in slips)
    total_tables = len(slips)

    avg_per_customer = int(total_sales / total_customers) if total_customers else 0

    return {
        "total_sales": total_sales,
        "total_customers": total_customers,
        "total_tables": total_tables,
        "avg_per_customer": avg_per_customer,
    }


def calculate_payment_totals(slips: List[Dict]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for s in slips:
        method = s.get("payment_method", "cash")
        amount = s.get("amount", 0)
        totals[method] = totals.get(method, 0) + amount
    return totals

# ---------------------------
# ① 首页 Dashboard（按营业日显示）
# ---------------------------
@main_bp.route("/")
def index():
    # 当前营业日：URL ?date= 优先，其次默认规则
    business_date = request.args.get("date") or get_default_business_date()

    slips = get_slips_by_date(business_date)

    # 提取时间 "YYYY-MM-DD HH:MM" → "HH:MM"
    for s in slips:
        s["time"] = s["created_at"][11:16]

    summary = calculate_summary(slips)

    # 该营业日内的负责人时间段
    segments = get_staff_segments_by_date(business_date)

    # 支付方式统计
    payment_labels = {
        "cash": "现金",
        "credit": "クレジットカード",
        "wechat": "WeChat Pay",
        "paypay": "PayPay",
        "alipay": "支付宝",
    }
    payment_totals = calculate_payment_totals(slips)
    payment_summary = [
        {"key": k, "label": v, "amount": payment_totals.get(k, 0)}
        for k, v in payment_labels.items()
    ]

    # 食物统计
    food_counts = get_food_sales_by_date(business_date)
    food_items = [
        {"key": key, "label": label, "quantity": food_counts.get(key, 0)}
        for key, label in FOOD_ITEMS.items()
    ]

    return render_template(
        "index.html",
        summary=summary,
        slips=slips,
        segments=segments,
        payment_summary=payment_summary,
        food_items=food_items,
        business_date=business_date,
        active_tab="home",
    )

# ---------------------------
# ② 新增“今日负责时间段”（按营业日）
# ---------------------------
@main_bp.route("/segments/today", methods=["POST"])
def add_today_segment():
    """
    首页「今日负责时间段」表单提交。
    """
    business_date = get_business_date_from_request()

    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    staff_name = request.form.get("staff_name", "").strip()

    # 简单防呆：有任何一项为空就直接返回首页
    if not (start_time and end_time and staff_name):
        return redirect(url_for("main.index", date=business_date))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    insert_staff_segment(
        slip_date=business_date,
        start_time=start_time,
        end_time=end_time,
        staff_name=staff_name,
        created_at=now,
    )

    return redirect(url_for("main.index", date=business_date))

# ---------------------------
# ③ 新建单据
# ---------------------------
@main_bp.route("/input", methods=["GET", "POST"])
def input_slip():
    if request.method == "POST":
        business_date = get_business_date_from_request()

        table_name = request.form.get("table", "").strip() or None
        people_raw = request.form.get("people", "0").strip()
        amount_raw = request.form.get("amount", "0").strip()
        payment_method = request.form.get("payment_method", "cash")

        try:
            people = int(people_raw)
        except ValueError:
            people = 0

        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        insert_slip(
            slip_date=business_date,
            table_name=table_name,
            people=people,
            amount=amount,
            created_at=now,
            payment_method=payment_method,
        )

        return redirect(url_for("main.index", date=business_date))

    business_date = request.args.get("date") or get_default_business_date()
    return render_template("input.html", business_date=business_date, active_tab="input")

# ---------------------------
# ④ 营业日报（报告页面）
# ---------------------------
@main_bp.route("/report")
def report():
    """
    指定营业日的日报：
    - URL /report?date=YYYY-MM-DD
    - 如果没给 date，就用默认营业日
    """
    slip_date = request.args.get("date") or get_default_business_date()

    slips = get_slips_by_date(slip_date)

    for s in slips:
        s["time"] = s["created_at"][11:16]

    summary = calculate_summary(slips)
    recent_dates = get_recent_dates()

    return render_template(
        "report.html",
        slip_date=slip_date,
        slips=slips,
        summary=summary,
        recent_dates=recent_dates,
        active_tab="report",
    )

# ---------------------------
# ⑤ 编辑单据（从日报/首页进入）
# ---------------------------
@main_bp.route("/slip/<int:slip_id>/edit", methods=["GET", "POST"])
def edit_slip(slip_id: int):
    slip = get_slip_by_id(slip_id)
    if slip is None:
        abort(404)

    slip_date = slip["slip_date"]

    if request.method == "POST":
        table_name = request.form.get("table", "").strip() or None
        people_raw = request.form.get("people", "0").strip()
        amount_raw = request.form.get("amount", "0").strip()

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

    return render_template(
        "edit.html",
        slip=slip,
        active_tab="report",
    )

# ---------------------------
# ⑥ 删除单据
# ---------------------------
@main_bp.route("/slip/<int:slip_id>/delete", methods=["POST"])
def delete_slip_route(slip_id: int):
    slip = get_slip_by_id(slip_id)
    if slip is None:
        abort(404)

    slip_date = slip["slip_date"]
    delete_slip(slip_id)

    return redirect(url_for("main.report", date=slip_date))

# ---------------------------
# ⑦ 当天食物数量修改（按营业日）
# ---------------------------
@main_bp.route("/food", methods=["GET", "POST"])
def edit_food_sales():
    if request.method == "POST":
        business_date = get_business_date_from_request()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        for key in FOOD_ITEMS.keys():
            raw = request.form.get(key, "").strip()
            try:
                qty = int(raw) if raw else 0
            except ValueError:
                qty = 0

            upsert_food_sale(
                slip_date=business_date,
                item_key=key,
                quantity=qty,
                updated_at=now,
            )

        return redirect(url_for("main.index", date=business_date))

    business_date = request.args.get("date") or get_default_business_date()

    food_counts = get_food_sales_by_date(business_date)
    items = [
        {"key": key, "label": label, "quantity": food_counts.get(key, 0)}
        for key, label in FOOD_ITEMS.items()
    ]

    return render_template(
        "food.html",
        items=items,
        business_date=business_date,
        active_tab="home",
    )

# ---------------------------
# ⑧ 设置页
# ---------------------------
@main_bp.route("/settings")
def settings():
    return render_template("settings.html", active_tab="settings")