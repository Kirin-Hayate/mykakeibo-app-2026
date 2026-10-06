"""
ui/views/timeline_dialog.py

【このコードの目的・機能・挙動】
Analysis画面の「Timeline」アイコンを押した際に立ち上がる、日次収支の「累積推移グラフ」ダイアログです。
折れ線グラフ（LineChart）により、期間内の収入（Inc: 緑）、支出（Exp: 赤）、残高（Bal: シアン）の
累積推移を動的に切り替えて閲覧できます。

【旧コードからの完全な描画互換性・アルゴリズム】
1. X軸・Y軸のスケーリングと間引き:
   logic.aggregator.calculate_timeline_data() および calculate_nice_interval() と連携し、
   期間長に応じた日付ラベルの間引き（14日以内＝日毎、90日以内＝週毎、それ以上＝月毎）や、
   キリの良い金額インターバル（1, 2, 5 × 10^n）を算出してグリッド線と軸ラベルを設定します。
2. チェックボックスボタンによる系列表示切替:
   Inc, Exp, Bal の各ボタンをクリックすることで、表示対象の系列をトグルし、
   表示中の系列に合わせてY軸のスケールをリアルタイムに再計算して再描画します。
"""

import asyncio
from datetime import datetime
from typing import List, Any
import flet as ft
import flet_charts as fch

from logic.aggregator import calculate_timeline_data, calculate_nice_interval


def open_timeline_dialog(page: ft.Page, filtered_data_rows: List[List[Any]]) -> None:
    """
    推移グラフダイアログを構築して表示する。
    """
    if not filtered_data_rows:
        return

    # 集計ロジックを呼び出し、座標データを生成
    t_data = calculate_timeline_data(filtered_data_rows)
    if not t_data:
        return

    min_x = t_data["min_x"]
    max_x = t_data["max_x"]
    min_ts = t_data["min_ts"]
    x_interval = t_data["x_interval"]
    date_fmt = t_data["date_fmt"]

    # 折れ線グラフ用データポイントの変換
    data_inc = [fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"]) for p in t_data["points_inc"]]
    data_exp = [fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"]) for p in t_data["points_exp"]]
    data_bal = [fch.LineChartDataPoint(p["x"], p["y"], tooltip=p["tooltip"]) for p in t_data["points_bal"]]

    # 表示切替ステート（初期値: Bal のみ表示）
    show_inc = False
    show_exp = False
    show_bal = True

    chart = fch.LineChart(
        expand=True,
        border=ft.Border.all(1, ft.Colors.GREY_800),
        left_axis=fch.ChartAxis(
            label_size=50,
            title=ft.Text("金額 (¥)"),
            title_size=20,
        ),
        bottom_axis=fch.ChartAxis(
            label_size=40,
            title=ft.Text("日付"),
            title_size=20,
        ),
    )
    summary_col = ft.Column()

    def update_graph(e: ft.ControlEvent = None):
        """トグルボタンの状態に合わせてグラフとサマリーテキストを更新"""
        nonlocal show_inc, show_exp, show_bal

        if e:
            if e.control.data == "inc":
                show_inc = not show_inc
            elif e.control.data == "exp":
                show_exp = not show_exp
            elif e.control.data == "bal":
                show_bal = not show_bal

        # ボタンの見た目更新
        btn_inc.icon = ft.Icons.CHECK_BOX if show_inc else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_inc.style = ft.ButtonStyle(color=ft.Colors.GREEN if show_inc else ft.Colors.GREY)

        btn_exp.icon = ft.Icons.CHECK_BOX if show_exp else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_exp.style = ft.ButtonStyle(color=ft.Colors.RED if show_exp else ft.Colors.GREY)

        btn_bal.icon = ft.Icons.CHECK_BOX if show_bal else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        btn_bal.style = ft.ButtonStyle(color=ft.Colors.CYAN if show_bal else ft.Colors.GREY)

        line_series = []
        all_visible_points = []

        if show_inc and data_inc:
            line_series.append(fch.LineChartData(data_inc, color=ft.Colors.GREEN, stroke_width=3))
            all_visible_points.extend(data_inc)
        if show_exp and data_exp:
            line_series.append(fch.LineChartData(data_exp, color=ft.Colors.RED, stroke_width=3))
            all_visible_points.extend(data_exp)
        if show_bal and data_bal:
            line_series.append(fch.LineChartData(data_bal, color=ft.Colors.CYAN, stroke_width=3))
            all_visible_points.extend(data_bal)

        # Y軸のキリの良い目盛り計算
        if all_visible_points:
            vals = [p.y for p in all_visible_points]
            raw_min_y, raw_max_y = min(vals), max(vals)
        else:
            raw_min_y, raw_max_y = 0.0, 100.0

        y_interval, nice_min_y, nice_max_y = calculate_nice_interval(raw_min_y, raw_max_y, target_steps=5)

        chart.min_y = nice_min_y
        chart.max_y = nice_max_y
        chart.min_x = 0
        chart.max_x = max_x - min_x
        chart.data_series = line_series

        # X軸ラベルの動的生成
        labels = []
        curr_rel_x = 0
        while curr_rel_x <= (max_x - min_x):
            dt_obj = datetime.fromtimestamp(min_ts + curr_rel_x)
            labels.append(
                fch.ChartAxisLabel(
                    value=curr_rel_x,
                    label=ft.Container(
                        margin=ft.Margin.only(top=10),
                        content=ft.Text(dt_obj.strftime(date_fmt), size=10, weight=ft.FontWeight.BOLD)
                    )
                )
            )
            curr_rel_x += x_interval

        chart.bottom_axis.labels = labels
        chart.vertical_grid_lines = fch.ChartGridLines(
            interval=x_interval,
            color=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
            width=1
        )
        chart.horizontal_grid_lines = fch.ChartGridLines(
            interval=y_interval,
            color=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
            width=1
        )

        # サマリー情報の構築
        summary_col.controls.clear()
        if show_bal and data_bal:
            vals = [p.y for p in data_bal]
            summary_col.controls.append(
                ft.Row([
                    ft.Text("Balance: ", color=ft.Colors.CYAN, weight=ft.FontWeight.BOLD),
                    ft.Text(f"\nCurrent ¥{vals[-1]:,.0f} \nMax ¥{max(vals):,.0f} \nMin ¥{min(vals):,.0f}", size=12)
                ], spacing=5)
            )

        if e:
            timeline_dialog.update()

    btn_inc = ft.TextButton("Inc", icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK, on_click=update_graph, data="inc")
    btn_exp = ft.TextButton("Exp", icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK, on_click=update_graph, data="exp")
    btn_bal = ft.TextButton("Bal", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="bal")

    async def close_timeline(e: ft.ControlEvent):
        timeline_dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if timeline_dialog in page.overlay:
            page.overlay.remove(timeline_dialog)
            page.update()

    timeline_dialog = ft.AlertDialog(
        title=ft.Text("推移グラフ"),
        content=ft.Container(
            width=700,
            height=500,
            content=ft.Column([
                ft.Row([btn_inc, btn_exp, btn_bal], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                summary_col,
                ft.Container(chart, expand=True, padding=10)
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