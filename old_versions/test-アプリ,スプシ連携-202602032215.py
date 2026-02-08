import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

#記録は、リスト形式[日付、金額、ジャンル、内容]

def Kakikomi(record):
    # 1.認証フェーズ（「通行証」の準備）ーーーーーーーーーーーーーーーーー
    #scope: 「このアプリはGoogleドライブのどの範囲まで触っていいか？」という権限の範囲を定義しています。
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

    #creds: ~.json（秘密鍵）を読み込み、「私は許可されたプログラムです」というデジタルな通行証を作成しています。
    creds = ServiceAccountCredentials.from_json_keyfile_name('秘密鍵-kakeibofrom202602032126.json', scope) # ここにファイル名

    # 2. 接続フェーズ（「扉」を開ける）
    #authorize: 通行証をGoogleのサーバーに提示し、操作を許可してもらいます。
    client = gspread.authorize(creds)
    #open: インターネット上にある膨大なファイルの中から、名前を頼りに特定のシートを見つけて接続を確立します。
    SHEET_NAME = "家計簿テストver202602032139" 
    sheet = client.open(SHEET_NAME).sheet1

    # 3. 操作フェーズ（「命令」を送る）
    #append_row: 「一番下の空いている行に、このリストの内容を書き込め」という命令を送ります。
    sheet.append_row(record)
    #この瞬間、PythonからGoogleのサーバーへデータが送信され、スプレッドシートがリアルタイムで更新されます。

    print(f"書き込み成功：内容{record}")

def main(page: ft.Page):
    page.title = "test-アプリ,スプシ連携-202602032215"
    page.window_width = 400
    page.window_height = 600
    page.theme_mode = ft.ThemeMode.DARK

    #部品の作成(保存ボタン、日付以外)
    amount_input = ft.TextField(
        label="金額", 
        prefix =ft.Text("¥"), 
        keyboard_type=ft.KeyboardType.NUMBER
    )
    
    #カテゴリ作成
    category_dropdown = ft.Dropdown(
        label="カテゴリ",
        options=[
            ft.dropdown.Option("食費"),
            ft.dropdown.Option("日用品"),
            ft.dropdown.Option("趣味・娯楽"),
            ft.dropdown.Option("交通費"),
        ],
    )

    #説明欄の初期設定
    content_input = ft.TextField(
        label = "説明",
        keyboard_type=ft.KeyboardType.TEXT,
        multiline = True,
        min_lines=3
    )

    #保存ができたかどうか表示する用のやつ(内容はのちのち入れる)
    status_label = ft.Text("", color="green", weight="bold")

    #入力された値をスプシに保存する関数
    def save_to_sheets(e):
        try:
            if not amount_input.value or not category_dropdown.value:
                # 入力漏れがある場合
                status_label.color = "red"
                status_label.value = f"金額またはカテゴリが未記入です"
                page.update()
                return
            
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record = [date_str,amount_input.value, category_dropdown.value,content_input.value ]
            Kakikomi(record)

            # 成功メッセージ
            status_label.color = "green"
            status_label.value = f"保存完了:{record}"
            
            # 入力欄をクリア
            amount_input.value = ""
            category_dropdown.value = None
            content_input.value = ""

            page.update()

        except:
            status_label.value = f"保存失敗:{record}"
            status_label.color = "red"
            page.update()

    #保存ボタン作成
    save_button = ft.ElevatedButton("スプレッドシートに保存",icon="save",on_click=save_to_sheets) 


    #画面に部品を追加
    page.add(
        ft.Text("支出を記録", size=20, weight=ft.FontWeight.BOLD),
        amount_input,
        category_dropdown,
        content_input,
        save_button,
        status_label
    )


ft.app(target=main)
