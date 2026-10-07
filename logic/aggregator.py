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
from datetime import datetime, timedelta
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
    推移グラフ用に、期間長に応じたビン（日/週/月）ごとの支出(負)・収入(正)の棒グラフデータと、
    累積Balanceの折れ線データを計算して返す。
    """
    if not data_rows:
        return {}

    # 1. 日付順にソート
    sorted_rows = sorted(data_rows, key=lambda x: x[0])

    def to_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d")

    start_dt = to_date(sorted_rows[0][0])
    end_dt = to_date(sorted_rows[-1][0])
    total_days = (end_dt - start_dt).days + 1

    # 2. 期間に応じたビニング（集計単位）の決定
    # - 31日以下: 日次 (Daily)
    # - 180日以下: 週次 (Weekly)
    # - それ以上: 月次 (Monthly)
    if total_days <= 31:
        bin_mode = "daily"
    elif total_days <= 180:
        bin_mode = "weekly"
    else:
        bin_mode = "monthly"

    # 日付からビンのキー（YYYY-MM-DD または代表日）とラベルを返すヘルパー
    def get_bin_info(dt: datetime) -> Tuple[datetime, str]:
        if bin_mode == "daily":
            return dt, dt.strftime("%m/%d")
        elif bin_mode == "weekly":
            # 週の月曜日を代表日とする
            mon = dt - timedelta(days=dt.weekday())
            return mon, mon.strftime("%m/%d")
        else:
            # 月の1日を代表日とする
            first_day = datetime(dt.year, dt.month, 1)
            return first_day, first_day.strftime("%Y/%m")

    # 3. 日別集計と累積Balanceの計算
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

    # 全期間の日付リスト
    unique_dates = sorted(daily_summary.keys())
    cum_bal = 0.0
    balance_points = []  # LineChart用

    # 棒グラフ用のビン集計
    bin_summary: Dict[datetime, Dict[str, Any]] = {}

    for d_str in unique_dates:
        dt = to_date(d_str)
        inc = daily_summary[d_str]["income"]
        exp = daily_summary[d_str]["expense"]
        cum_bal += (inc + exp)

        # 折れ線グラフ用（日次累積）
        balance_points.append({
            "date": d_str,
            "cum_bal": cum_bal,
            "inc": inc,
            "exp": exp,
            "dt": dt
        })

        # 棒グラフ用ビニング
        bin_dt, label = get_bin_info(dt)
        if bin_dt not in bin_summary:
            bin_summary[bin_dt] = {"income": 0.0, "expense": 0.0, "label": label}
        bin_summary[bin_dt]["income"] += inc
        bin_summary[bin_dt]["expense"] += exp  # 支出は負の値

    # 棒グラフ用のインデックス座標変換
    sorted_bins = sorted(bin_summary.keys())
    bar_groups = []
    
    # 棒グラフのX座標インデックス (0, 1, 2, ...)
    for idx, b_dt in enumerate(sorted_bins):
        b_data = bin_summary[b_dt]
        bar_groups.append({
            "x": idx,
            "income": b_data["income"],
            "expense": b_data["expense"],  # 負の値
            "label": b_data["label"],
            "dt": b_dt
        })

    # 折れ線グラフのX座標を棒グラフのインデックススケールに正規化
    # 棒グラフの各ビン代表日からの相対位置でマッピング
    norm_line_points = []
    if len(sorted_bins) == 1:
        for p in balance_points:
            norm_line_points.append({"x": 0.0, "y": p["cum_bal"], "tooltip": f"Balance: ¥{p['cum_bal']:,.0f}\n{p['date']}"})
    else:
        min_bin_ts = sorted_bins[0].timestamp()
        max_bin_ts = sorted_bins[-1].timestamp()
        ts_span = max_bin_ts - min_bin_ts if max_bin_ts != min_bin_ts else 1.0
        max_idx = len(sorted_bins) - 1

        for p in balance_points:
            cur_ts = p["dt"].timestamp()
            rel_x = ((cur_ts - min_bin_ts) / ts_span) * max_idx
            norm_line_points.append({
                "x": rel_x,
                "y": p["cum_bal"],
                "tooltip": f"Balance: ¥{p['cum_bal']:,.0f}\n+{p['inc']:,.0f} | {p['exp']:,.0f}\n{p['date']}"
            })

    return {
        "bar_groups": bar_groups,
        "line_points": norm_line_points,
        "bin_count": len(sorted_bins),
        "bin_mode": bin_mode
    }