# views/main_views.py
from datetime import datetime, date
from typing import Dict, List, Optional
import csv
from io import StringIO

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    make_response,
    session,
)

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from database.db import (
    get_slips_by_date,
    get_slip,
    insert_slip,
    update_slip,
    delete_slip,
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
    get_all_slips,
    create_user,
    get_user_by_username,
    clear_all_business_data,
)

main_bp = Blueprint("main", __name__)


# ===========================
# 登录保护装饰器
# ===========================
def login_required(view_func):
    """
    没有登录（session 里没有 user_id）就跳去登录页。
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            next_url = request.path
            return redirect(url_for("main.login", next=next_url))
        return view_func(*args, **kwargs)

    return wrapped


# ===========================
# 共用：统计用汇总函数
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
@login_required
def index():
    # 营业日：query string 中没有就用今天
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")

    slips = get_slips_by_date(business_date)
    summary = calculate_summary(slips)

    # 时间字段只取 HH:MM
    for slip in slips:
        created_at = slip.get("created_at")
        slip["time"] = created_at[11:16] if created_at and len(created_at) >= 16 else ""

    # 支付方式汇总
    payment_summary = get_payment_summary_by_date(business_date)

    # 食物贩卖
    food_raw = get_food_sales(business_date) or {}
    food_items = [
        {"key": "steak",       "label": "牛排",   "quantity": food_raw.get("steak", 0)},
        {"key": "beef_cube",   "label": "牛肉粒", "quantity": food_raw.get("beef_cube", 0)},
        {"key": "beef_skewer", "label": "牛肉串", "quantity": food_raw.get("beef_skewer", 0)},
        {"key": "burger",      "label": "汉堡",   "quantity": food_raw.get("burger", 0)},
        {"key": "sandwich",    "label": "三明治", "quantity": food_raw.get("sandwich", 0)},
        {"key": "shrimp",      "label": "虾",     "quantity": food_raw.get("shrimp", 0)},
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
@login_required
def input_slip():
    # 优先： query string -> form.hidden -> 今天
    business_date = (
        request.args.get("date")
        or request.form.get("business_date")
        or date.today().strftime("%Y-%m-%d")
    )

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
@login_required
def edit_slip_view(slip_id: int):
    slip = get_slip(slip_id)
    if not slip:
        return redirect(url_for("main.index"))

    business_date = slip["slip_date"]

    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        # 目前 edit 页面没有支付方式选项，先用原来的
        payment_method = slip["payment_method"]

        table_name: Optional[str] = table_raw or None
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
            payment_method=payment_method,
        )

        return redirect(url_for("main.index", date=business_date))

    # GET
    return render_template(
        "edit.html",
        slip=slip,
        active_tab="home",
    )


@main_bp.route("/slips/<int:slip_id>/delete", methods=["POST"])
@login_required
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
@login_required
def report():
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")
    slips = get_slips_by_date(business_date)

    # 给日报用的 time 字段
    for slip in slips:
        created_at = slip.get("created_at")
        slip["time"] = created_at[11:16] if created_at and len(created_at) >= 16 else ""

    summary = calculate_summary(slips)
    payment_summary = get_payment_summary_by_date(business_date)

    food_raw = get_food_sales(business_date) or {}
    food_items = [
        {"label": "牛排",   "quantity": food_raw.get("steak", 0)},
        {"label": "牛肉粒", "quantity": food_raw.get("beef_cube", 0)},
        {"label": "牛肉串", "quantity": food_raw.get("beef_skewer", 0)},
        {"label": "汉堡",   "quantity": food_raw.get("burger", 0)},
        {"label": "三明治", "quantity": food_raw.get("sandwich", 0)},
        {"label": "虾",     "quantity": food_raw.get("shrimp", 0)},
    ]

    segments = get_segments_by_date(business_date)
    recent_dates = get_recent_dates(limit=7)

    return render_template(
        "report.html",
        active_tab="report",
        slip_date=business_date,
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
@login_required
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
    food_raw = get_food_sales(business_date) or {}
    items = [
        {"key": "steak",       "label": "牛排",   "quantity": food_raw.get("steak", 0)},
        {"key": "beef_cube",   "label": "牛肉粒", "quantity": food_raw.get("beef_cube", 0)},
        {"key": "beef_skewer", "label": "牛肉串", "quantity": food_raw.get("beef_skewer", 0)},
        {"key": "burger",      "label": "汉堡",   "quantity": food_raw.get("burger", 0)},
        {"key": "sandwich",    "label": "三明治", "quantity": food_raw.get("sandwich", 0)},
        {"key": "shrimp",      "label": "虾",     "quantity": food_raw.get("shrimp", 0)},
    ]

    return render_template(
        "food.html",
        active_tab="home",
        business_date=business_date,
        items=items,
    )


# ===========================
# 负责人时间段：新增 / 编辑 / 删除
# ===========================
@main_bp.route("/segments/add", methods=["POST"])
@login_required
def add_segment():
    business_date = request.form.get("business_date") or date.today().strftime("%Y-%m-%d")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    staff_name = request.form.get("staff_name", "").strip()

    if start_time and end_time and staff_name:
        insert_segment(business_date, start_time, end_time, staff_name)

    return redirect(url_for("main.index", date=business_date))


@main_bp.route("/segments/<int:segment_id>/edit", methods=["GET", "POST"])
@login_required
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

    return render_template(
        "edit_segment.html",
        segment=seg,
        active_tab="home",
    )


@main_bp.route("/segments/<int:segment_id>/delete", methods=["POST"])
@login_required
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
@login_required
def performance():
    daily_stats = get_daily_sales_and_customers(limit=7)

    line_labels = [d["slip_date"] for d in daily_stats]
    line_sales = [d["total_sales"] for d in daily_stats]
    line_customers = [d["total_customers"] for d in daily_stats]

    food_totals = get_food_totals_last_days(limit=7)
    bar_labels = ["牛排", "牛肉粒", "牛肉串", "汉堡", "三明治", "虾"]
    bar_values = [
        food_totals.get("steak", 0),
        food_totals.get("beef_cube", 0),
        food_totals.get("beef_skewer", 0),
        food_totals.get("burger", 0),
        food_totals.get("sandwich", 0),
        food_totals.get("shrimp", 0),
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
@login_required
def settings():
    cleared = request.args.get("cleared") == "1"
    return render_template(
        "settings.html",
        active_tab="settings",
        cleared=cleared,
        username=session.get("username"),
    )


# ===========================
# 数据导出 CSV（明细）
# ===========================
@main_bp.route("/export/csv")
@login_required
def export_data_csv():
    """
    导出所有单据数据为 CSV 文件（明细）
    """
    slips_data = get_all_slips()

    # 1. CSV 头
    header = [
        "ID",
        "营业日",
        "桌号",
        "人数",
        "金额(日元)",
        "支付方式",
        "记录时间",
    ]

    rows = []
    payment_map = {
        "cash": "现金",
        "credit": "クレジットカード",
        "wechat": "WeChat Pay",
        "paypay": "PayPay",
        "alipay": "支付宝",
    }

    for slip in slips_data:
        payment_label = payment_map.get(slip["payment_method"], slip["payment_method"])

        rows.append(
            [
                slip["id"],
                slip["slip_date"],
                slip["table_name"] or "",
                slip["people"],
                slip["amount"],
                payment_label,
                slip["created_at"],
            ]
        )

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(header)
    cw.writerows(rows)

    output = make_response(si.getvalue())
    current_date = date.today().strftime("%Y%m%d")
    filename = f"sales_export_{current_date}.csv"

    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    return output


# ===========================
# 清空所有业务数据
# ===========================
@main_bp.route("/clear-data", methods=["POST"])
@login_required
def clear_data_view():
    clear_all_business_data()
    return redirect(url_for("main.settings", cleared="1"))


# ===========================
# 登录 / 注册 / 登出
# ===========================
@main_bp.route("/login", methods=["GET", "POST"])
def login():
    # 已经登录就跳首页
    if "user_id" in session:
        return redirect(url_for("main.index"))

    error: Optional[str] = None
    next_url = request.args.get("next") or url_for("main.index")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = get_user_by_username(username)

        if not user or not check_password_hash(user["password_hash"], password):
            error = "账号或密码错误"
        else:
            # 登录成功
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(next_url)

    return render_template(
        "login.html",
        error=error,
        next_url=next_url,
        active_tab=None,
    )


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    简单注册页：你可以只用来创建自己的账号。
    （有默认账号时也可以直接登录，不强制用这个）
    """
    if "user_id" in session:
        return redirect(url_for("main.index"))

    error: Optional[str] = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        if not username or not password:
            error = "账号和密码不能为空"
        elif password != password2:
            error = "两次输入的密码不一致"
        elif get_user_by_username(username):
            error = "该账号已存在"
        else:
            pw_hash = generate_password_hash(password)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            create_user(username, pw_hash, now_str)

            user = get_user_by_username(username)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("main.index"))

    return render_template(
        "register.html",
        error=error,
        active_tab=None,
    )


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))