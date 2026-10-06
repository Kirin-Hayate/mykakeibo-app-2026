"""
logic/aggregator.py

【このコードの目的・機能・挙動】
UI（Flet）から独立して動作する、純粋な集計・統計計算モジュールです。
以下の3つの主要な計算責務を担当します。

1. サマリー計算（calculate_summary）:
   フィルタ後の明細群から、支出合計（マイナス値）、収入合計（プラス値）、
   および最終収支（Balance）を高速に算出します。
2. 円グラフ内訳計算（calculate_category_breakdown）:
   支出・収入ごとにカテゴリ別の合計金額を集計し、降順ソートおよび構成比（%）を算出します。
3. 推移グラフ累積計算および軸スケーリング（calculate_timeline_data）:
   日付順にデータを並び替え、日々の収入・支出・残高の「累積値」を生成します。
   また、FletのLineChartで綺麗にグリッドを描画できるよう、最大値・最小値から
   「1, 2, 5 × 10^n」刻みの最適なY軸インターバルを算出します。
"""

import math
from datetime import datetime
from typing import List, Dict, Any, Tuple


def calculate_summary(data_rows: List[List[Any]]) -> Tuple[float, float, float]:
    """
    明細リストから (支出合計, 収入合計, 収支) を算出して返す。
    支出合計は負の数、収入合計は正の数として計算される。
    """
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
    """
    明細リストから、支出カテゴリ別集計と収入カテゴリ別集計を降順ソートして返す。
    戻り値: (sorted_expense_list, sorted_income_list)
    """
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

    # 金額の降順にソート
    sorted_expense = sorted(expense_summary.items(), key=lambda x: x[1], reverse=True)
    sorted_income = sorted(income_summary.items(), key=lambda x: x[1], reverse=True)

    return sorted_expense, sorted_income


def calculate_nice_interval(raw_min_y: float, raw_max_y: float, target_steps: int = 5) -> Tuple[float, float, float]:
    """
    与えられた最小値と最大値から、グラフの目盛りとしてキリの良い間隔（nice step）と
    拡張されたmin_y, max_yを算出する。
    nice stepは 1, 2, 5 × 10^n のいずれかになる。
    """
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

    # min_y, max_y をインターバルの倍数に広げて余裕を持たせる
    min_y = math.floor(raw_min_y / y_interval) * y_interval - y_interval
    max_y = math.ceil(raw_max_y / y_interval) * y_interval + y_interval

    return y_interval, min_y, max_y


def calculate_timeline_data(data_rows: List[List[Any]]) -> Dict[str, Any]:
    """
    推移グラフ用に、日別の累積データとX軸/Y軸の描画パラメータを計算して返す。
    """
    if not data_rows:
        return {}

    # 1. 日付順にソート
    sorted_rows = sorted(data_rows, key=lambda x: x[0])

    # 2. 日付ごとに集計
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

    dates = sorted(daily_summary.keys())
    if not dates:
        return {}

    def to_ts(date_str: str) -> float:
        return datetime.strptime(date_str, "%Y-%m-%d").timestamp()

    min_x = to_ts(dates[0])
    max_x = to_ts(dates[-1])
    day_seconds = 24 * 60 * 60

    if max_x == min_x:
        max_x += day_seconds

    cum_inc, cum_exp, cum_bal = 0.0, 0.0, 0.0
    points_inc, points_exp, points_bal = [], [], []

    for d in dates:
        inc = daily_summary[d]["income"]
        exp = daily_summary[d]["expense"]

        cum_inc += inc
        cum_exp += abs(exp)  # 支出は絶対値で累積
        cum_bal += (inc + exp)

        ts = to_ts(d)
        rel_x = ts - min_x  # 開始日を0秒とする相対X座標

        points_inc.append({"x": rel_x, "y": cum_inc, "tooltip": f"+{cum_inc:,.0f}|+{inc:,.0f}"})
        points_exp.append({"x": rel_x, "y": cum_exp, "tooltip": f"-{cum_exp:,.0f}|-{abs(exp):,.0f}"})
        points_bal.append({"x": rel_x, "y": cum_bal, "tooltip": f"{cum_bal:,.0f}|{inc + exp:,.0f} \n {d}"})

    # X軸の間引き間隔決定
    duration = max_x - min_x
    if duration <= 14 * day_seconds:
        x_interval = day_seconds
        date_fmt = "%m/%d"
    elif duration <= 90 * day_seconds:
        x_interval = 7 * day_seconds
        date_fmt = "%m/%d"
    else:
        x_interval = 30 * day_seconds
        date_fmt = "%Y/%m"

    return {
        "min_x": 0,
        "max_x": max_x - min_x,
        "min_ts": min_x,
        "x_interval": x_interval,
        "date_fmt": date_fmt,
        "points_inc": points_inc,
        "points_exp": points_exp,
        "points_bal": points_bal,
    }