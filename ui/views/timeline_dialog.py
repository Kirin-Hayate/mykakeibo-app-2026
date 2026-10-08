"""
ui/views/timeline_dialog.py

【このコードの目的・機能・挙動】
Analysis画面の「Timeline」ダイアログモジュールです。
LineChart 1つに完全統合し、柱の内部のみを安全に塗りつぶしつつ、
単一の折れ線系列（全点描画 ＆ 動的間引きツールチップ）によって
正確なピーク表示とサクサク動く要約カード描画を実現します。

- 支出: X軸（0円ライン）から下へ伸びる半透明オレンジ色の柱（ホバー縦線は完全透明化）
- 収入: X軸（0円ライン）から上へ伸びる半透明緑色の柱（ホバー縦線は完全透明化）
- 収支(Balance): 最前面を横断するシアン色の折れ線（全点通過・有効点のみ小さな選択点と要約カードが点灯）
"""

import asyncio
from typing import List, Any
import flet as ft
import flet_charts as fch

from logic.aggregator import calculate_timeline_data, calculate_nice_interval


def open_timeline_dialog(page: ft.Page, filtered_data_rows: List[List[Any]]) -> None:
    if not filtered_data_rows:
        return

    t_data = calculate_timeline_data(filtered_data_rows)
    if not t_data:
        return

    bar_inc_series = t_data["bar_inc_series"]
    bar_exp_series = t_data["bar_exp_series"]
    line_bal_points = t_data["line_bal_points"]
    labels_info = t_data["labels_info"]
    bin_count = t_data["bin_count"]
    bin_mode = t_data["bin_mode"]

    show_inc = True
    show_exp = True
    show_bal = True

    # --------------------------------------------------------------------------
    # 単一LineChartコンポーネント
    # --------------------------------------------------------------------------
    chart = fch.LineChart(
        expand=True,
        border=ft.Border.all(1, ft.Colors.GREY_800),
        vertical_grid_lines=fch.ChartGridLines(
            color=ft.Colors.with_opacity(0.18, ft.Colors.CYAN_100),
            width=1.0,
        ),
        left_axis=fch.ChartAxis(
            label_size=55,
            title=ft.Text("金額 (¥)"),
            title_size=14,
        ),
        bottom_axis=fch.ChartAxis(
            label_size=40,
            title=ft.Text(f"期間 ({bin_mode})"),
            title_size=14,
        ),
        top_axis=None,
        right_axis=None,
    )

    summary_row = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
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

        btn_inc.icon = ft.Icons.CHECK_BOX if show_inc else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_inc.style = ft.ButtonStyle(color=ft.Colors.GREEN if show_inc else ft.Colors.GREY)

        btn_exp.icon = ft.Icons.CHECK_BOX if show_exp else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_exp.style = ft.ButtonStyle(color=ft.Colors.ORANGE_ACCENT if show_exp else ft.Colors.GREY)

        btn_bal.icon = ft.Icons.CHECK_BOX if show_bal else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_bal.style = ft.ButtonStyle(color=ft.Colors.CYAN if show_bal else ft.Colors.GREY)

        # ----------------------------------------------------------------------
        # スケール（Min Y / Max Y）の計算（全取引データから厳密に計算）
        # ----------------------------------------------------------------------
        y_values = [0.0]
        if show_inc:
            for item in bar_inc_series:
                y_values.append(item["val"])
        if show_exp:
            for item in bar_exp_series:
                y_values.append(item["val"])
        if show_bal:
            y_values.extend([p["y"] for p in line_bal_points])

        raw_min_y = min(y_values)
        raw_max_y = max(y_values)
        y_interval, nice_min_y, nice_max_y = calculate_nice_interval(raw_min_y, raw_max_y, target_steps=5)

        chart.min_y = nice_min_y
        chart.max_y = nice_max_y
        chart.min_x = 0
        chart.max_x = bin_count

        chart.horizontal_grid_lines = fch.ChartGridLines(
            interval=y_interval,
            color=ft.Colors.with_opacity(0.12, ft.Colors.GREY),
            width=1,
        )

        # ----------------------------------------------------------------------
        # X軸目盛ラベル
        # ----------------------------------------------------------------------
        current_width = page.width if page.width else (page.window.width if page.window.width else 400)
        target_label_count = 4 if current_width < 500 else 7
        step = max(1, bin_count // target_label_count)

        chart_labels = []
        for item in labels_info:
            idx = item["value"]
            if idx % step == 0 or idx == bin_count - 1:
                chart_labels.append(
                    fch.ChartAxisLabel(
                        value=idx,
                        label=ft.Container(
                            margin=ft.Margin.only(top=10),
                            content=ft.Text(
                                item["text"],
                                size=9 if current_width < 500 else 10,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                    )
                )
        chart.bottom_axis.labels = chart_labels

        # ----------------------------------------------------------------------
        # 系列データ構築（Bal系列を最優先登録してツールチップ打ち消しを回避）
        # ----------------------------------------------------------------------
        series_list = []

        invisible_point = fch.ChartCirclePoint(
            radius=0,
            color=ft.Colors.TRANSPARENT,
        )

        # 【超重要】1. 収支（Balance）折れ線を「一番最初（インデックス0）」に追加
        # 先頭に置くことで、Flutter側のツールチップ評価エンジンが最優先でこのテキストを採用する
        if show_bal and line_bal_points:
            bal_data_points = [
                fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"])
                for p in line_bal_points
            ]
            series_list.append(
                fch.LineChartData(
                    bal_data_points,
                    color=ft.Colors.CYAN_ACCENT_400,
                    stroke_width=2.5 if current_width < 500 else 3.0,
                    point=invisible_point,
                    selected_point=fch.ChartCirclePoint(
                        radius=4.0,
                        color=ft.Colors.CYAN_ACCENT_100,
                    ),
                )
            )

        # 2. 収入の柱（Balの後に配置してツールチップを汚染させない）
        if show_inc:
            for item in bar_inc_series:
                pts = [fch.LineChartDataPoint(p["x"], p["y"], tooltip=None) for p in item["points"]]
                series_list.append(
                    fch.LineChartData(
                        pts,
                        color=ft.Colors.TRANSPARENT,
                        stroke_width=0,
                        below_line_bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.GREEN),
                        below_line_cutoff_y=0.0,
                        point=invisible_point,
                        selected_point=invisible_point,
                    )
                )

        # 3. 支出の柱（Balの後に配置してツールチップを汚染させない）
        if show_exp:
            for item in bar_exp_series:
                pts = [fch.LineChartDataPoint(p["x"], p["y"], tooltip=None) for p in item["points"]]
                series_list.append(
                    fch.LineChartData(
                        pts,
                        color=ft.Colors.TRANSPARENT,
                        stroke_width=0,
                        above_line_bgcolor=ft.Colors.with_opacity(0.40, ft.Colors.ORANGE_ACCENT),
                        above_line_cutoff_y=0.0,
                        point=invisible_point,
                        selected_point=invisible_point,
                    )
                )

        chart.data_series = series_list
        # ----------------------------------------------------------------------
        # 全体サマリー行の更新（全点から真の最高値・最低値を表示）
        # ----------------------------------------------------------------------
        summary_row.controls.clear()
        if show_bal and line_bal_points:
            vals = [p["y"] for p in line_bal_points]
            summary_row.controls.extend([
                ft.Text(f"Balance: ¥{vals[-1]:,.0f}", color=ft.Colors.CYAN, weight=ft.FontWeight.BOLD, size=11),
                ft.Text(f"Max: ¥{max(vals):,.0f}", color=ft.Colors.GREY_400, size=11),
                ft.Text(f"Min: ¥{min(vals):,.0f}", color=ft.Colors.GREY_400, size=11),
            ])

        if e:
            timeline_dialog.update()

    btn_inc = ft.TextButton("In", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="inc")
    btn_exp = ft.TextButton("Ex", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="exp")
    btn_bal = ft.TextButton("Bal", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="bal")

    button_row = ft.Row(
        controls=[btn_inc, btn_exp, btn_bal],
        alignment=ft.MainAxisAlignment.CENTER,
        wrap=True,
        spacing=5,
    )

    async def close_timeline(e: ft.ControlEvent):
        timeline_dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if timeline_dialog in page.overlay:
            page.overlay.remove(timeline_dialog)
            page.update()

    win_w = page.width if page.width else (page.window.width if page.window.width else 400)
    win_h = page.height if page.height else (page.window.height if page.window.height else 700)
    dialog_width = min(820, int(win_w * 0.95))
    dialog_height = min(560, int(win_h * 0.85))

    timeline_dialog = ft.AlertDialog(
        title=ft.Text("推移・収支分析", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=dialog_width,
            height=dialog_height,
            content=ft.Column(
                controls=[
                    button_row,
                    summary_row,
                    ft.Container(chart, expand=True, padding=ft.Padding.only(top=5, right=10)),
                ],
                spacing=4,
            ),
        ),
        actions=[
            ft.TextButton("閉じる", on_click=close_timeline),
        ],
    )

    page.overlay.append(timeline_dialog)
    timeline_dialog.open = True
    update_graph()
    page.update()