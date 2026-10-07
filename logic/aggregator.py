"""
logic/aggregator.py

【このコードの目的・機能・挙動】
UI（Flet）から独立して動作する集計・統計計算モジュールです。
LineChart単一統合向けに、以下の計算を担当します。
1. サマリー計算（calculate_summary）
2. 円グラフ内訳計算（calculate_category_breakdown）
3. 単一LineChart用タイムラインデータ生成（calculate_timeline_data）:
   - 収入: 各区間 [i, i+1] の矩形ステップ点群（0 -> +Inc -> +Inc -> 0）
   - 支出: 各区間 [i, i+1] の矩形ステップ点群（0 -> -Exp -> -Exp -> 0）
   - 収支(Balance): 各日の累積残高を区間内の正確な小数X座標にマッピング
"""

import math
import calendar
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple


def calculate_summary(data_rows: List[List[Any]]) -> Tuple[float, float, float]:
    """明細リストから (支出合計, 収入合計, 収支) を算出して返す"""
    total_expense = 0.0
    total_income = 0.0

    for row in data_rows:
        val_str = str(row[2]).strip() if len(row) > 2 and row[2] != "" else ""
        if not val_str:
            continue
        try:
            amt = float(val_str)
            if amt < 0:
                total_expense += amt
            elif amt > 0:
                total_income += amt
        except ValueError:
            continue

    balance = total_income + total_expense
    return total_expense, total_income, balance


def calculate_category_breakdown(data_rows: List[List[Any]]) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """支出カテゴリ別・収入カテゴリ別の合計金額を降順ソートして返す"""
    expense_summary: Dict[str, float] = {}
    income_summary: Dict[str, float] = {}

    for row in data_rows:
        if len(row) < 4:
            continue
        mode = row[1]
        val_str = str(row[2]).strip()
        cat = row[3]

        try:
            amt = abs(float(val_str)) if val_str else 0.0
        except ValueError:
            amt = 0.0

        if mode == "Expense":
            expense_summary[cat] = expense_summary.get(cat, 0.0) + amt
        else:
            income_summary[cat] = income_summary.get(cat, 0.0) + amt

    sorted_expense = sorted(expense_summary.items(), key=lambda x: x[1], reverse=True)
    sorted_income = sorted(income_summary.items(), key=lambda x: x[1], reverse=True)

    return sorted_expense, sorted_income


def calculate_nice_interval(raw_min_y: float, raw_max_y: float, target_steps: int = 5) -> Tuple[float, float, float]:
    """キリの良い間隔（1, 2, 5 × 10^n）とmin_y, max_yを算出する"""
    y_range = raw_max_y - raw_min_y
    if y_range == 0:
        y_range = 100.0

    rough_step = y_range / target_steps
    magnitude = 10 ** math.floor(math.log10(rough_step)) if rough_step > 0 else 1.0
    normalized_step = rough_step / magnitude

    if normalized_step <= 1:
        nice_step = 1.0
    elif normalized_step <= 2:
        nice_step = 2.0
    elif normalized_step <= 5:
        nice_step = 5.0
    else:
        nice_step = 10.0

    y_interval = nice_step * magnitude
    min_y = math.floor(raw_min_y / y_interval) * y_interval - y_interval
    max_y = math.ceil(raw_max_y / y_interval) * y_interval + y_interval

    return y_interval, min_y, max_y


def calculate_timeline_data(data_rows: List[List[Any]]) -> Dict[str, Any]:
    """
    LineChart単一統合用の座標データを生成する。
    """
    if not data_rows:
        return {}

    sorted_rows = sorted(data_rows, key=lambda x: x[0])

    def to_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d")

    start_dt = to_date(sorted_rows[0][0])
    end_dt = to_date(sorted_rows[-1][0])
    total_days = (end_dt - start_dt).days + 1

    # 期間に応じたビニング単位の決定
    if total_days <= 31:
        bin_mode = "daily"
    elif total_days <= 180:
        bin_mode = "weekly"
    else:
        bin_mode = "monthly"

    # 日別集計
    daily_summary: Dict[str, Dict[str, float]] = {}
    for row in sorted_rows:
        d = row[0]
        mode = row[1]
        try:
            val = float(row[2]) if row[2] else 0.0
        except ValueError:
            val = 0.0

        if d not in daily_summary:
            daily_summary[d] = {"income": 0.0, "expense": 0.0}

        if mode == "Income":
            daily_summary[d]["income"] += val
        elif mode == "Expense":
            daily_summary[d]["expense"] += val

    unique_dates = sorted(daily_summary.keys())

    # ビン区間の生成（開始日・終了日・ラベル）
    bins: List[Dict[str, Any]] = []
    curr = start_dt

    if bin_mode == "monthly":
        curr = datetime(start_dt.year, start_dt.month, 1)
        end_limit = datetime(end_dt.year, end_dt.month, 1)
        while curr <= end_limit:
            _, last_day = calendar.monthrange(curr.year, curr.month)
            next_month = curr + timedelta(days=last_day)
            bins.append({
                "start": curr,
                "end": next_month,
                "label": curr.strftime("%Y/%m"),
                "income": 0.0,
                "expense": 0.0
            })
            curr = next_month
    elif bin_mode == "weekly":
        curr = start_dt - timedelta(days=start_dt.weekday())
        while curr <= end_dt:
            next_week = curr + timedelta(days=7)
            bins.append({
                "start": curr,
                "end": next_week,
                "label": curr.strftime("%m/%d"),
                "income": 0.0,
                "expense": 0.0
            })
            curr = next_week
    else:  # daily
        while curr <= end_dt:
            next_day = curr + timedelta(days=1)
            bins.append({
                "start": curr,
                "end": next_day,
                "label": curr.strftime("%m/%d"),
                "income": 0.0,
                "expense": 0.0
            })
            curr = next_day

    # 各レコードを該当ビンに積算し、Balanceの連続座標を算出
    cum_bal = 0.0
    line_bal_points: List[Dict[str, Any]] = []

    for d_str in unique_dates:
        dt = to_date(d_str)
        inc = daily_summary[d_str]["income"]
        exp = daily_summary[d_str]["expense"]
        cum_bal += (inc + exp)

        for idx, b in enumerate(bins):
            if b["start"] <= dt < b["end"]:
                b["income"] += inc
                b["expense"] += exp  # 負の値

                # 区間内の精密なX座標 (idx + 経過割合)
                bin_duration = (b["end"] - b["start"]).total_seconds()
                offset = (dt - b["start"]).total_seconds()
                exact_x = idx + (offset / bin_duration)

                line_bal_points.append({
                    "x": exact_x,
                    "y": cum_bal,
                    "tooltip": f"Balance: ¥{cum_bal:,.0f}\n+{inc:,.0f} | {exp:,.0f}\n{d_str}"
                })
                break

    # 柱状ステップ面用のポイント作成 (区間 [i, i+1] を矩形として表現)
    step_inc_points: List[Dict[str, Any]] = []
    step_exp_points: List[Dict[str, Any]] = []

    for idx, b in enumerate(bins):
        inc_val = b["income"]
        exp_val = b["expense"]  # 負の値

        # 収入柱 (0 -> Inc -> Inc -> 0)
        step_inc_points.extend([
            {"x": float(idx), "y": 0.0, "tooltip": None},
            {"x": float(idx), "y": inc_val, "tooltip": f"収入: +¥{inc_val:,.0f}\n{b['label']}"},
            {"x": float(idx + 1), "y": inc_val, "tooltip": f"収入: +¥{inc_val:,.0f}\n{b['label']}"},
            {"x": float(idx + 1), "y": 0.0, "tooltip": None},
        ])

        # 支出柱 (0 -> Exp -> Exp -> 0)
        step_exp_points.extend([
            {"x": float(idx), "y": 0.0, "tooltip": None},
            {"x": float(idx), "y": exp_val, "tooltip": f"支出: ¥{exp_val:,.0f}\n{b['label']}"},
            {"x": float(idx + 1), "y": exp_val, "tooltip": f"支出: ¥{exp_val:,.0f}\n{b['label']}"},
            {"x": float(idx + 1), "y": 0.0, "tooltip": None},
        ])

    # ラベル情報
    labels_info = [{"value": idx, "text": b["label"]} for idx, b in enumerate(bins)]

    return {
        "step_inc_points": step_inc_points,
        "step_exp_points": step_exp_points,
        "line_bal_points": line_bal_points,
        "labels_info": labels_info,
        "bin_count": len(bins),
        "bin_mode": bin_mode
    }