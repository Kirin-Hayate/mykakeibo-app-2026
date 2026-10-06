"""
ui/state.py

【このコードの目的・機能・挙動】
Webブラウザ等からアクセスしてきたユーザー（Fletセッション）ごとに独立して
画面状態を保持・管理するための状態管理クラス（AppState）を定義します。

【旧コードからの大幅な改善点・動作原理】
旧コードでは current_scroll_task や current_task がモジュールレベルの
グローバル変数となっていたため、HeroBoxをサーバーとして複数クライアントから
同時接続した場合に、他ユーザーのスクロールやページ切り替えタスクを
誤って強制キャンセルしてしまう競合問題（レースコンディション）を抱えていました。
本モジュールにより、状態がすべて page.session_id ごとにインスタンス化される
AppState 内にカプセル化されるため、マルチユーザー環境でも完全な独立稼働が保証されます。
"""

import asyncio
from typing import List, Optional, Any


class AppState:
    def __init__(self):
        # 現在の選択モード（"Expense" / "Income" / "Analysis"）
        self.current_mode: str = "Expense"

        # カテゴリ一覧（スプレッドシートから読み込んだマスタ）
        self.expense_categories: List[str] = []
        self.income_categories: List[str] = []

        # 入力画面で選択中のカテゴリ
        self.selected_category: Optional[str] = None

        # フィルタ条件の保持用リスト
        # [mode, [categories], keyword, oldest_date, latest_date, max_amt, min_amt]
        self.filter_query: List[Any] = [None, None, None, None, None, None, None]

        # ソート状態（0:日付, 1:カテゴリ, 2:金額, 3:内容）
        self.sort_column_index: int = 0
        self.sort_ascending: bool = False

        # 現在画面上で表示・保持しているフィルタ済みレコード
        self.filtered_data_rows: List[List[Any]] = []

        # セッション個別の非同期タスク参照（グローバル変数の完全排除）
        self.current_page_task: Optional[asyncio.Task] = None
        self.current_scroll_task: Optional[asyncio.Task] = None

    def cancel_tasks(self) -> None:
        """実行中のバックグラウンドタスク（描画・スクロール）があれば安全にキャンセルする"""
        if self.current_page_task and not self.current_page_task.done():
            self.current_page_task.cancel()
        if self.current_scroll_task and not self.current_scroll_task.done():
            self.current_scroll_task.cancel()