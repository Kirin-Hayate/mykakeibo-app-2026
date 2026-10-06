"""
main.py

【このコードの目的・機能・挙動】
家計簿アプリケーション全体の起動エントリーポイントおよび画面ルーティングを司る最上位モジュールです。

【旧コードからの改善点・動作原理】
1. Celeron J4125 / Xubuntu サーバー環境（systemd）向けの完全対応:
   旧コードでは os.getenv("RENDER") の判定のみで、自前サーバー向けのリッスンホスト・ポートが
   未定義でした。本モジュールでは config.settings から SERVER_HOST（0.0.0.0）と
   SERVER_PORT（8501等）を読み込み、外部端末のブラウザから確実にアクセスできるように起動します。
2. セッション独立性の確立（マルチユーザー接続の安定化）:
   アクセスしてきたブラウザ（Fletページ）ごとに独立した AppState を生成し、
   初期カテゴリと初期明細データの並列読み込み（asyncio.gather）を効率よく実行します。
3. 高速な画面モード切替（ルーティング）:
   最上部の SegmentedButton（Expense / Income / Analysis）の切り替えに応じて、
   コンテンツ表示コンテナ（content_container）の中身を動的に差し替えます。
   ページ全体を毎回白紙化（page.clean）する無駄を省き、チラつきを抑えて高速に応答します。
"""

import os
import asyncio
import flet as ft

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
    """
    ユーザーが接続した際に呼ばれるメインライフサイクル関数。
    セッションごとに完全に分離された状態とUIツリーを構築・維持する。
    """
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

    # セッション個別のステートをインスタンス化
    state = AppState()

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

    # 読み込んだカテゴリ（またはデフォルト）をステートに格納
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
    # ロード画面をクリアし、通常の左上揃えレイアウトへ移行
    page.clean()
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # 画面下部のメインコンテンツを表示するためのコンテナ
    content_container = ft.Column(expand=True, spacing=10)

    async def refresh_view():
        """現在のモードに合わせて画面コンテンツを再描画する"""
        state.cancel_tasks()
        content_container.controls.clear()

        # 描画切り替えのローディング表示
        content_container.controls.append(create_loading_indicator())
        page.update()
        await asyncio.sleep(0)  # UIスレッドへ制御を戻して描画を先行

        content_container.controls.clear()
        if state.current_mode == "Analysis":
            analysis_controls = await build_analysis_view(page, state, refresh_view)
            content_container.controls.extend(analysis_controls)
        else:
            # Expense または Income 入力画面
            record_controls = build_record_view(page, state)
            content_container.controls.extend(record_controls)

        page.update()

    async def on_mode_change(e: ft.ControlEvent):
        """最上部 SegmentedButton の切り替えハンドラ"""
        if e.control.selected:
            selected_mode = list(e.control.selected)[0]
            state.current_mode = selected_mode
            choice_segment.selected = [selected_mode]
            await refresh_view()

    # モード切り替えセグメントボタン
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

    # 常時表示される共通ヘッダーとコンテンツコンテナを追加
    page.add(
        ft.Text("My家計簿", size=20, weight=ft.FontWeight.BOLD),
        choice_segment,
        content_container
    )

    # 初回画面描画を実行
    await refresh_view()


if __name__ == "__main__":
    # 環境変数または引数でWeb公開モードを判定
    # CHUWI HeroBox常時稼働サーバー向けに、デフォルトで 0.0.0.0 / ポート8501 でブラウザ公開
    is_web = os.getenv("WEB_MODE", "1") == "1"

    if is_web:
        print(f"[MyKAKEIBO] サーバー起動中: http://{SERVER_HOST}:{SERVER_PORT}")
        ft.run(
            main,
            host=SERVER_HOST,
            port=SERVER_PORT,
            view=ft.AppView.WEB_BROWSER
        )
    else:
        # ローカル開発時のデスクトップネイティブ表示
        ft.run(main)