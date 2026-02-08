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
    page.title = "test-アプリ-202602050821"
    page.window_width = 100
    page.window_height = 300
    page.theme_mode = ft.ThemeMode.DARK

    #モード切替(Expense/Income/Analysis)
    current_mode = "Expense"

    #メッセージ表示するやつ(内容はのちのち変更)
    status_label = ft.Text("", color="green", weight="bold")

    #画面に部品を追加(レイアウトの指定)
    async def make_recordingpage():
        page.add(
            ft.Row(
                [date_label, dateselect_button],
                alignment=ft.MainAxisAlignment.START # ラベルは左、ボタンは右
            ),
            amount_input,
            category_dropdown,
            content_input,
            save_button,
            status_label
        )
    

    #画面を再読み込み（再構築）する関数を作る
    async def refresh_view():
        page.clean()  # いったん画面の中身を全部消す
        
        # モードによらず必ず表示するものを追加
        page.add(ft.Text("My家計簿ver202602051000", size=20),choice_segment)

        # モードに応じて表示し分ける
        if current_mode == "Analysis":
            # Analysisモードの表示内容
            page.add(ft.Text("分析画面です", size=30))
            page.add(ft.Icon(ft.Icons.ANALYTICS, size=100))
        else:
            # Expense / Income モードの表示内容
            await make_recordingpage()
        page.update() # 最後に画面を更新

    async def mode_handle_change(e):
        nonlocal current_mode, status_label
        if e.control.selected:
            #集合(set)から最初の値を取り出す
            val = list(e.control.selected)[0]
            current_mode = str(val)
            #更新時も「リスト」で上書きする
            choice_segment.selected = [current_mode]

            #モードに合わせてドロップダウンの選択肢を差し替える
            if current_mode == "Expense":
                category_dropdown.options = options_expense
            elif current_mode == "Income":
                category_dropdown.options = options_income

            # 選択肢が変わったので、現在選ばれている値はリセットするのが安全
            category_dropdown.value = None

            status_label = ft.Text("", color="green", weight="bold")

            await refresh_view()

    #部品の定義
    choice_segment = ft.SegmentedButton(
        selected=["Expense"],  
        allow_multiple_selection=False,
        on_change= mode_handle_change,
        segments=[
            ft.Segment(value="Expense", label=ft.Text("Expense")),
            ft.Segment(value="Income", label=ft.Text("Income")),
            ft.Segment(value="Analysis", label=ft.Text("Analysis"))
        ],
    )


    #日付入力部分の作成
    #日付はdate_inputに格納。デフォルトでは今日の日付today YYYY-MM-DD を代入
    today = datetime.now().strftime("%Y-%m-%d")
    date_input = today

    #選択した日付を表示する部分
    date_label = ft.Text(f"date: {date_input}", color="white", weight="bold",size=20)

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
        keyboard_type=ft.KeyboardType.NUMBER,
        border_color="bluegrey900",  # ここで色を指定！
        focused_border_color="blue400" # 入力中に枠線の色を変える設定（視認性アップ）
        )
    
    #カテゴリ作成

    options_expense = [
            ft.dropdown.Option("Wagner"),
            ft.dropdown.Option("SYC"),
            ft.dropdown.Option("交通"),
            ft.dropdown.Option("食費"),
            ft.dropdown.Option("交際"),
            ft.dropdown.Option("勉強,研究"),
            ft.dropdown.Option("電話"),
            ft.dropdown.Option("娯楽"),
            ft.dropdown.Option("美容"),
            ft.dropdown.Option("税"),
            ft.dropdown.Option("衣服"),
            ft.dropdown.Option("旅行"),
            ft.dropdown.Option("給与誤差脱漏"),
            ft.dropdown.Option("医療"),
            ft.dropdown.Option("その他"),
        ]
    
    options_income = [
            ft.dropdown.Option("FreeStep"),
            ft.dropdown.Option("お小遣い"),
            ft.dropdown.Option("その他"),
        ]

    category_dropdown = ft.Dropdown(
        label="カテゴリ",
        options= options_expense ,
        border_color="bluegrey900",  # ここで色を指定！
        focused_border_color="blue400" # 入力中に枠線の色を変える設定（視認性アップ）
    )

    #説明欄の初期設定
    content_input = ft.TextField(
        label = "説明",
        keyboard_type=ft.KeyboardType.TEXT,
        multiline = True,
        min_lines=3,
        border_color="bluegrey900",  # ここで色を指定！
        focused_border_color="blue400" # 入力中に枠線の色を変える設定（視認性アップ）
    )

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

            
            #日付,モード,金額,カテゴリ,説明,記録入力日時を含むリスト "record"を作成
            #金額については、全角数字で書かれていた場合でもfloat型になおす
            #Expenseモードの選択時のみ、数値に対して自動で「-」をつける

            if current_mode == "Expense":
                kingaku = (-1)*float(amount_input.value)
            else:
                kingaku = float(amount_input.value)

            record = [date_input,current_mode,kingaku, category_dropdown.value,content_input.value,datetime.now().strftime("%Y-%m-%d-%H-%M-%S")]
            
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
    
    await refresh_view()

ft.app(target=main)
