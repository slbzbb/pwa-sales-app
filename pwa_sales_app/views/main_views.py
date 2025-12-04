# views/main_views.py
from datetime import datetime, date
from typing import Dict, List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
)

from database.db import (
    get_slips_by_date,
    get_slip,
    insert_slip,
    update_slip,
    delete_slip,
    get_connection,          # 暂时没用到，但留下也没问题
    get_recent_dates,
    get_payment_summary_by_date,
    get_food_sales,
    upsert_food_sales,
    get_daily_sales_and_customers,
    get_food_totals_last_days,
    insert_segment,
    get_segments_by_date,
    get_segment,
    update_segment,
    delete_segment,
)

main_bp = Blueprint("main", __name__)


# ===========================
# 共用：首页统计
# ===========================
def calculate_summary(slips: List[Dict]) -> Dict[str, int]:
    total_sales = sum(slip["amount"] for slip in slips)
    total_customers = sum(slip["people"] for slip in slips)
    total_tables = len(slips)

    avg_per_customer = int(total_sales / total_customers) if total_customers else 0

    return {
        "total_sales": total_sales,
        "total_customers": total_customers,
        "total_tables": total_tables,
        "avg_per_customer": avg_per_customer,
    }


# ===========================
# 首页
# ===========================
@main_bp.route("/")
def index():
    # 营业日：query string 中没有就用今天
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")

    slips = get_slips_by_date(business_date)
    summary = calculate_summary(slips)

    # 时间字段只取 HH:MM
    for slip in slips:
        created_at = slip["created_at"]
        slip["time"] = created_at[11:16] if created_at and len(created_at) >= 16 else ""

    # 支付方式汇总
    payment_summary = get_payment_summary_by_date(business_date)

    # 食物贩卖
    food_raw = get_food_sales(business_date)
    food_items = [
        {"key": "steak",       "label": "牛排",   "quantity": food_raw["steak"]},
        {"key": "beef_cube",   "label": "牛肉粒", "quantity": food_raw["beef_cube"]},
        {"key": "beef_skewer", "label": "牛肉串", "quantity": food_raw["beef_skewer"]},
        {"key": "burger",      "label": "汉堡",   "quantity": food_raw["burger"]},
        {"key": "sandwich",    "label": "三明治", "quantity": food_raw["sandwich"]},
        {"key": "shrimp",      "label": "虾",     "quantity": food_raw["shrimp"]},
    ]

    # 负责人时间段
    segments = get_segments_by_date(business_date)

    return render_template(
        "index.html",
        active_tab="home",
        business_date=business_date,
        summary=summary,
        slips=slips,
        payment_summary=payment_summary,
        food_items=food_items,
        segments=segments,
    )


# ===========================
# 新建单据
# ===========================
@main_bp.route("/input", methods=["GET", "POST"])
def input_slip():
    # 从 query string 接收营业日（从首页“新建单据”点过来）
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method") or "cash"

        table_name: Optional[str] = table_raw or None
        try:
            people = int(people_raw)
        except ValueError:
            people = 0
        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 0

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        insert_slip(
            slip_date=business_date,
            table_name=table_name,
            people=people,
            amount=amount,
            payment_method=payment_method,
            created_at=now_str,
        )

        return redirect(url_for("main.index", date=business_date))

    # GET: 显示表单
    return render_template(
        "input.html",
        active_tab="input",
        business_date=business_date,
    )


# ===========================
# 编辑 / 删除 单据
# ===========================
@main_bp.route("/slips/<int:slip_id>/edit", methods=["GET", "POST"])
def edit_slip_view(slip_id: int):
    slip = get_slip(slip_id)
    if not slip:
        return redirect(url_for("main.index"))

    business_date = slip["slip_date"]

    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = request.form.get("payment_method") or "cash"

        table_name: Optional[str] = table_raw or None
        try:
            people = int(people_raw)
        except ValueError:
            people = 0
        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 0

        # 由于您的编辑表单（edit.html）没有提供 payment_method 字段，
        # 这里的 update_slip 暂时无法更新支付方式，但为了保持功能完整性，
        # 如果需要更新 payment_method，需要修改 edit.html 模板。
        # 暂时使用一个默认值（不影响核心业务逻辑）
        update_slip(
            slip_id=slip_id,
            table_name=table_name,
            people=people,
            amount=amount,
            # 这里的 payment_method 如果没从表单来，可能导致问题。
            # 暂时保持现有逻辑，但请注意 edit.html 中缺少 payment_method 字段。
            payment_method=slip["payment_method"],
        )

        return redirect(url_for("main.index", date=business_date))

    # GET
    return render_template(
        "edit.html",   # <--- 修复点 1：将 "edit_slip.html" 改为 "edit.html"
        slip=slip,
        active_tab="home",
    )


@main_bp.route("/slips/<int:slip_id>/delete", methods=["POST"])
def delete_slip_view(slip_id: int):
    slip = get_slip(slip_id)
    if slip:
        business_date = slip["slip_date"]
        delete_slip(slip_id)
        return redirect(url_for("main.index", date=business_date))
    return redirect(url_for("main.index"))


# ===========================
# 日报（某一天的详细报表）
# ===========================
@main_bp.route("/report")
def report():
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")
    slips = get_slips_by_date(business_date)
    summary = calculate_summary(slips)
    payment_summary = get_payment_summary_by_date(business_date)
    food_raw = get_food_sales(business_date)

    food_items = [
        {"label": "牛排",   "quantity": food_raw["steak"]},
        {"label": "牛肉粒", "quantity": food_raw["beef_cube"]},
        {"label": "牛肉串", "quantity": food_raw["beef_skewer"]},
        {"label": "汉堡",   "quantity": food_raw["burger"]},
        {"label": "三明治", "quantity": food_raw["sandwich"]},
        {"label": "虾",     "quantity": food_raw["shrimp"]},
    ]
    
    # 负责人时间段
    segments = get_segments_by_date(business_date)
    
    # 最近有记录的营业日
    recent_dates = get_recent_dates(limit=7)

    return render_template(
        "report.html",
        active_tab="report",
        slip_date=business_date, # report.html 使用 slip_date
        summary=summary,
        slips=slips,
        payment_summary=payment_summary,
        food_items=food_items,
        segments=segments,
        recent_dates=recent_dates,
    )


# ===========================
# 食物贩卖编辑
# ===========================
@main_bp.route("/food/edit", methods=["GET", "POST"])
def edit_food_sales():
    business_date = (
        request.args.get("date")
        or request.form.get("business_date")
        or date.today().strftime("%Y-%m-%d")
    )

    if request.method == "POST":
        def parse_int(name: str) -> int:
            raw = request.form.get(name, "").strip()
            try:
                return int(raw)
            except ValueError:
                return 0

        steak = parse_int("steak")
        beef_cube = parse_int("beef_cube")
        beef_skewer = parse_int("beef_skewer")
        burger = parse_int("burger")
        sandwich = parse_int("sandwich")
        shrimp = parse_int("shrimp")

        upsert_food_sales(
            business_date,
            steak,
            beef_cube,
            beef_skewer,
            burger,
            sandwich,
            shrimp,
        )
        return redirect(url_for("main.index", date=business_date))

    # GET
    food_raw = get_food_sales(business_date)
    items = [
        {"key": "steak",       "label": "牛排",   "quantity": food_raw["steak"]},
        {"key": "beef_cube",   "label": "牛肉粒", "quantity": food_raw["beef_cube"]},
        {"key": "beef_skewer", "label": "牛肉串", "quantity": food_raw["beef_skewer"]},
        {"key": "burger",      "label": "汉堡",   "quantity": food_raw["burger"]},
        {"key": "sandwich",    "label": "三明治", "quantity": food_raw["sandwich"]},
        {"key": "shrimp",      "label": "虾",     "quantity": food_raw["shrimp"]},
    ]

    return render_template(
        "food.html",   # <--- 修复点 2：将 "edit_food_sales.html" 改为 "food.html"
        active_tab="home",
        business_date=business_date,
        items=items,
    )


# ===========================
# 负责人时间段：新增 / 编辑 / 删除
# ===========================
@main_bp.route("/segments/add_today", methods=["POST"])
def add_today_segment():
    business_date = request.form.get("business_date") or date.today().strftime("%Y-%m-%d")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    staff_name = request.form.get("staff_name", "").strip()

    if start_time and end_time and staff_name:
        insert_segment(business_date, start_time, end_time, staff_name)

    return redirect(url_for("main.index", date=business_date))


@main_bp.route("/segments/<int:segment_id>/edit", methods=["GET", "POST"])
def edit_segment_view(segment_id: int):
    seg = get_segment(segment_id)
    if not seg:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        staff_name = request.form.get("staff_name", "").strip()
        update_segment(segment_id, start_time, end_time, staff_name)
        return redirect(url_for("main.index", date=seg["business_date"]))

    # 注意：edit_segment.html 中 action="{{ url_for('main.edit_segment', ... ) }}"
    # 如果没有修改 edit_segment.html，这里可能还会报错。建议检查该文件中的路由名称。
    return render_template(
        "edit_segment.html",
        segment=seg,
        active_tab="home",
    )


@main_bp.route("/segments/<int:segment_id>/delete", methods=["POST"])
def delete_segment_view(segment_id: int):
    seg = get_segment(segment_id)
    if seg:
        delete_segment(segment_id)
        return redirect(url_for("main.index", date=seg["business_date"]))
    return redirect(url_for("main.index"))


# ===========================
# Performance 业绩分析
# ===========================
@main_bp.route("/performance")
def performance():
    daily_stats = get_daily_sales_and_customers(limit=7)

    line_labels = [d["slip_date"] for d in daily_stats]
    line_sales = [d["total_sales"] for d in daily_stats]
    line_customers = [d["total_customers"] for d in daily_stats]

    food_totals = get_food_totals_last_days(limit=7)
    bar_labels = ["牛排", "牛肉粒", "牛肉串", "汉堡", "三明治", "虾"]
    bar_values = [
        food_totals["steak"],
        food_totals["beef_cube"],
        food_totals["beef_skewer"],
        food_totals["burger"],
        food_totals["sandwich"],
        food_totals["shrimp"],
    ]

    return render_template(
        "performance.html",
        active_tab="performance",
        line_labels=line_labels,
        line_sales=line_sales,
        line_customers=line_customers,
        bar_labels=bar_labels,
        bar_values=bar_values,
    )


# ===========================
# 设置
# ===========================
@main_bp.route("/settings")
def settings():
    return render_template("settings.html", active_tab="settings")