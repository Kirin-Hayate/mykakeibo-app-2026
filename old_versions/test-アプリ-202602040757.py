import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import asyncio
from datetime import timedelta

#スプシへの書き込みを行う関数 Kakikomi()
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

#ページを駆動する部分
async def main(page: ft.Page):
    page.title = "test-アプリ-202602040757"
    page.window_width = 400
    page.window_height = 600
    page.theme_mode = ft.ThemeMode.DARK

    #日付入力部分の作成
    #日付はdate_inputに格納。デフォルトでは今日の日付today YYYY-MM-DD を代入
    today = datetime.now().strftime("%Y-%m-%d")
    date_input = today

    #選択した日付を表示する部分
    date_label = ft.Text(f"date:{date_input}", color="white", weight="bold",size=20)

    #カレンダーから日付が選択されたときの動作の詳細を規定
    async def handle_change(e):
        nonlocal date_input
        temp_date = e.control.value
        #Flet,日本時間じゃなくてイギリス時間で動いているらしい。不本意ながら12時間足して中和する
        fixed_date = temp_date + timedelta(hours=12)
        #このままだとtemp_dateがPythonのオブジェクトそのものなので、文字列YYYY-MM-DDに変換
        date_input = fixed_date .strftime("%Y-%m-%d")
        date_label.value = f"date:{date_input}"
        page.update()

    #カレンダーの設定と、日付選択時の動作を規定
    date_picker = ft.DatePicker(
    on_change=handle_change,  # 日付が選択された時に動く関数
    value = datetime.now(), #初期選択位置を今日にする
    first_date=datetime(2023, 1, 1), # 選択可能な最小日
    last_date=datetime(2100, 12, 31)  # 選択可能な最大日
    )

    #日付の変更ボタンを押したときの動作を規定
    async def open_picker(e):
        date_picker.open = True
        page.update()

    #日付変更ボタンのデザインや機能を規定
    dateselect_button = ft.Button(
    f"日付の変更",
    icon="calendar_month",
    on_click = open_picker
    )

    #金額入力部分の作成
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

    #メッセージ表示するやつ(内容はのちのち変更)
    status_label = ft.Text("", color="green", weight="bold")

    #入力された値をスプシに保存する関数
    async def save_to_sheets(e):
        try:
            if not amount_input.value or not category_dropdown.value:
                # 入力漏れがある場合
                status_label.color = "red"
                status_label.value = f"現在の入力:金額[{amount_input.value}],カテゴリ[{category_dropdown.value}]\n金額またはカテゴリが未記入です"
                page.update()
                return
            
            if  amount_input.value.isnumeric()== False:
                #金額欄に入力された文字列がすべて数字ならTrue,そうでなければFalseになる
                status_label.color = "red"
                status_label.value = f"現在の金額欄:{amount_input.value}\n金額欄には0以上の半角数字を入力"
                page.update()
                return

            
            #日付,金額,カテゴリ,説明を含むリスト "record"を作成
            #金額については、全角数字で書かれていた場合でもfloat型になおす
            record = [date_input,float(amount_input.value), category_dropdown.value,content_input.value ]
            
            #「保存中」メッセージを表示
            status_label.color = "orange"
            status_label.value = f"保存中...:{record}"
            page.update()

            #スプシへの書き込み処理(非同期で実行)
            await asyncio.to_thread(Kakikomi, record)

            # 成功メッセージを作成
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
    save_button = ft.Button("スプレッドシートに保存",icon="save",on_click=save_to_sheets) 


    #カレンダーを仕込んでおく
    page.overlay.append(date_picker)

    #画面に部品を追加(レイアウトの指定)
    page.add(
        date_label,
        dateselect_button,
        amount_input,
        category_dropdown,
        content_input,
        save_button,
        status_label
    )


ft.app(target=main)
