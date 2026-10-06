import flet as ft

#ここがアプリの「中身」を書く場所です。page という変数が、スマホやPCの「画面そのもの」を指しています。
def main(page: ft.Page):
    # 1. ページ（画面）の設定
    page.title = "test-flet動作確認-202602032159"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER # 中央寄せ

    # 2. 「こんにちは」という部品（Textコントロール）を作成
    hello_text = ft.Text("こんにちは！", size=30, color="blue")

    # 3. ページに部品を追加
    page.add(hello_text)

# アプリを起動する.Windowsならウィンドウが開き、Androidならアプリ画面が開くことになります。
ft.app(target=main)