"""
logic/aggregator.py

【このコードの目的・機能・挙動】
UI（Flet）から独立して動作する集計・統計計算モジュールです。
LineChart単一統合向けに、各柱を独立した矩形（4点）として算出し、
0円ラインから柱の内部のみを安全に塗りつぶすためのデータを生成します。

【折れ線の単一系統統合 ＆ ツールチップ動的間引き】
- 折れ線自体は全取引日（スパイク・歴代最高値・歴代最低値を含む）を100%保持して描画。
- ツールチップ（要約カード）は、ダウンサンプリングによって選定された40〜60点、
  および歴代最高値・最低値・始終点にのみ文字列を設定し、中間点には tooltip=None を設定。
- これにより、系列同士の競合や描画スキップを防ぎ、ホバー判定の安定性と高精細な描画を両立します。
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
    """LineChart単一統合用の座標データを生成する"""
    if not data_rows:
        return {}

    sorted_rows = sorted(data_rows, key=lambda x: x[0])

    def to_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d")

    start_dt = to_date(sorted_rows[0][0])
    end_dt = to_date(sorted_rows[-1][0])
    total_days = (end_dt - start_dt).days + 1

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

    # ビン区間の生成
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

    # 1. 全日ポイントの連続計算（折れ線自体の幾何学的完全性を担保）
    cum_bal = 0.0
    raw_bal_points: List[Dict[str, Any]] = []

    for d_str in unique_dates:
        dt = to_date(d_str)
        inc = daily_summary[d_str]["income"]
        exp = daily_summary[d_str]["expense"]
        cum_bal += (inc + exp)

        for idx, b in enumerate(bins):
            if b["start"] <= dt < b["end"]:
                b["income"] += inc
                b["expense"] += exp

                bin_duration = (b["end"] - b["start"]).total_seconds()
                offset = (dt - b["start"]).total_seconds()
                exact_x = idx + (offset / bin_duration)

                sign_bal = f"+{cum_bal:,.0f}" if cum_bal >= 0 else f"- {abs(cum_bal):,.0f}"
                fmt_inc = f"+{inc:,.0f}" if inc > 0 else "0"
                fmt_exp = f"- {abs(exp):,.0f}" if exp < 0 else "0"

                tip_text = f"{dt.strftime('%Y/%m/%d')}\n収支: {sign_bal}\n+{fmt_inc} | {fmt_exp}"

                raw_bal_points.append({
                    "x": exact_x,
                    "y": cum_bal,
                    "tooltip_text": tip_text,
                    "bin_idx": idx,
                })
                break

    # 2. ツールチップ有効点の選定（サンプリング ＋ 最大値・最小値の厳密保持）
    active_indices = set()
    total_raw = len(raw_bal_points)

    if total_raw <= 60 or bin_mode == "daily":
        active_indices = set(range(total_raw))
    else:
        # 各ビンから代表点（中央・末尾）を抽出
        bin_to_indices: Dict[int, List[int]] = {}
        for i, pt in enumerate(raw_bal_points):
            bin_to_indices.setdefault(pt["bin_idx"], []).append(i)

        for b_idx in sorted(bin_to_indices.keys()):
            indices = bin_to_indices[b_idx]
            count = len(indices)
            if count <= 2:
                active_indices.update(indices)
            else:
                active_indices.add(indices[count // 2])
                active_indices.add(indices[-1])

        # 歴代最高値（Max）・最低値（Min）のインデックスを必ず含める
        max_idx = max(range(total_raw), key=lambda i: raw_bal_points[i]["y"])
        min_idx = min(range(total_raw), key=lambda i: raw_bal_points[i]["y"])
        active_indices.add(max_idx)
        active_indices.add(min_idx)

        # 始点と終点も含める
        active_indices.add(0)
        active_indices.add(total_raw - 1)

    # 3. 単一折れ線用の最終データ点リストを作成
    # （選定された点のみ tooltip を持たせ、それ以外は None にして判定競合を回避）
    line_bal_points: List[Dict[str, Any]] = []
    for i, pt in enumerate(raw_bal_points):
        line_bal_points.append({
            "x": pt["x"],
            "y": pt["y"],
            "tooltip": pt["tooltip_text"] if i in active_indices else None,
        })

    # 4. 柱ごとの独立した矩形点リスト作成（0 -> Y -> Y -> 0）
    bar_inc_series: List[Dict[str, Any]] = []
    bar_exp_series: List[Dict[str, Any]] = []

    EPSILON = 0.04  # 折れ線との境界干渉・ホバー衝突を防ぐマージン

    for idx, b in enumerate(bins):
        inc_val = b["income"]
        exp_val = b["expense"]

        x_left = float(idx) + EPSILON
        x_right = float(idx + 1) - EPSILON

        if inc_val > 0:
            bar_inc_series.append({
                "points": [
                    {"x": x_left, "y": 0.0},
                    {"x": x_left, "y": inc_val},
                    {"x": x_right, "y": inc_val},
                    {"x": x_right, "y": 0.0},
                ],
                "val": inc_val
            })

        if exp_val < 0:
            bar_exp_series.append({
                "points": [
                    {"x": x_left, "y": 0.0},
                    {"x": x_left, "y": exp_val},
                    {"x": x_right, "y": exp_val},
                    {"x": x_right, "y": 0.0},
                ],
                "val": exp_val
            })

    labels_info = [{"value": idx, "text": b["label"]} for idx, b in enumerate(bins)]

    return {
        "bar_inc_series": bar_inc_series,
        "bar_exp_series": bar_exp_series,
        "line_bal_points": line_bal_points,
        "labels_info": labels_info,
        "bin_count": len(bins),
        "bin_mode": bin_mode
    }