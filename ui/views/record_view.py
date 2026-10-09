"""
ui/views/record_view.py

【このコードの目的・機能・挙動】
家計簿のメイン入力画面（Expense: 支出入力、Income: 収入入力）を構築するビューモジュールです。

【旧コードからの外観・機能・動作の完全互換性】
- 日付選択: DatePickerによりカレンダーから日付を選択。JST基準の日時フォーマット（YYYY-MM-DD）で保持。
- 金額入力: 枠線色 bluegrey900 / blue400、数値キーボード指定、Expense時は自動で負の値へ反転。
- カテゴリ選択: 横スクロール可能な単一選択 Chip 列。
- メモ入力: 複数行対応のテキストフィールド。
- 簡易電卓: 式を入力して計算ボタンを押すと、safe_calculate() により安全に四則演算を評価・表示。
- スプシ保存: レコード（日付, モード, 金額, カテゴリ, メモ, タイムスタンプ, UUID）を生成し、
  asyncio.to_thread 経由で sheets_service.add_record を呼び出し非同期保存。
"""

import asyncio
import uuid
from datetime import datetime
from typing import List
import flet as ft

from config.settings import JST
from ui.state import AppState
from ui.views.category_dialog import open_category_settings_dialog
from services.sheets_service import sheets_service
from logic.calculator import safe_calculate


def build_record_view(page: ft.Page, state: AppState) -> List[ft.Control]:
    """
    Expense または Income 入力画面の全コントロールリストを生成して返す。
    
    引数:
        page: 現在のFletページオブジェクト
        state: セッション個別のアプリケーション状態
    戻り値:
        List[ft.Control]: page.add() 等で追加可能なUIコントロール群
    """
    # --------------------------------------------------------------------------
    # 1. 日付管理（JST基準）
    # --------------------------------------------------------------------------
    # 初期値は現在の日本時間
    now_jst = datetime.now(JST)
    selected_date_str = now_jst.strftime("%Y-%m-%d")

    # 日付表示ラベル
    date_label = ft.Text(f"date: {selected_date_str}", color="white", weight=ft.FontWeight.BOLD, size=20)

    async def handle_date_change(e: ft.ControlEvent):
        """DatePickerで日付が選ばれたときのイベントハンドラ（JST変換による1日ズレ防止）"""
        nonlocal selected_date_str
        val = e.control.value
        if val:
            if isinstance(val, str):
                # ISOフォーマット文字列で渡ってきた場合
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            else:
                dt = val

            # タイムゾーンが未設定（naive）またはUTCの場合はJSTに揃える
            if dt.tzinfo is None:
                # Flutterから0:00として届いたnaive datetimeをJST化
                dt = dt.replace(tzinfo=JST)
            else:
                # UTC等のタイムゾーンがついている場合はJSTへ変換
                dt = dt.astimezone(JST)

            selected_date_str = dt.strftime("%Y-%m-%d")
            date_label.value = f"date: {selected_date_str}"
            page.update()

    # カレンダーピッカー
    date_picker = ft.DatePicker(
        on_change=handle_date_change,
        value=now_jst,
        first_date=datetime(2000, 1, 1),
        last_date=datetime(3000, 12, 31)
    )
    if date_picker not in page.overlay:
        page.overlay.append(date_picker)

    async def open_date_picker(e: ft.ControlEvent):
        date_picker.open = True
        page.update()

    dateselect_button = ft.Button(
        "日付の変更",
        icon=ft.Icons.CALENDAR_MONTH,
        on_click=open_date_picker
    )

    # --------------------------------------------------------------------------
    # 2. 金額・カテゴリ・メモ入力コンポーネント
    # --------------------------------------------------------------------------
    amount_input = ft.TextField(
        label="金額",
        prefix=ft.Text("¥"),
        keyboard_type=ft.KeyboardType.NUMBER,
        border_color="bluegrey900",
        focused_border_color="blue400"
    )

    # 操作結果・バリデーションエラー表示用ラベル
    status_label = ft.Text("", color="green", weight=ft.FontWeight.BOLD)

    # カテゴリチップ列の構築用コンテナ
    category_chips_row = ft.Row(
        scroll=ft.ScrollMode.ADAPTIVE,
        height=70,
        spacing=5
    )

    def render_category_chips():
        """現在のモードに対応するカテゴリリストからChip群を構築する"""
        target_list = (
            state.expense_categories
            if state.current_mode == "Expense"
            else state.income_categories
        )

        def on_chip_select(e: ft.ControlEvent):
            # すべてのチップの選択状態を解除（単一選択）
            for chip in category_chips_row.controls:
                chip.selected = False
            # 押されたチップを選択状態にする
            e.control.selected = True
            state.selected_category = e.control.label.value
            page.update()

        category_chips_row.controls = [
            ft.Chip(
                label=ft.Text(cat_name),
                selected=(state.selected_category == cat_name),
                on_select=on_chip_select,
                selected_color="blue700",
                show_checkmark=True,
            )
            for cat_name in target_list
        ]

    # 初回描画
    render_category_chips()

    content_input = ft.TextField(
        label="メモ",
        keyboard_type=ft.KeyboardType.TEXT,
        multiline=True,
        min_lines=3,
        border_color="bluegrey900",
        focused_border_color="blue400"
    )

    # --------------------------------------------------------------------------
    # 3. カテゴリ設定ダイアログ連携
    # --------------------------------------------------------------------------
    async def open_settings(e: ft.ControlEvent):
        async def on_cat_updated():
            # ダイアログで追加・削除された結果をチップ列に再反映
            render_category_chips()
            page.update()

        await open_category_settings_dialog(page, state, on_cat_updated)

    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS,
        tooltip="カテゴリの追加・削除",
        on_click=open_settings
    )

    # --------------------------------------------------------------------------
    # 4. データ保存処理（Googleスプレッドシートへの非同期追加）
    # --------------------------------------------------------------------------
    async def save_to_sheets(e: ft.ControlEvent):
        try:
            # 入力バリデーション
            if not amount_input.value or not state.selected_category:
                status_label.color = "red"
                status_label.value = (
                    f"現在の入力: 金額[{amount_input.value}], "
                    f"カテゴリ[{state.selected_category}]\n金額またはカテゴリが未記入です"
                )
                page.update()
                return

            val_str = amount_input.value.strip()
            if not val_str.replace(".", "", 1).isdigit():
                status_label.color = "red"
                status_label.value = f"現在の金額欄: {val_str}\n金額欄には0以上の半角数字を入力してください"
                page.update()
                return

            raw_amount = float(val_str)
            # Expense の場合は負数、Income の場合は正数にする
            amount_final = -raw_amount if state.current_mode == "Expense" else raw_amount

            # 固有UUIDとタイムスタンプの生成
            record_id = str(uuid.uuid4())
            timestamp_str = datetime.now(JST).strftime("%Y-%m-%d-%H-%M-%S")

            # レコード形式: [日付, モード, 金額, カテゴリ, メモ, タイムスタンプ, UUID]
            record = [
                selected_date_str,
                state.current_mode,
                amount_final,
                state.selected_category,
                content_input.value if content_input.value else "",
                timestamp_str,
                record_id
            ]

            # 保存中表示
            status_label.color = "orange"
            status_label.value = f"保存中...: {record[0:5]}"
            page.update()

            # Google Sheets API への追加（別スレッド実行でUIフリーズを防止）
            await asyncio.to_thread(sheets_service.add_record, record)

            # 保存成功時のUI更新
            status_label.color = "green"
            status_label.value = f"保存完了: {record[0:5]}"

            # 入力フィールドのリセット
            amount_input.value = ""
            content_input.value = ""
            state.selected_category = None
            for chip in category_chips_row.controls:
                chip.selected = False
            page.update()

        except Exception as ex:
            status_label.color = "red"
            status_label.value = f"エラー発生: {str(ex)}"
            page.update()
            print(f"[RecordView] 保存エラー詳細: {ex}")

    save_button = ft.Button("スプレッドシートに保存", icon=ft.Icons.SAVE, on_click=save_to_sheets)

    # --------------------------------------------------------------------------
    # 5. 安全な簡易電卓コンポーネント
    # --------------------------------------------------------------------------
    calc_input = ft.TextField(label="計算欄", hint_text="例: 1170 * (40/60)", expand=True, text_size=14)
    calc_result = ft.TextField(label="計算結果", read_only=True, value="", text_size=14)

    def on_calculate(e: ft.ControlEvent):
        # 安全なASTパーサーを利用して計算
        calc_result.value = safe_calculate(calc_input.value)
        page.update()

    calc_button = ft.Button("計算", on_click=on_calculate)

    # --------------------------------------------------------------------------
    # 6. コントロールの組み立てと返却
    # --------------------------------------------------------------------------
    controls: List[ft.Control] = [
        ft.Row(
            controls=[date_label, dateselect_button],
            alignment=ft.MainAxisAlignment.START
        ),
        amount_input,
        ft.Text("カテゴリを選択", size=12, color="grey500"),
        category_chips_row,
        content_input,
        ft.Row(
            controls=[save_button, settings_button],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        status_label,
        ft.Text("簡易電卓", size=12, color="grey500"),
        ft.Row(
            controls=[calc_input, calc_button],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        calc_result
    ]

    return controls