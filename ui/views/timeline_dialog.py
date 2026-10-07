"""
ui/views/timeline_dialog.py

【このコードの目的・機能・挙動】
Analysis画面の「Timeline」ダイアログモジュールです。
BarChartを完全撤廃し、単一のLineChartに統合したアーキテクチャです。
- 支出: X軸（0円ライン）から下へ伸びる半透明オレンジ色のステップ面
- 収入: X軸（0円ライン）から上へ伸びる半透明緑色のステップ面
- 収支(Balance): 最前面を横断するシアン色の累積折れ線グラフ

【単一チャート化による利点】
1. 座標の完全一致: 同一キャンバスのため、X軸・Y軸の原点・端点・境界線が100%一致。
2. ラベル重複の根絶: 軸が1組しか存在しないため、数字や日付の二重描画が発生しない。
3. レスポンシブ完全自動対応: 端末の画面幅変化にFlutter描画エンジンが自動追従。
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

    step_inc_points = t_data["step_inc_points"]
    step_exp_points = t_data["step_exp_points"]
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
        left_axis=fch.ChartAxis(
            label_size=55,
            title=ft.Text("金額 (¥)"),
            title_size=14
        ),
        bottom_axis=fch.ChartAxis(
            label_size=40,
            title=ft.Text(f"期間 ({bin_mode})"),
            title_size=14
        ),
        top_axis=None,
        right_axis=None,
    )

    summary_row = ft.Row(
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

        btn_inc.icon = ft.Icons.CHECK_BOX if show_inc else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_inc.style = ft.ButtonStyle(color=ft.Colors.GREEN if show_inc else ft.Colors.GREY)

        btn_exp.icon = ft.Icons.CHECK_BOX if show_exp else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_exp.style = ft.ButtonStyle(color=ft.Colors.ORANGE_ACCENT if show_exp else ft.Colors.GREY)

        btn_bal.icon = ft.Icons.CHECK_BOX if show_bal else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_bal.style = ft.ButtonStyle(color=ft.Colors.CYAN if show_bal else ft.Colors.GREY)

        # ----------------------------------------------------------------------
        # スケール（Min Y / Max Y）の計算
        # ----------------------------------------------------------------------
        y_values = [0.0]
        if show_inc:
            y_values.extend([p["y"] for p in step_inc_points])
        if show_exp:
            y_values.extend([p["y"] for p in step_exp_points])
        if show_bal:
            y_values.extend([p["y"] for p in line_bal_points])

        raw_min_y = min(y_values)
        raw_max_y = max(y_values)
        y_interval, nice_min_y, nice_max_y = calculate_nice_interval(raw_min_y, raw_max_y, target_steps=5)

        chart.min_y = nice_min_y
        chart.max_y = nice_max_y
        chart.min_x = 0
        chart.max_x = bin_count

        # 横グリッド線
        chart.horizontal_grid_lines = fch.ChartGridLines(
            interval=y_interval,
            color=ft.Colors.with_opacity(0.12, ft.Colors.GREY),
            width=1
        )

        # ----------------------------------------------------------------------
        # X軸目盛ラベル（期間境界に正確に配置）
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
                                weight=ft.FontWeight.BOLD
                            )
                        )
                    )
                )
        chart.bottom_axis.labels = chart_labels

        # ----------------------------------------------------------------------
        # 系列データ構築（背面: 収入・支出の面塗り、前面: 収支の折れ線）
        # ----------------------------------------------------------------------
        series_list = []

        # 1. 収入の柱（緑の面塗り）
        if show_inc and step_inc_points:
            inc_data_points = [
                fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"])
                for p in step_inc_points
            ]
            series_list.append(
                fch.LineChartData(
                    inc_data_points,
                    color=ft.Colors.with_opacity(0.40, ft.Colors.GREEN),
                    stroke_width=1,
                    below_line_bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.GREEN),
                )
            )

        # 2. 支出の柱（オレンジの面塗り）
        if show_exp and step_exp_points:
            exp_data_points = [
                fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"])
                for p in step_exp_points
            ]
            series_list.append(
                fch.LineChartData(
                    exp_data_points,
                    color=ft.Colors.with_opacity(0.40, ft.Colors.ORANGE_ACCENT),
                    stroke_width=1,
                    above_line_bgcolor=ft.Colors.with_opacity(0.40, ft.Colors.ORANGE_ACCENT),
                )
            )

        # 3. 収支（Balance）折れ線（最前面）
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
                )
            )

        chart.data_series = series_list

        # ----------------------------------------------------------------------
        # サマリー情報更新
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

    btn_inc = ft.TextButton("Income (面)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="inc")
    btn_exp = ft.TextButton("Expense (面)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="exp")
    btn_bal = ft.TextButton("Balance (線)", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="bal")

    button_row = ft.Row(
        controls=[btn_inc, btn_exp, btn_bal],
        alignment=ft.MainAxisAlignment.CENTER,
        wrap=True,
        spacing=5
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
    dialog_width = min(800, int(win_w * 0.95))
    dialog_height = min(560, int(win_h * 0.85))

    timeline_dialog = ft.AlertDialog(
        title=ft.Text("推移・収支分析", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=dialog_width,
            height=dialog_height,
            content=ft.Column([
                button_row,
                summary_row,
                ft.Container(chart, expand=True, padding=ft.Padding.only(top=5, right=10))
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