"""
ui/components/loading.py

【このコードの目的・機能・挙動】
アプリケーション全体（起動時、データ通信時、リスト追加読み込み時）で
一貫して使用するローディング表示インジケーターを提供するモジュールです。

旧コードにあったオレンジ色の ProgressRing と "Loading..." のテキストからなる Row を、
独立したコンポーネント関数として再定義しました。
必要な箇所で呼び出すだけで、統一されたデザインのインジケーターを安全に配置・再利用できます。
"""

import flet as ft


def create_loading_indicator(text: str = "Loading...") -> ft.Row:
    """
    中央揃えのオレンジ色ローディングインジケーターを生成して返す。
    
    引数:
        text: インジケーターの横に表示するテキスト（デフォルト: "Loading..."）
    戻り値:
        ft.Row: プログレスリングとテキストを含むレイアウト行
    """
    return ft.Row(
        controls=[
            ft.ProgressRing(
                width=16,
                height=16,
                stroke_width=2,
                color="orange"
            ),
            ft.Text(text, color="orange", size=12),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )