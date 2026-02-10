import flet as ft

def main(page: ft.Page):
    page.title = "test-fletアプリ-202602032203"
    page.window_width = 400
    page.window_height = 600

    # 1. 部品の作成
    # TextFieldのprefixも、より安定した構成に変更しました
    amount_input = ft.TextField(
        label="金額", 
        prefix =ft.Text("¥"), 
        keyboard_type=ft.KeyboardType.NUMBER
    )
    
    category_dropdown = ft.Dropdown(
        label="カテゴリ",
        options=[
            ft.dropdown.Option("食費"),
            ft.dropdown.Option("日用品"),
            ft.dropdown.Option("趣味・娯楽"),
            ft.dropdown.Option("交通費"),
        ],
    )

    # 確実に動作するボタンの書き方
    save_button = ft.ElevatedButton("スプレッドシートに保存",icon="save")

    # 2. 画面に部品を追加
    page.add(
        ft.Text("支出を記録", size=20, weight=ft.FontWeight.BOLD),
        amount_input,
        category_dropdown,
        save_button
    )

ft.app(target=main)