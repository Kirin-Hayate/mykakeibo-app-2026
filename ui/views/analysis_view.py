"""
ui/views/analysis_view.py

【このコードの目的・機能・挙動】
家計簿の「Analysis（分析・一覧）」画面全体を構築・制御するメインビューモジュールです。

【旧コードからの改善点・機能・動作原理】
1. セッション単位の非同期タスク管理（マルチユーザー安全性）:
   旧コードでは global current_scroll_task が使われており、複数ブラウザから接続した際に
   他ユーザーのスクロールが誤ってキャンセルされる競合不具合がありました。
   本モジュールでは state.current_scroll_task（AppState）に保持することで、
   Web公開時や複数端末接続時でも完全に独立してスムーズな仮想スクロールを実現します。
2. インクリメンタルスクロール（逐次読み込み）:
   100件ずつのバッチ読み込みを行い、スクロール端（末尾100px以内）に達した際に
   ローディングインジケーターを表示しながら次の100件をコントロールとして追加します。
   10件ごとの一瞬のスリープ（await asyncio.sleep(0)）により、UIのブロッキングを防ぎます。
3. 高度な絞り込み（Filterダイアログ）:
   モード、カテゴリ（複数選択チェックボックス）、キーワード（スペース区切りOR検索）、
   日付範囲（from〜to）、金額範囲（min〜max）の全条件を管理し、適用時には
   アクティブな条件を太字の白文字（非アクティブは灰色）でインジケーター表示します。
4. 各種分析ダイアログおよび明細編集ダイアログとの連携:
   ツールバー上の「Filter」「Breakdown（内訳半円グラフ）」「Timeline（推移グラフ）」
   「Reload（スプシ再読込）」、および各行の「EDIT」ボタンから、ステップ3で作成した
   各ダイアログを独立して呼び出します。
"""

import asyncio
from typing import List, Callable, Coroutine, Any
import flet as ft

from ui.state import AppState
from ui.components.loading import create_loading_indicator
from ui.views.edit_dialog import open_edit_dialog
from ui.views.report_dialog import open_detailed_report_dialog
from ui.views.timeline_dialog import open_timeline_dialog
from services.sheets_service import sheets_service
from logic.filter_sort import filter_records, sort_records
from logic.aggregator import calculate_summary


async def build_analysis_view(
    page: ft.Page,
    state: AppState,
    on_refresh_needed: Callable[[], Coroutine[Any, Any, None]]
) -> List[ft.Control]:
    """
    Analysis（明細一覧・分析）画面の全UIコントロール群を生成して返す非同期関数。

    引数:
        page: 現在のFletページオブジェクト
        state: セッション個別のアプリケーション状態（AppState）
        on_refresh_needed: データ更新や再読み込み時に画面再描画を要求するコールバック
    戻り値:
        List[ft.Control]: 画面に追加するウィジェットリスト
    """
    view_controls: List[ft.Control] = []
    loading_ind = create_loading_indicator("データ読み込み中...")

    # --------------------------------------------------------------------------
    # 1. スプレッドシートからのデータ取得と前処理
    # --------------------------------------------------------------------------
    # sheets_service が内部でキャッシュを保持しているため、通信不要時は即座に返る
    raw_data = await asyncio.to_thread(sheets_service.get_all_records)
    if not raw_data or len(raw_data) < 2:
        return [ft.Text("明細データが存在しません", color="grey", size=14)]

    # 1行目はヘッダー、2行目以降がデータ
    data_rows = raw_data[1:]

    # フィルタ条件の適用（logic.filter_sort）
    state.filtered_data_rows = filter_records(data_rows, state.filter_query)

    # --------------------------------------------------------------------------
    # 2. フィルタ状態表示バーの生成（条件が有効な項目だけ白文字で強調）
    # --------------------------------------------------------------------------
    def get_filter_style(value: Any) -> ft.TextStyle:
        return ft.TextStyle(color="white", weight=ft.FontWeight.BOLD) if value else ft.TextStyle(color="grey600")

    q = state.filter_query
    mode_text = q[0] if q[0] else "All"
    cats_text = ",".join(q[1]) if q[1] else "All"
    kw_text = q[2] if q[2] else "None"
    date_text = f"{q[3] or 'min'}~{q[4] or 'max'}"
    amt_text = f"{q[6] or 'min'}~{q[5] or 'max'}"

    filtering_message = ft.Text(
        spans=[
            ft.TextSpan(f"[mode]:{mode_text} ", style=get_filter_style(q[0])),
            ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
            ft.TextSpan(f"[category]:{cats_text} ", style=get_filter_style(q[1])),
            ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
            ft.TextSpan(f"[keyword]:{kw_text} ", style=get_filter_style(q[2])),
            ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
            ft.TextSpan(f"[date]:{date_text} ", style=get_filter_style(q[3] or q[4])),
            ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
            ft.TextSpan(f"[amount]:{amt_text}", style=get_filter_style(q[5] or q[6])),
        ],
        size=11
    )

    # --------------------------------------------------------------------------
    # 3. 絞り込み条件入力ダイアログ（Filter Dialog）
    # --------------------------------------------------------------------------
    async def open_filter_dialog():
        # プルダウン: モード
        mode_dd = ft.Dropdown(
            label="",
            options=[
                ft.dropdown.Option(key="", text="指定なし"),
                ft.dropdown.Option("Expense"),
                ft.dropdown.Option("Income")
            ],
            width=110,
            text_size=12,
            value=state.filter_query[0] or ""
        )

        # カテゴリ複数選択
        all_cat_options = sorted(list(set(state.expense_categories + state.income_categories)))
        initial_cats = state.filter_query[1] if isinstance(state.filter_query[1], list) else []
        selected_cats = set(initial_cats)

        cat_status_text = ft.Text(
            value=",".join(sorted(list(selected_cats))) if selected_cats else "指定なし",
            size=12,
            color="white" if selected_cats else "grey",
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True
        )

        def on_cat_checkbox_change(e: ft.ControlEvent):
            if e.control.value:
                selected_cats.add(e.control.label)
            else:
                selected_cats.discard(e.control.label)

        def close_cat_selector(e: ft.ControlEvent):
            cat_selector_dialog.open = False
            cat_status_text.value = ",".join(sorted(list(selected_cats))) if selected_cats else "指定なし"
            cat_status_text.color = "white" if selected_cats else "grey"
            filter_dialog.open = True
            page.update()

        cat_selector_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("カテゴリを選択"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Checkbox(
                            label=c,
                            value=(c in selected_cats),
                            on_change=on_cat_checkbox_change
                        ) for c in all_cat_options
                    ],
                    scroll=ft.ScrollMode.AUTO
                ),
                height=300,
                width=250
            ),
            actions=[ft.TextButton("完了", on_click=close_cat_selector)]
        )

        def open_cat_selector(e: ft.ControlEvent):
            col = cat_selector_dialog.content.content
            for cb in col.controls:
                cb.value = (cb.label in selected_cats)
            if cat_selector_dialog not in page.overlay:
                page.overlay.append(cat_selector_dialog)
            cat_selector_dialog.open = True
            page.update()

        cat_select_btn = ft.Button("選択", on_click=open_cat_selector, height=30, style=ft.ButtonStyle(padding=5))

        keyword_tf = ft.TextField(label="keyword", expand=True, text_size=12, value=state.filter_query[2] or "")
        oldest_date_tf = ft.TextField(label="date (from)", hint_text="YYYY-MM-DD", width=110, text_size=12, value=state.filter_query[3] or "")
        latest_date_tf = ft.TextField(label="date (to)", hint_text="YYYY-MM-DD", width=110, text_size=12, value=state.filter_query[4] or "")

        max_val_str = str(state.filter_query[5]) if state.filter_query[5] is not None else ""
        min_val_str = str(state.filter_query[6]) if state.filter_query[6] is not None else ""
        max_amt_tf = ft.TextField(label="amount (max)", width=110, text_size=12, value=max_val_str)
        min_amt_tf = ft.TextField(label="amount (min)", width=110, text_size=12, value=min_val_str)

        async def on_apply(e: ft.ControlEvent):
            state.filter_query[0] = mode_dd.value if mode_dd.value and mode_dd.value != "指定なし" else None
            state.filter_query[1] = sorted(list(selected_cats)) if selected_cats else None
            state.filter_query[2] = keyword_tf.value.strip() if keyword_tf.value and keyword_tf.value.strip() else None
            state.filter_query[3] = oldest_date_tf.value.strip() if oldest_date_tf.value and oldest_date_tf.value.strip() else None
            state.filter_query[4] = latest_date_tf.value.strip() if latest_date_tf.value and latest_date_tf.value.strip() else None

            try:
                state.filter_query[5] = float(max_amt_tf.value.strip()) if max_amt_tf.value and max_amt_tf.value.strip() else None
            except ValueError:
                state.filter_query[5] = None

            try:
                state.filter_query[6] = float(min_amt_tf.value.strip()) if min_amt_tf.value and min_amt_tf.value.strip() else None
            except ValueError:
                state.filter_query[6] = None

            filter_dialog.open = False
            page.update()
            await asyncio.sleep(0.1)
            if filter_dialog in page.overlay:
                page.overlay.remove(filter_dialog)
            await on_refresh_needed()

        def on_clear(e: ft.ControlEvent):
            mode_dd.value = ""
            selected_cats.clear()
            cat_status_text.value = "指定なし"
            cat_status_text.color = "grey"
            keyword_tf.value = ""
            oldest_date_tf.value = ""
            latest_date_tf.value = ""
            max_amt_tf.value = ""
            min_amt_tf.value = ""
            page.update()

        async def close_filter_dialog(e: ft.ControlEvent):
            filter_dialog.open = False
            page.update()
            await asyncio.sleep(0.1)
            if filter_dialog in page.overlay:
                page.overlay.remove(filter_dialog)
            page.update()

        filter_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Text("絞り込み条件", size=16, weight=ft.FontWeight.BOLD),
                    ft.TextButton("All Clear", icon=ft.Icons.CLEAR_ALL, on_click=on_clear, style=ft.ButtonStyle(color="red"))
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            content=ft.Column(
                controls=[
                    ft.Row([ft.Text("mode:"), mode_dd], alignment=ft.MainAxisAlignment.START),
                    ft.Row([ft.Text("category:"), cat_select_btn, cat_status_text], alignment=ft.MainAxisAlignment.START),
                    ft.Row([ft.Text("keyword:"), keyword_tf], spacing=10),
                    ft.Row([ft.Text("date  :", size=12), oldest_date_tf, ft.Text("～"), latest_date_tf], spacing=5),
                    ft.Row([ft.Text("amount:", size=12), min_amt_tf, ft.Text("～"), max_amt_tf], spacing=5),
                ],
                tight=True,
                spacing=20
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=close_filter_dialog),
                ft.Button("絞り込み", icon=ft.Icons.FILTER_ALT, on_click=on_apply),
            ]
        )

        page.overlay.append(filter_dialog)
        filter_dialog.open = True
        page.update()

    # --------------------------------------------------------------------------
    # 4. 上部アクションバー（Filter / Breakdown / Timeline / Reload）
    # --------------------------------------------------------------------------
    async def on_reload_clicked(e: ft.ControlEvent):
        # キャッシュを破棄してスプレッドシートから再読み込み
        sheets_service.invalidate_cache()
        await on_refresh_needed()

    action_bar = ft.Row(
        controls=[
            ft.IconButton(icon=ft.Icons.MANAGE_SEARCH, icon_size=25, on_click=lambda _: page.run_task(open_filter_dialog), tooltip="絞り込み条件を開く"),
            ft.Text("Filter", size=10, weight=ft.FontWeight.BOLD),
            ft.IconButton(icon=ft.Icons.PIE_CHART, icon_size=25, on_click=lambda _: open_detailed_report_dialog(page, state.filtered_data_rows), tooltip="詳細な分析を開く"),
            ft.Text("Breakdown", size=10, weight=ft.FontWeight.BOLD),
            ft.IconButton(icon=ft.Icons.SHOW_CHART, icon_size=25, on_click=lambda _: open_timeline_dialog(page, state.filtered_data_rows), tooltip="推移を表示"),
            ft.Text("Timeline", size=10, weight=ft.FontWeight.BOLD),
            ft.IconButton(icon=ft.Icons.REFRESH, icon_size=25, on_click=on_reload_clicked, tooltip="データを再読み込み"),
            ft.Text("Reload", size=10, weight=ft.FontWeight.BOLD),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=5
    )

    # --------------------------------------------------------------------------
    # 5. 収支サマリーカード（Expense, Income, 収支）
    # --------------------------------------------------------------------------
    total_exp, total_inc, balance = calculate_summary(state.filtered_data_rows)
    balance_color = "green" if balance >= 0 else "orange"

    summary_card = ft.Container(
        content=ft.Row(
            controls=[
                ft.Column([
                    ft.Text("Expense", size=12, color="grey500"),
                    ft.Text(f"{total_exp:,.0f}", color="orange", weight=ft.FontWeight.BOLD, size=16),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                ft.Column([
                    ft.Text("Income", size=12, color="grey500"),
                    ft.Text(f"+{total_inc:,.0f}", color="green", weight=ft.FontWeight.BOLD, size=16),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                ft.Text("=", size=20, color="grey500"),
                ft.Column([
                    ft.Text("収支", size=12, color="grey500"),
                    ft.Text(f"{balance:,.0f}", size=16, weight=ft.FontWeight.BOLD, color=balance_color),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=10,
        bgcolor=ft.Colors.GREY_900,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.GREY_800),
    )

    # --------------------------------------------------------------------------
    # 6. 一覧テーブルおよびインクリメンタルスクロール構築
    # --------------------------------------------------------------------------
    # ソートの適用
    state.filtered_data_rows = sort_records(state.filtered_data_rows, state.sort_column_index, state.sort_ascending)

    current_display_count = 100
    now_loading_next100 = False

    def create_row_item(row: List[Any]) -> ft.Container:
        """明細1行分のコンテナウィジェットを生成"""
        row_color = ft.Colors.ORANGE_ACCENT if len(row) > 1 and row[1] == "Expense" else ft.Colors.GREEN_400
        try:
            amt_num = float(row[2]) if len(row) > 2 and row[2] != "" else 0.0
            amt_formatted = f"{amt_num:,.0f}"
        except ValueError:
            amt_formatted = str(row[2])

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(str(row[0]), width=75, size=11, color=row_color),
                    ft.Text(str(row[3]), width=70, size=11, color=row_color, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(amt_formatted, width=60, size=11, color=row_color, text_align="right"),
                    ft.Text(str(row[4]), expand=True, size=11, color=row_color, no_wrap=False),
                    ft.TextButton(
                        content=ft.Text("EDIT", size=10, weight=ft.FontWeight.W_400, color=ft.Colors.GREY_500),
                        on_click=lambda _: page.run_task(open_edit_dialog, page, state, row, on_refresh_needed)
                    ),
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.START
            ),
            padding=ft.Padding.symmetric(vertical=5, horizontal=5),
            border=ft.Border(bottom=ft.BorderSide(0.5, ft.Colors.GREY_800))
        )

    # スクロール検知ハンドラ（セッション個別のタスク管理）
    async def on_scroll(e: ft.OnScrollEvent):
        nonlocal current_display_count, now_loading_next100

        # すでに実行中のスクロールタスクがあればキャンセル
        if state.current_scroll_task is not None and not state.current_scroll_task.done():
            state.current_scroll_task.cancel()
            try:
                await state.current_scroll_task
            except asyncio.CancelledError:
                pass

        async def scroll_logic():
            nonlocal current_display_count, now_loading_next100
            # 末尾100px以内に到達したとき次のバッチを追加
            if e.pixels >= e.max_scroll_extent - 100 and not now_loading_next100:
                if current_display_count < len(state.filtered_data_rows):
                    now_loading_next100 = True
                    next_batch = state.filtered_data_rows[current_display_count : current_display_count + 100]

                    new_controls = []
                    for i, r in enumerate(next_batch):
                        if i % 10 == 0:
                            await asyncio.sleep(0)  # UIブロッキング防止
                        new_controls.append(create_row_item(r))

                    list_view.controls.extend(new_controls)
                    current_display_count += 100
                    list_view.update()
                    now_loading_next100 = False

        state.current_scroll_task = asyncio.create_task(scroll_logic())

    # 初回100件のリストビュー
    list_view = ft.ListView(
        expand=True,
        spacing=0,
        controls=[create_row_item(r) for r in state.filtered_data_rows[:100]],
        on_scroll=on_scroll,
        scroll_interval=100
    )

    table_header = ft.Container(
        bgcolor=ft.Colors.GREY_900,
        content=ft.Row(
            controls=[
                ft.Text("日付", width=75, size=12, weight=ft.FontWeight.BOLD),
                ft.Text("カテゴリ", width=70, size=12, weight=ft.FontWeight.BOLD),
                ft.Text("金額", width=60, size=12, weight=ft.FontWeight.BOLD, text_align="right"),
                ft.Text("内容", expand=True, size=12, weight=ft.FontWeight.BOLD),
                ft.Text(" ", width=50),
            ],
            spacing=5
        ),
        padding=ft.Padding.symmetric(vertical=10, horizontal=5),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_700))
    )

    data_table_column = ft.Column(
        controls=[table_header, list_view],
        expand=True
    )

    # 画面コントロールの構成
    view_controls.extend([
        action_bar,
        filtering_message,
        summary_card,
        data_table_column
    ])

    return view_controls