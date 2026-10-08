"""
main.py

【このコードの目的・機能・挙動】
家計簿アプリケーション全体の起動エントリーポイントおよび画面ルーティングを司る最上位モジュールです。

【実行環境の自動切り替え】
.env の APP_ENV（local または server）を読み取り、以下の通り起動挙動を自動分岐します。
1. ノートPC（APP_ENV=local）:
   デスクトップアプリとしてウィンドウ表示で即座に起動し、手元でのUI確認やデバッグを可能にします。
2. ミニPCサーバー（APP_ENV=server）:
   ホスト 0.0.0.0、ポート 8501（または環境変数指定）で常駐Webサーバーとして立ち上がり、
   同一LAN内のブラウザ（スマホやPC）からアクセス可能にします。

【動作仕様】
- セッションごとに独立した AppState をインスタンス化し、マルチユーザー接続時のタスク競合を排除。
- 初期起動時にカテゴリ情報と全レコードを非同期並列（asyncio.gather）で高速読み込み。
- SegmentedButton（Expense / Income / Analysis）の切り替えに応じ、コンテンツコンテナのみを差分再描画。

【Windowsでの終了フリーズ対策】
page.window.on_event および page.on_disconnect を監視し、
デスクトップウィンドウが閉じられた瞬間にバックグラウンドタスクを停止し
os._exit(0) で安全にプロセスを解放してターミナルへ戻します。
"""

import os
import sys
import asyncio
import socket
import flet as ft

# ------------------------------------------------------------------------------
# Windows特有の Proactor パイプ切断例外 (WinError 10054) 対策
# ------------------------------------------------------------------------------
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport

    _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

    def _safe_call_connection_lost(self, exc=None):
        try:
            _orig_call_connection_lost(self, exc)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            # ダイアログ展開中の強制切断時、コンソールをフリーズさせずに即終了
            if os.getenv("APP_ENV", "local").lower() != "server":
                os._exit(0)

    _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost

from config.settings import (
    SPREADSHEET_NAME,
    SERVER_HOST,
    SERVER_PORT,
    ICON_PATH
)
from ui.state import AppState
from ui.components.loading import create_loading_indicator
from ui.views.record_view import build_record_view
from ui.views.analysis_view import build_analysis_view
from services.sheets_service import sheets_service


async def main(page: ft.Page):
    # ウィンドウの閉鎖はOS標準に委ねる（どの画面でも×ボタンが即座に反応）
    page.window.prevent_close = False

    # 切断イベント発生時もプロセスを即時解放
    page.on_disconnect = lambda _: os._exit(0) if os.getenv("APP_ENV", "local").lower() != "server" else None

    # セッション個別のステートをインスタンス化
    state = AppState()

    # --------------------------------------------------------------------------
    # 1. ページ初期設定（テーマ、ウィンドウサイズ、アイコン）
    # --------------------------------------------------------------------------
    page.title = "MyKAKEIBO"
    page.window.width = 400
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 5

    if ICON_PATH.exists():
        page.window.icon = str(ICON_PATH)

    # --------------------------------------------------------------------------
    # 2. 初期ロード画面の表示（接続中演出）
    # --------------------------------------------------------------------------
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    page.add(
        ft.Column(
            controls=[
                ft.Text("My家計簿", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(ft.Icons.SAVINGS, size=100, color=ft.Colors.WHITE),
                ft.Text(f"connecting to {SPREADSHEET_NAME}", size=10, weight=ft.FontWeight.W_200, color=ft.Colors.WHITE),
                create_loading_indicator("初期データ取得中..."),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    page.update()

    # --------------------------------------------------------------------------
    # 3. 初期データの非同期並行読み込み（カテゴリ & 明細）
    # --------------------------------------------------------------------------
    task_cat = asyncio.to_thread(sheets_service.load_categories)
    task_data = asyncio.to_thread(sheets_service.get_all_records)
    (loaded_expense, loaded_income), _ = await asyncio.gather(task_cat, task_data)

    if loaded_expense:
        state.expense_categories = loaded_expense
    else:
        state.expense_categories = [
            "Wagner", "SYC", "交通", "食費", "交際", "勉強,研究",
            "電話", "娯楽", "美容", "税", "衣服", "旅行",
            "給与誤差脱漏", "医療", "その他"
        ]

    if loaded_income:
        state.income_categories = loaded_income
    else:
        state.income_categories = ["FreeStep", "お小遣い", "その他"]

    # --------------------------------------------------------------------------
    # 4. メインUI構造の定義とルーティング
    # --------------------------------------------------------------------------
    page.clean()
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    content_container = ft.Column(expand=True, spacing=10)

    async def refresh_view():
        state.cancel_tasks()
        content_container.controls.clear()

        content_container.controls.append(create_loading_indicator())
        page.update()
        await asyncio.sleep(0)

        content_container.controls.clear()
        if state.current_mode == "Analysis":
            analysis_controls = await build_analysis_view(page, state, refresh_view)
            content_container.controls.extend(analysis_controls)
        else:
            record_controls = build_record_view(page, state)
            content_container.controls.extend(record_controls)

        page.update()

    async def on_mode_change(e: ft.ControlEvent):
        if e.control.selected:
            selected_mode = list(e.control.selected)[0]
            state.current_mode = selected_mode
            choice_segment.selected = [selected_mode]
            await refresh_view()

    choice_segment = ft.SegmentedButton(
        selected=[state.current_mode],
        allow_multiple_selection=False,
        on_change=on_mode_change,
        segments=[
            ft.Segment(value="Expense", label=ft.Text("Expense")),
            ft.Segment(value="Income", label=ft.Text("Income")),
            ft.Segment(value="Analysis", label=ft.Text("Analysis"))
        ],
    )

    page.add(
        ft.Text("My家計簿", size=20, weight=ft.FontWeight.BOLD),
        choice_segment,
        content_container
    )

    await refresh_view()


if __name__ == "__main__":
    app_env = os.getenv("APP_ENV", "local").lower()

    if app_env == "server":
        print(f"[MyKAKEIBO] サーバーモード起動: http://{SERVER_HOST}:{SERVER_PORT}")
        ft.run(
            main,
            host=SERVER_HOST,
            port=SERVER_PORT,
            view=ft.AppView.WEB_BROWSER
        )
    else:
        print("[MyKAKEIBO] ローカルPCモード起動 (デスクトップUI)")
        ft.run(main)