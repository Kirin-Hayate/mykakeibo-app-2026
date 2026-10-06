"""
ui/views/category_dialog.py

【このコードの目的・機能・挙動】
支出（Expense）または収入（Income）のカテゴリ一覧を動的に追加・削除するための
モーダルダイアログを提供するモジュールです。

【旧コードからの改善点・動作原理】
1. 画面全体の再描画を排除:
   旧コードではカテゴリ編集の完了時に画面全体の refresh_view() を呼び出して
   全コントロールを再構築していましたが、本モジュールではダイアログ内の
   カテゴリ変更をスプレッドシート（Settingsシート）に保存後、
   呼び出し元から渡されたコールバック関数（on_category_changed）を通じて
   画面側のチップ列のみを差分更新（update）させ、描画コストを最小限に抑えます。
2. 非同期通信の分離:
   スプレッドシート保存処理（sheets_service.save_categories）は
   asyncio.to_thread を用いてワーカースレッドへ逃がし、UIのフリーズを防ぎます。
"""

import asyncio
from typing import Callable, Coroutine, Any
import flet as ft

from ui.state import AppState
from services.sheets_service import sheets_service


async def open_category_settings_dialog(
    page: ft.Page,
    state: AppState,
    on_category_changed: Callable[[], Coroutine[Any, Any, None]]
) -> None:
    """
    カテゴリ編集ダイアログを開く。

    引数:
        page: 現在のFletページオブジェクト
        state: セッション個別のアプリケーション状態
        on_category_changed: カテゴリの追加・削除が完了した際に画面側のチップを更新するための非同期コールバック
    """
    # 現在のモード（Expense / Income）に応じた編集対象のリストを参照
    target_list = (
        state.expense_categories
        if state.current_mode == "Expense"
        else state.income_categories
    )

    # 新規カテゴリ入力用テキストフィールド
    new_cat_input = ft.TextField(
        label="新しいカテゴリ",
        expand=True,
        height=40,
        text_size=14
    )

    # 既存カテゴリ一覧を表示する縦スクロールコンテナ
    cat_list_col = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        height=300,
        spacing=5
    )

    async def render_cat_list():
        """現在の target_list に基づいてダイアログ内の一覧を再描画する"""
        cat_list_col.controls.clear()
        for cat in target_list:
            cat_list_col.controls.append(
                ft.Row(
                    controls=[
                        ft.Text(cat, expand=True, size=13),
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            icon_color="red",
                            icon_size=18,
                            data=cat,
                            on_click=delete_category
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )
        if settings_dialog.open:
            page.update()

    async def add_category(e: ft.ControlEvent):
        """入力されたカテゴリをリストに追加し、スプレッドシートへ保存する"""
        val = new_cat_input.value.strip() if new_cat_input.value else ""
        if val and val not in target_list:
            target_list.append(val)
            new_cat_input.value = ""

            # Google Sheets APIのSettingsシートへ非同期保存
            await asyncio.to_thread(
                sheets_service.save_categories,
                state.expense_categories,
                state.income_categories
            )

            # ダイアログ内の一覧を再描画
            await render_cat_list()

    async def delete_category(e: ft.ControlEvent):
        """選択されたカテゴリをリストから削除し、スプレッドシートへ保存する"""
        cat_name = e.control.data
        if cat_name in target_list:
            target_list.remove(cat_name)

            # Google Sheets APIのSettingsシートへ非同期保存
            await asyncio.to_thread(
                sheets_service.save_categories,
                state.expense_categories,
                state.income_categories
            )

            # ダイアログ内の一覧を再描画
            await render_cat_list()

    async def close_settings_dialog(e: ft.ControlEvent):
        """ダイアログを閉じ、呼び出し元のUIに最新カテゴリを反映させる"""
        settings_dialog.open = False
        page.update()

        # ダイアログのアニメーション完了待ち
        await asyncio.sleep(0.1)
        if settings_dialog in page.overlay:
            page.overlay.remove(settings_dialog)
            page.update()

        # 親画面側のカテゴリ選択チップ等を再生成するコールバックを呼び出し
        await on_category_changed()

    # ダイアログの定義
    settings_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"{state.current_mode} カテゴリ編集"),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            new_cat_input,
                            ft.IconButton(
                                icon=ft.Icons.ADD,
                                on_click=add_category
                            )
                        ]
                    ),
                    ft.Divider(),
                    cat_list_col,
                ],
                tight=True
            ),
            width=300
        ),
        actions=[
            ft.TextButton("閉じる", on_click=close_settings_dialog)
        ],
    )

    # 初回の一覧構築を行ってからオーバーレイに追加・表示
    await render_cat_list()
    page.overlay.append(settings_dialog)
    settings_dialog.open = True
    page.update()