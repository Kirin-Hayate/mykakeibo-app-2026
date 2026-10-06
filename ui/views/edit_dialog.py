"""
ui/views/edit_dialog.py

【このコードの目的・機能・挙動】
明細一覧（Analysis画面）の各行にある「EDIT」ボタンが押された際に立ち上がる、
明細の「修正保存」「新規複製保存」「削除」を行うモーダルダイアログモジュールです。

【旧コードからの改善点・動作原理】
1. 肥大化した main.py からの分離と疎結合化:
   旧コードでは make_analysispage() の内部関数として深くネストしていた open_edit_dialog() を独立化しました。
   更新・複製・削除の実行後は、引数として受け取った非同期コールバック（on_data_mutated）を呼び出し、
   親画面へ一覧の再描画を依頼します。
2. DatePickerおよびダイアログのライフサイクル管理:
   page.overlay に追加した DatePicker や AlertDialog が画面に残り続けるゾンビ化バグを防ぐため、
   保存・削除・キャンセルのいずれのアクションでも overlay から確実に削除・クリーンアップします。
3. sheets_service との連携:
   非同期で sheets_service.update_or_delete_record() や sheets_service.add_record() を実行し、
   キャッシュの破棄・整合性を担保します。
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Any, Callable, Coroutine
import flet as ft

from config.settings import JST
from ui.state import AppState
from services.sheets_service import sheets_service


async def open_edit_dialog(
    page: ft.Page,
    state: AppState,
    row_data: List[Any],
    on_data_mutated: Callable[[], Coroutine[Any, Any, None]]
) -> None:
    """
    指定された1件の明細データを編集・削除・複製するためのダイアログを表示する。

    引数:
        page: 現在のFletページオブジェクト
        state: セッション個別のアプリケーション状態
        row_data: 編集対象のレコード [日付, モード, 金額, カテゴリ, メモ, 登録日時, UUID]
        on_data_mutated: データ更新・削除・複製完了後に一覧を再読込するための非同期コールバック
    """
    # --------------------------------------------------------------------------
    # 1. 編集用の一時状態の初期化
    # --------------------------------------------------------------------------
    current_edit_date = str(row_data[0])
    current_edit_mode = str(row_data[1])
    current_edit_category = str(row_data[3])
    raw_amount = abs(float(row_data[2])) if len(row_data) > 2 and row_data[2] != "" else 0.0
    memo_val = str(row_data[4]) if len(row_data) > 4 else ""
    target_uuid = str(row_data[6]) if len(row_data) > 6 else ""

    # 全カテゴリ（重複排除・ソート）
    all_categories = sorted(list(set(state.expense_categories + state.income_categories)))

    # --------------------------------------------------------------------------
    # 2. UI部品の作成（モード切替チップ、カテゴリ選択チップ、入力欄）
    # --------------------------------------------------------------------------
    category_row = ft.Row(wrap=False, scroll=ft.ScrollMode.ADAPTIVE, spacing=5)

    def render_category_chips():
        """現在のモードと選択カテゴリに合わせてチップ列を描画"""
        category_row.controls.clear()
        # モードに対応するカテゴリを優先（なければ全体）
        target_list = state.expense_categories if current_edit_mode == "Expense" else state.income_categories
        if not target_list:
            target_list = all_categories

        for cat in target_list:
            category_row.controls.append(
                ft.Chip(
                    label=ft.Text(cat),
                    selected=(current_edit_category == cat),
                    on_select=lambda e, c=cat: on_select_category(c),
                    show_checkmark=True,
                )
            )

    def on_select_category(cat_name: str):
        nonlocal current_edit_category
        current_edit_category = cat_name
        for chip in category_row.controls:
            chip.selected = (chip.label.value == cat_name)
        page.update()

    def update_mode(mode_name: str):
        """Expense / Income のモード切替"""
        nonlocal current_edit_mode
        current_edit_mode = mode_name
        mode_choice_expense.selected = (mode_name == "Expense")
        mode_choice_income.selected = (mode_name == "Income")
        render_category_chips()
        page.update()

    mode_choice_expense = ft.Chip(
        label=ft.Text("Expense"),
        selected=(current_edit_mode == "Expense"),
        on_select=lambda e: update_mode("Expense"),
        show_checkmark=True,
        selected_color=ft.Colors.ORANGE_ACCENT,
    )
    mode_choice_income = ft.Chip(
        label=ft.Text("Income"),
        selected=(current_edit_mode == "Income"),
        on_select=lambda e: update_mode("Income"),
        show_checkmark=True,
        selected_color=ft.Colors.GREEN_400,
    )

    render_category_chips()

    # 日付ピッカーの設定
    try:
        initial_date = datetime.strptime(current_edit_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        initial_date = datetime.now(JST)

    async def on_edit_date_change(e: ft.ControlEvent):
        nonlocal current_edit_date
        if e.control.value:
            current_edit_date = e.control.value.strftime("%Y-%m-%d")
            edit_date_button.text = f"日付: {current_edit_date}"
            page.update()

    edit_date_picker = ft.DatePicker(
        on_change=on_edit_date_change,
        first_date=datetime(2000, 1, 1),
        last_date=datetime(3000, 12, 31),
        value=initial_date
    )
    page.overlay.append(edit_date_picker)

    def open_edit_date_picker(e: ft.ControlEvent):
        edit_date_picker.open = True
        page.update()

    edit_date_button = ft.Button(
        f"日付: {current_edit_date}",
        icon=ft.Icons.CALENDAR_MONTH,
        on_click=open_edit_date_picker
    )

    edit_amount = ft.TextField(label="金額", value=str(int(raw_amount) if raw_amount.is_integer() else raw_amount))
    edit_content = ft.TextField(label="メモ", multiline=True, value=memo_val)

    # 進行中ステータス表示
    status_left = ft.Text("", weight=ft.FontWeight.BOLD, size=12)
    status_right = ft.Text("", weight=ft.FontWeight.BOLD, size=12)

    # --------------------------------------------------------------------------
    # 3. 各アクションハンドラ（保存 / 削除 / 複製 / 閉じる）
    # --------------------------------------------------------------------------
    async def cleanup_overlay():
        """ダイアログとDatePickerを overlay から完全消去"""
        dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if edit_date_picker in page.overlay:
            page.overlay.remove(edit_date_picker)
        if dialog in page.overlay:
            page.overlay.remove(dialog)
        page.update()

    async def on_save(e: ft.ControlEvent):
        """変更内容で上書き保存（UPDATE）"""
        try:
            amt_val = float(edit_amount.value.strip())
        except ValueError:
            amt_val = 0.0

        new_kingaku = -amt_val if current_edit_mode == "Expense" else amt_val
        status_right.value = "保存中..."
        status_right.color = "orange"
        page.update()

        # レコード更新: UUIDと元タイムスタンプは維持
        updated_record = [
            current_edit_date,
            current_edit_mode,
            new_kingaku,
            current_edit_category,
            edit_content.value,
            row_data[5],
            target_uuid
        ]

        await cleanup_overlay()
        await asyncio.to_thread(
            sheets_service.update_or_delete_record,
            target_uuid,
            updated_record,
            "UPDATE"
        )
        await on_data_mutated()

    async def on_delete(e: ft.ControlEvent):
        """該当レコードを行削除（DELETE）"""
        status_left.value = "削除中..."
        status_left.color = "orange"
        page.update()

        await cleanup_overlay()
        await asyncio.to_thread(
            sheets_service.update_or_delete_record,
            target_uuid,
            None,
            "DELETE"
        )
        await on_data_mutated()

    async def on_duplicate(e: ft.ControlEvent):
        """現在の入力内容をもとに新しいUUIDを付与して新規複製保存（INSERT）"""
        try:
            amt_val = float(edit_amount.value.strip())
        except ValueError:
            amt_val = 0.0

        new_kingaku = -amt_val if current_edit_mode == "Expense" else amt_val
        new_id = str(uuid.uuid4())
        new_ts = datetime.now(JST).strftime("%Y-%m-%d-%H-%M-%S")

        new_record = [
            current_edit_date,
            current_edit_mode,
            new_kingaku,
            current_edit_category,
            edit_content.value,
            new_ts,
            new_id
        ]

        await cleanup_overlay()
        await asyncio.to_thread(sheets_service.add_record, new_record)
        await on_data_mutated()

    async def close_dialog(e: ft.ControlEvent):
        await cleanup_overlay()

    # --------------------------------------------------------------------------
    # 4. ダイアログの構築と表示
    # --------------------------------------------------------------------------
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Text("Edit/Delete"),
                ft.IconButton(
                    icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                    tooltip="この内容で新規作成(複製)",
                    on_click=on_duplicate
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        content=ft.Column(
            controls=[
                ft.Text("日付", size=12, color="grey500"),
                edit_date_button,
                ft.Text("モード", size=12, color="grey500"),
                ft.Row([mode_choice_expense, mode_choice_income]),
                ft.Text("カテゴリ", size=12, color="grey500"),
                category_row,
                edit_amount,
                edit_content,
            ],
            tight=True
        ),
        actions=[
            ft.Row(
                controls=[
                    ft.Row([
                        ft.TextButton("削除", on_click=on_delete, icon_color="red"),
                        status_left
                    ], spacing=5),
                    ft.Row([
                        status_right,
                        ft.TextButton("キャンセル", on_click=close_dialog),
                        ft.TextButton("保存", on_click=on_save),
                    ], spacing=10)
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
        ]
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()