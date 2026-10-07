"""
ui/views/timeline_dialog.py

【このコードの目的・機能・挙動】
Analysis画面の「Timeline」ダイアログモジュールです。
- 支出: X軸より下に伸びる半透明オレンジ色の柱状グラフ（期間合算）
- 収入: X軸より上に伸びる半透明緑色の柱状グラフ（期間合算）
- 収支(Balance): 最前面に重ねて描画されるシアン色の累積折れ線グラフ

【マルチデバイス対応・改善点】
1. ラベル重複の完全解決:
   LineChart側のX軸目盛りに「空文字の透明ラベル」を明示的に渡し、
   インデックス数字（0, 2, 4...）が背面のBarChartの日付と重なって描画される問題を根絶。
2. レスポンシブな柱幅の算出:
   現在のページ幅（page.width / page.window.width）に応じて、各柱が隙間なく
   かつ重なり合わない最適な幅（width）を動的計算。スマホ・タブレット・PC全対応。
3. サマリー表示の自動折り返し:
   wrap=True により画面幅が狭くてもサマリーテキスト（Balance/Max/Min）が見切れないよう調整。
"""

import asyncio
from typing import List, Any
import flet as ft
import flet_charts as fch

from logic.aggregator import calculate_timeline_data, calculate_nice_interval


def open_timeline_dialog(page: ft.Page, filtered_data_rows: List[List[Any]]) -> None:
    if not filtered_data_rows:
        return

    # 集計ロジックを呼び出し、座標データを生成
    t_data = calculate_timeline_data(filtered_data_rows)
    if not t_data:
        return

    bar_groups_data = t_data["bar_groups"]
    line_points_data = t_data["line_points"]
    bin_count = t_data["bin_count"]
    bin_mode = t_data["bin_mode"]

    # --------------------------------------------------------------------------
    # 1. 表示トグルステート
    # --------------------------------------------------------------------------
    show_inc = True
    show_exp = True
    show_bal = True

    # 軸の共通サイズ定数
    Y_LABEL_SIZE = 55
    X_LABEL_SIZE = 40

    # --------------------------------------------------------------------------
    # 2. グラフコンポーネント（背面: BarChart, 前面: LineChart）
    # --------------------------------------------------------------------------
    bar_chart = fch.BarChart(
        expand=True,
        border=ft.Border.all(1, ft.Colors.GREY_800),
        left_axis=fch.ChartAxis(
            label_size=Y_LABEL_SIZE,
            title=ft.Text("金額 (¥)"),
            title_size=14
        ),
        bottom_axis=fch.ChartAxis(
            label_size=X_LABEL_SIZE,
            title=ft.Text(f"期間 ({bin_mode})"),
            title_size=14
        ),
    )

    # 前面: 折れ線グラフ
    line_chart = fch.LineChart(
        expand=True,
        bgcolor=ft.Colors.TRANSPARENT,
        border=ft.Border.all(1, ft.Colors.TRANSPARENT),
        left_axis=fch.ChartAxis(
            label_size=Y_LABEL_SIZE,
            labels=[fch.ChartAxisLabel(value=0, label=ft.Text(""))],  # 自動数字目盛りの生成を防止
            title=ft.Text(" ", size=14),
        ),
        bottom_axis=fch.ChartAxis(
            label_size=X_LABEL_SIZE,
            labels=[fch.ChartAxisLabel(value=0, label=ft.Text(""))],  # 自動数字目盛り（0, 2, 4...）の生成を防止
            title=ft.Text(" ", size=14),
        ),
        top_axis=None,
        right_axis=None,
    )

    # サマリー表示用コンテナ（自動折り返しを有効化）
    summary_col = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10
    )

    def update_graph(e: ft.ControlEvent = None):
        nonlocal show_inc, show_exp, show_bal

        if e:
            if e.control.data == "inc":
                show_inc = not show_inc
            elif e.control.data == "exp":
                show_exp = not show_exp
            elif e.control.data == "bal":
                show_bal = not show_bal

        # ボタンのスタイル更新
        btn_inc.icon = ft.Icons.CHECK_BOX if show_inc else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_inc.style = ft.ButtonStyle(color=ft.Colors.GREEN if show_inc else ft.Colors.GREY)

        btn_exp.icon = ft.Icons.CHECK_BOX if show_exp else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_exp.style = ft.ButtonStyle(color=ft.Colors.ORANGE_ACCENT if show_exp else ft.Colors.GREY)

        btn_bal.icon = ft.Icons.CHECK_BOX if show_bal else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_bal.style = ft.ButtonStyle(color=ft.Colors.CYAN if show_bal else ft.Colors.GREY)

        # ----------------------------------------------------------------------
        # スケール（Min Y / Max Y）の共通計算
        # ----------------------------------------------------------------------
        y_values = [0.0]
        for bg in bar_groups_data:
            if show_inc and bg["income"] > 0:
                y_values.append(bg["income"])
            if show_exp and bg["expense"] < 0:
                y_values.append(bg["expense"])

        if show_bal:
            for lp in line_points_data:
                y_values.append(lp["y"])

        raw_min_y = min(y_values)
        raw_max_y = max(y_values)
        y_interval, nice_min_y, nice_max_y = calculate_nice_interval(raw_min_y, raw_max_y, target_steps=5)

        # ----------------------------------------------------------------------
        # 画面幅に応じたレスポンシブな柱の幅の計算
        # ----------------------------------------------------------------------
        current_width = page.width if page.width else (page.window.width if page.window.width else 400)
        # ダイアログのパディングとY軸ラベル幅を除いた有効プロット幅を算出
        usable_plot_width = max(200, current_width - Y_LABEL_SIZE - 60)
        # 柱同士が適度に埋まる幅（階級幅の約70%）
        calculated_col_width = (usable_plot_width / max(1, bin_count)) * 0.70
        col_width = max(3, min(28, int(calculated_col_width)))

        # ----------------------------------------------------------------------
        # 背面: 棒グラフ（BarChart）のデータ生成
        # ----------------------------------------------------------------------
        chart_bar_groups = []
        labels = []

        # 画面幅に応じて横軸ラベルの表示数を調整（スマホは3〜4個、PCは6〜8個）
        target_label_count = 4 if current_width < 500 else 7
        step = max(1, bin_count // target_label_count)

        trans_green = ft.Colors.with_opacity(0.35, ft.Colors.GREEN)
        trans_orange = ft.Colors.with_opacity(0.40, ft.Colors.ORANGE_ACCENT)

        for bg in bar_groups_data:
            x_idx = bg["x"]
            rod_stack = []

            # 収入柱
            if show_inc and bg["income"] > 0:
                rod_stack.append(
                    fch.BarChartRod(
                        from_y=0,
                        to_y=bg["income"],
                        width=col_width,
                        color=trans_green,
                        border_radius=ft.BorderRadius(2, 2, 0, 0),
                        tooltip=f"収入: +¥{bg['income']:,.0f}"
                    )
                )

            # 支出柱
            if show_exp and bg["expense"] < 0:
                rod_stack.append(
                    fch.BarChartRod(
                        from_y=0,
                        to_y=bg["expense"],
                        width=col_width,
                        color=trans_orange,
                        border_radius=ft.BorderRadius(0, 0, 2, 2),
                        tooltip=f"支出: ¥{bg['expense']:,.0f}"
                    )
                )

            chart_bar_groups.append(fch.BarChartGroup(x=x_idx, rods=rod_stack))

            # X軸ラベル（間引き設定）
            if x_idx % step == 0 or x_idx == bin_count - 1:
                labels.append(
                    fch.ChartAxisLabel(
                        value=x_idx,
                        label=ft.Container(
                            margin=ft.Margin.only(top=10),
                            content=ft.Text(bg["label"], size=9 if current_width < 500 else 10, weight=ft.FontWeight.BOLD)
                        )
                    )
                )

        bar_chart.min_y = nice_min_y
        bar_chart.max_y = nice_max_y
        bar_chart.groups = chart_bar_groups
        bar_chart.bottom_axis.labels = labels

        # 横グリッド線
        bar_chart.horizontal_grid_lines = fch.ChartGridLines(
            interval=y_interval,
            color=ft.Colors.with_opacity(0.12, ft.Colors.GREY),
            width=1
        )

        # ----------------------------------------------------------------------
        # 前面: 折れ線グラフ（LineChart）のデータ生成
        # ----------------------------------------------------------------------
        line_chart.min_y = nice_min_y
        line_chart.max_y = nice_max_y

        max_idx = max(0, bin_count - 1)
        line_chart.min_x = 0
        line_chart.max_x = max_idx

        # 【最重要】前面LineChartのX軸・Y軸に空文字のダミーラベルをセットして自動目盛数字（0,2,4...）を消去
        line_chart.bottom_axis.labels = [fch.ChartAxisLabel(value=x, label=ft.Text("")) for x in range(bin_count)]
        line_chart.left_axis.labels = [fch.ChartAxisLabel(value=nice_min_y, label=ft.Text("")), fch.ChartAxisLabel(value=nice_max_y, label=ft.Text(""))]

        if show_bal and line_points_data:
            data_points = [
                fch.LineChartDataPoint(
                    max(0.0, min(float(max_idx), lp["x"])),
                    lp["y"],
                    tooltip=lp["tooltip"]
                )
                for lp in line_points_data
            ]
            line_chart.data_series = [
                fch.LineChartData(
                    data_points,
                    color=ft.Colors.CYAN_ACCENT_400,
                    stroke_width=2.5 if current_width < 500 else 3.0
                )
            ]
        else:
            line_chart.data_series = []

        # ----------------------------------------------------------------------
        # サマリー情報更新（折り返し対応）
        # ----------------------------------------------------------------------
        summary_col.controls.clear()
        if show_bal and line_points_data:
            vals = [lp["y"] for lp in line_points_data]
            summary_col.controls.extend([
                ft.Text(f"Balance: ¥{vals[-1]:,.0f}", color=ft.Colors.CYAN, weight=ft.FontWeight.BOLD, size=11),
                ft.Text(f"Max: ¥{max(vals):,.0f}", color=ft.Colors.GREY_400, size=11),
                ft.Text(f"Min: ¥{min(vals):,.0f}", color=ft.Colors.GREY_400, size=11),
            ])

        if e:
            timeline_dialog.update()

    # 操作ボタングループ
    btn_inc = ft.TextButton("Income (柱)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="inc")
    btn_exp = ft.TextButton("Expense (柱)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="exp")
    btn_bal = ft.TextButton("Balance (線)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="bal")

    button_row = ft.Row(
        controls=[btn_inc, btn_exp, btn_bal],
        alignment=ft.MainAxisAlignment.CENTER,
        wrap=True,
        spacing=5
    )

    combined_chart_stack = ft.Stack(
        controls=[
            bar_chart,   # 背面: 目盛り・グリッド・柱
            line_chart   # 前面: 累積折れ線（目盛り数字非表示）
        ],
        expand=True
    )

    async def close_timeline(e: ft.ControlEvent):
        timeline_dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if timeline_dialog in page.overlay:
            page.overlay.remove(timeline_dialog)
            page.update()

    # ダイアログ自体のレスポンシブサイズ設定
    win_w = page.width if page.width else (page.window.width if page.window.width else 400)
    win_h = page.height if page.height else (page.window.height if page.window.height else 700)
    
    dialog_width = min(800, int(win_w * 0.95))
    dialog_height = min(560, int(win_h * 0.85))

    timeline_dialog = ft.AlertDialog(
        title=ft.Text("推移・収支分析", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=dialog_width,
            height=dialog_height,
            content=ft.Column([
                button_row,
                summary_col,
                ft.Container(combined_chart_stack, expand=True, padding=ft.Padding.only(top=5, right=10))
            ])
        ),
        actions=[
            ft.TextButton("閉じる", on_click=close_timeline)
        ]
    )

    page.overlay.append(timeline_dialog)
    timeline_dialog.open = True
    update_graph()
    page.update()