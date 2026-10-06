"""
ui/views/report_dialog.py

【このコードの目的・機能・挙動】
Analysis画面の「Breakdown」アイコンを押した際に表示される「収支内訳レポート」ダイアログです。
現在フィルタされている明細から支出・収入それぞれのカテゴリ構成比を集計し、
「半円ドーナツグラフ（PieChart）」と「順位・割合・金額一覧テーブル（DataTable）」を並べて可視化します。

【旧コードからの完全な描画互換性・アルゴリズム】
1. 半円チャートの描画トリック:
   PieChart に合計値と同じサイズの透明セクション（ft.Colors.TRANSPARENT）を追加し、
   start_degree_offset=180（時計の9時の位置）から時計回りに配置することで、
   画面上半分だけにデータセクションを表示させ、下半分を透明にして閉じる独自描画を維持しています。
2. 集計ロジックの分離:
   ロジック層（logic.aggregator.calculate_category_breakdown）を利用してデータを前処理し、
   UI構築コードの見通しを向上させています。
"""

import asyncio
from typing import List, Tuple, Any
import flet as ft
import flet_charts as fch

from logic.aggregator import calculate_category_breakdown


def open_detailed_report_dialog(page: ft.Page, filtered_data_rows: List[List[Any]]) -> None:
    """
    収支内訳（半円円グラフ＋テーブル）ダイアログを構築して表示する。
    """
    # 支出・収入それぞれのカテゴリ別合計を降順で取得
    sorted_expense, sorted_income = calculate_category_breakdown(filtered_data_rows)

    def create_semicircle_chart_and_table(
        sorted_data: List[Tuple[str, float]],
        is_expense: bool = True
    ) -> ft.Control:
        """
        指定された集計データから半円グラフとテーブルを生成する内部関数
        """
        if not sorted_data:
            return ft.Text("データなし", size=12, color="grey")

        total_val = sum(v for _, v in sorted_data)
        total_color = "orange" if is_expense else "green"
        total_text = f"-¥{total_val:,.0f}" if is_expense else f"¥{total_val:,.0f}"

        # グラフ用カラーパレット
        palette = [
            ft.Colors.BLUE, ft.Colors.RED, ft.Colors.GREEN,
            ft.Colors.AMBER, ft.Colors.PURPLE, ft.Colors.CYAN,
            ft.Colors.ORANGE, ft.Colors.TEAL, ft.Colors.PINK
        ]

        sections = []
        table_rows = []

        for i, (cat, val) in enumerate(sorted_data):
            rank = i + 1
            percentage = (val / total_val) * 100 if total_val > 0 else 0
            color = palette[i % len(palette)]

            # グラフセクション（順位番号のみ中央に白文字表示）
            sections.append(
                fch.PieChartSection(
                    value=val,
                    title=str(rank),
                    color=color,
                    radius=50,
                    title_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD, color="white"),
                )
            )

            # テーブル行（順位バッジ、カテゴリ名、比率%、金額）
            table_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(str(rank), color="white", size=9, weight=ft.FontWeight.BOLD),
                                bgcolor=color,
                                border_radius=10,
                                width=16,
                                height=16,
                                alignment=ft.Alignment(0, 0)
                            )
                        ),
                        ft.DataCell(ft.Text(cat, size=12)),
                        ft.DataCell(ft.Text(f"{percentage:.1f}%", size=12)),
                        ft.DataCell(ft.Text(f"¥{val:,.0f}", size=12)),
                    ]
                )
            )

        # 半円にするための下半分ダミーセクション（透明）
        sections.append(
            fch.PieChartSection(
                value=total_val,
                title="",
                color=ft.Colors.TRANSPARENT,
                radius=50
            )
        )

        # 円グラフの構築（9時位置＝180度からスタート）
        chart = fch.PieChart(
            sections=sections,
            sections_space=0,
            center_space_radius=40,
            start_degree_offset=180,
            expand=True
        )

        # チャート中心に合計金額を配置するためのStack
        chart_stack = ft.Stack(
            controls=[
                chart,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Total", size=10, color="grey"),
                            ft.Text(total_text, size=14, weight=ft.FontWeight.BOLD, color=total_color)
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=ft.Padding.only(bottom=10)
                )
            ],
            alignment=ft.Alignment(0, 0)
        )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("順位")),
                ft.DataColumn(ft.Text("カテゴリ")),
                ft.DataColumn(ft.Text("割合")),
                ft.DataColumn(ft.Text("金額")),
            ],
            rows=table_rows,
            heading_row_height=0,
            data_row_min_height=18,
            column_spacing=10
        )

        # 下半分の余白を削ってテーブルとの間隔を詰める
        return ft.Column(
            controls=[
                ft.Container(
                    chart_stack,
                    height=180,
                    alignment=ft.Alignment(0, 0),
                    margin=ft.Margin.only(top=0, bottom=-70)
                ),
                table
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )

    expense_content = create_semicircle_chart_and_table(sorted_expense, is_expense=True)
    income_content = create_semicircle_chart_and_table(sorted_income, is_expense=False)

    async def close_report(e: ft.ControlEvent):
        report_dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if report_dialog in page.overlay:
            page.overlay.remove(report_dialog)
            page.update()

    report_dialog = ft.AlertDialog(
        title=ft.Text("収支内訳レポート"),
        content=ft.Container(
            width=900,
            height=500,
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=220,
                        content=ft.Column(
                            controls=[
                                ft.Text("支出の内訳", color="orange", weight=ft.FontWeight.BOLD),
                                expense_content,
                            ],
                            scroll=ft.ScrollMode.AUTO
                        )
                    ),
                    ft.VerticalDivider(width=1, color="grey"),
                    ft.Container(
                        width=220,
                        content=ft.Column(
                            controls=[
                                ft.Text("収入の内訳", color="green", weight=ft.FontWeight.BOLD),
                                income_content,
                            ],
                            scroll=ft.ScrollMode.AUTO
                        )
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                vertical_alignment=ft.CrossAxisAlignment.START
            )
        ),
        actions=[
            ft.TextButton("閉じる", on_click=close_report)
        ]
    )

    page.overlay.append(report_dialog)
    report_dialog.open = True
    page.update()