"""
ui/views/edit_dialog.py

【このコードの目的・機能・挙動】
明細一覧（Analysis画面）の各行にある「EDIT」ボタンが押された際に立ち上がる、
明細の「修正保存」「新規複製保存」「削除」を行うモーダルダイアログモジュールです。

【修正内容】
- DatePickerの返却値（UTCの15:00）を確実に JST（UTC+9）に変換して日付を確定させ、
  カレンダーで選んだ日付（10/8）がそのまま 10/8 として表示・保存されるよう修正。
"""

import asyncio
import uuid
from datetime import datetime, timezone
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
    """
    current_edit_date = str(row_data[0])
    current_edit_mode = str(row_data[1])
    current_edit_category = str(row_data[3])
    raw_amount = abs(float(row_data[2])) if len(row_data) > 2 and row_data[2] != "" else 0.0
    memo_val = str(row_data[4]) if len(row_data) > 4 else ""
    target_uuid = str(row_data[6]) if len(row_data) > 6 else ""

    all_categories = sorted(list(set(state.expense_categories + state.income_categories)))

    category_row = ft.Row(wrap=False, scroll=ft.ScrollMode.ADAPTIVE, spacing=5)

    def render_category_chips():
        category_row.controls.clear()
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

    try:
        initial_date = datetime.strptime(current_edit_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        initial_date = datetime.now(JST)

    date_display_text = ft.Text(
        f"日付: {current_edit_date}",
        size=14,
        weight=ft.FontWeight.W_500
    )

    def on_edit_date_change(e: ft.ControlEvent):
        nonlocal current_edit_date
        picked_val = e.control.value
        if picked_val is not None:
            if isinstance(picked_val, datetime):
                # Fletから届くUTC時刻（前日15:00等）をJST（+9時間）に正しく変換
                if picked_val.tzinfo is None:
                    jst_dt = picked_val.replace(tzinfo=timezone.utc).astimezone(JST)
                else:
                    jst_dt = picked_val.astimezone(JST)
                current_edit_date = f"{jst_dt.year:04d}-{jst_dt.month:02d}-{jst_dt.day:02d}"
            else:
                current_edit_date = str(picked_val)[:10]

            date_display_text.value = f"日付: {current_edit_date}"
            date_display_text.update()
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

    edit_date_button = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CALENDAR_MONTH, size=18, color=ft.Colors.CYAN_200),
                date_display_text,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(vertical=10, horizontal=14),
        border=ft.Border.all(1, ft.Colors.GREY_700),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREY),
        on_click=open_edit_date_picker,
        ink=True,
    )

    edit_amount = ft.TextField(label="金額", value=str(int(raw_amount) if raw_amount.is_integer() else raw_amount))
    edit_content = ft.TextField(label="メモ", multiline=True, value=memo_val)

    status_left = ft.Text("", weight=ft.FontWeight.BOLD, size=12)
    status_right = ft.Text("", weight=ft.FontWeight.BOLD, size=12)

    async def cleanup_overlay():
        dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if edit_date_picker in page.overlay:
            page.overlay.remove(edit_date_picker)
        if dialog in page.overlay:
            page.overlay.remove(dialog)
        page.update()

    async def on_save(e: ft.ControlEvent):
        try:
            amt_val = float(edit_amount.value.strip())
        except ValueError:
            amt_val = 0.0

        new_kingaku = -amt_val if current_edit_mode == "Expense" else amt_val
        status_right.value = "保存中..."
        status_right.color = "orange"
        page.update()

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