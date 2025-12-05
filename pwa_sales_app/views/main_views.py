# views/main_views.py
from datetime import datetime, date
from typing import Dict, List, Optional
import csv # <-- 新增导入
from io import StringIO # <-- 新增导入

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    make_response, # <-- 新增导入
)

from database.db import (
    get_slips_by_date,
    get_slip,
    insert_slip,
    update_slip,
    delete_slip,
    get_connection,
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
    get_all_slips, # <-- 新增导入 (db.py 需实现)
    clear_all_data,
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
    food_raw = get_food_sales(business_date) or {} # <-- 修复 AttributeError: 确保 food_raw 为字典
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
def edit_slip_view(slip_id: int): # <-- 路由函数名为 edit_slip_view
    slip = get_slip(slip_id)
    if not slip:
        return redirect(url_for("main.index"))

    business_date = slip["slip_date"]

    if request.method == "POST":
        table_raw = request.form.get("table", "").strip()
        people_raw = request.form.get("people", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        payment_method = slip["payment_method"] # edit.html 缺失 payment_method 字段，使用原值

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
        "edit.html",   # <-- 修复模板名称引用
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
    """某一天的营业日报页面"""
    business_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")

    # 单据列表
    slips = get_slips_by_date(business_date)

    # 补上 HH:MM 时间字段，给模板用 slip.time
    for slip in slips:
        created_at = slip["created_at"]
        slip["time"] = (
            created_at[11:16] if created_at and len(created_at) >= 16 else ""
        )

    # 汇总统计
    summary = calculate_summary(slips)
    payment_summary = get_payment_summary_by_date(business_date)

    # 食物贩卖数据（没有记录时用 0）
    food_raw = get_food_sales(business_date) or {}
    food_items = [
        {"label": "牛排",   "quantity": food_raw.get("steak", 0)},
        {"label": "牛肉粒", "quantity": food_raw.get("beef_cube", 0)},
        {"label": "牛肉串", "quantity": food_raw.get("beef_skewer", 0)},
        {"label": "汉堡",   "quantity": food_raw.get("burger", 0)},
        {"label": "三明治", "quantity": food_raw.get("sandwich", 0)},
        {"label": "虾",     "quantity": food_raw.get("shrimp", 0)},
    ]

    # 负责人时间段
    segments = get_segments_by_date(business_date)

    # 最近有记录的营业日
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
    food_raw = get_food_sales(business_date) or {} # <-- 确保为字典
    items = [
        {"key": "steak",       "label": "牛排",   "quantity": food_raw.get("steak", 0)},
        {"key": "beef_cube",   "label": "牛肉粒", "quantity": food_raw.get("beef_cube", 0)},
        {"key": "beef_skewer", "label": "牛肉串", "quantity": food_raw.get("beef_skewer", 0)},
        {"key": "burger",      "label": "汉堡",   "quantity": food_raw.get("burger", 0)},
        {"key": "sandwich",    "label": "三明治", "quantity": food_raw.get("sandwich", 0)},
        {"key": "shrimp",      "label": "虾",     "quantity": food_raw.get("shrimp", 0)},
    ]

    return render_template(
        "food.html",   # <-- 修复模板名称引用
        active_tab="home",
        business_date=business_date,
        items=items,
    )


# ===========================
# 负责人时间段：新增 / 编辑 / 删除
# ===========================
@main_bp.route("/segments/add", methods=["POST"])
def add_segment(): # <-- 修复路由函数名，并简化逻辑
    business_date = request.form.get("business_date") or date.today().strftime("%Y-%m-%d")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    staff_name = request.form.get("staff_name", "").strip()

    if start_time and end_time and staff_name:
        insert_segment(business_date, start_time, end_time, staff_name)

    return redirect(url_for("main.index", date=business_date))


@main_bp.route("/segments/<int:segment_id>/edit", methods=["GET", "POST"])
def edit_segment_view(segment_id: int): # <-- 路由函数名为 edit_segment_view
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
def settings():
    cleared = request.args.get("cleared") == "1"
    return render_template("settings.html", active_tab="settings", cleared=cleared)


#! 12月5日修改
# ===========================
# 数据导出 CSV  (明细：所有单据)
# ===========================
@main_bp.route("/export/csv")
def export_data_csv():
    """
    导出所有单据数据为 CSV 文件（明细）
    """
    slips_data = get_all_slips()

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
# 新增 1：日报汇总导出 CSV
# ===========================
@main_bp.route("/export/daily_report_csv")
def export_daily_report_csv():
    """
    每一行 = 1 个营业日 的汇总：
    总売上 / 人数 / 桌数 / 各支付方式金额 / 各食物份数
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            s.slip_date                     AS business_date,
            SUM(s.amount)                   AS total_sales,
            SUM(s.people)                   AS total_customers,
            COUNT(*)                        AS total_tables,
            SUM(CASE WHEN s.payment_method='cash'   THEN s.amount ELSE 0 END) AS cash_total,
            SUM(CASE WHEN s.payment_method='credit' THEN s.amount ELSE 0 END) AS credit_total,
            SUM(CASE WHEN s.payment_method='wechat' THEN s.amount ELSE 0 END) AS wechat_total,
            SUM(CASE WHEN s.payment_method='paypay' THEN s.amount ELSE 0 END) AS paypay_total,
            SUM(CASE WHEN s.payment_method='alipay' THEN s.amount ELSE 0 END) AS alipay_total,
            COALESCE(f.steak,       0) AS steak,
            COALESCE(f.beef_cube,   0) AS beef_cube,
            COALESCE(f.beef_skewer, 0) AS beef_skewer,
            COALESCE(f.burger,      0) AS burger,
            COALESCE(f.sandwich,    0) AS sandwich,
            COALESCE(f.shrimp,      0) AS shrimp
        FROM slips s
        LEFT JOIN food_sales f
            ON s.slip_date = f.business_date
        GROUP BY s.slip_date
        ORDER BY s.slip_date ASC
        """
    )

    rows_db = cur.fetchall()
    conn.close()

    # CSV 表头（按你要求）
    header = [
        "营业日",
        "总売上",
        "人数",
        "桌数",
        "总现金",
        "总信用卡",
        "总WeChat Pay",
        "总PayPay",
        "总支付宝",
        "牛排",
        "牛肉粒",
        "牛肉串",
        "汉堡",
        "三明治",
        "虾",
    ]

    rows = []
    for r in rows_db:
        rows.append(
            [
                r["business_date"],
                int(r["total_sales"] or 0),
                int(r["total_customers"] or 0),
                int(r["total_tables"] or 0),
                int(r["cash_total"] or 0),
                int(r["credit_total"] or 0),
                int(r["wechat_total"] or 0),
                int(r["paypay_total"] or 0),
                int(r["alipay_total"] or 0),
                int(r["steak"] or 0),
                int(r["beef_cube"] or 0),
                int(r["beef_skewer"] or 0),
                int(r["burger"] or 0),
                int(r["sandwich"] or 0),
                int(r["shrimp"] or 0),
            ]
        )

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(header)
    cw.writerows(rows)

    output = make_response(si.getvalue())
    filename = f"daily_report_{date.today().strftime('%Y%m%d')}.csv"
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


# ===========================
# 新增 2：月报汇总导出 CSV
# ===========================
@main_bp.route("/export/monthly_report_csv")
def export_monthly_report_csv():
    """
    每一行 = 1 个月 的汇总：
    上面日报的项目在「月度」层面汇总
    """
    conn = get_connection()
    cur = conn.cursor()

    # slips + food_sales 一起按「年月」汇总
    cur.execute(
        """
        SELECT
            strftime('%Y-%m', s.slip_date) AS ym,
            SUM(s.amount)                  AS total_sales,
            SUM(s.people)                  AS total_customers,
            COUNT(*)                       AS total_tables,
            SUM(CASE WHEN s.payment_method='cash'   THEN s.amount ELSE 0 END) AS cash_total,
            SUM(CASE WHEN s.payment_method='credit' THEN s.amount ELSE 0 END) AS credit_total,
            SUM(CASE WHEN s.payment_method='wechat' THEN s.amount ELSE 0 END) AS wechat_total,
            SUM(CASE WHEN s.payment_method='paypay' THEN s.amount ELSE 0 END) AS paypay_total,
            SUM(CASE WHEN s.payment_method='alipay' THEN s.amount ELSE 0 END) AS alipay_total,
            SUM(COALESCE(f.steak,       0)) AS steak,
            SUM(COALESCE(f.beef_cube,   0)) AS beef_cube,
            SUM(COALESCE(f.beef_skewer, 0)) AS beef_skewer,
            SUM(COALESCE(f.burger,      0)) AS burger,
            SUM(COALESCE(f.sandwich,    0)) AS sandwich,
            SUM(COALESCE(f.shrimp,      0)) AS shrimp
        FROM slips s
        LEFT JOIN food_sales f
            ON s.slip_date = f.business_date
        GROUP BY ym
        ORDER BY ym ASC
        """
    )

    rows_db = cur.fetchall()
    conn.close()

    header = [
        "年月",
        "总売上",
        "人数",
        "桌数",
        "总现金",
        "总信用卡",
        "总WeChat Pay",
        "总PayPay",
        "总支付宝",
        "牛排",
        "牛肉粒",
        "牛肉串",
        "汉堡",
        "三明治",
        "虾",
    ]

    rows = []
    for r in rows_db:
        rows.append(
            [
                r["ym"],
                int(r["total_sales"] or 0),
                int(r["total_customers"] or 0),
                int(r["total_tables"] or 0),
                int(r["cash_total"] or 0),
                int(r["credit_total"] or 0),
                int(r["wechat_total"] or 0),
                int(r["paypay_total"] or 0),
                int(r["alipay_total"] or 0),
                int(r["steak"] or 0),
                int(r["beef_cube"] or 0),
                int(r["beef_skewer"] or 0),
                int(r["burger"] or 0),
                int(r["sandwich"] or 0),
                int(r["shrimp"] or 0),
            ]
        )

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(header)
    cw.writerows(rows)

    output = make_response(si.getvalue())
    filename = f"monthly_report_{date.today().strftime('%Y%m%d')}.csv"
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

# ===========================
# 一键清空数据（危险操作）
# ===========================
@main_bp.route("/settings/clear", methods=["POST"])
def clear_data_view():
    """
    清空所有业务数据，然后回到设置页。
    """
    clear_all_data()
    # 带一个 ?cleared=1 回去，让页面显示“已清空”提示
    return redirect(url_for("main.settings", cleared="1"))