import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import asyncio
from datetime import timedelta
import uuid

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

#アプリからスプシ内容の修正と削除を行う関数　UpdateOrDeleteSheet()
# 特定のUUIDを持つ行を探して更新・削除する関数
def UpdateOrDeleteSheet(target_uuid, new_record=None, mode="UPDATE"):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('秘密鍵-kakeibofrom202602032126.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("家計簿テストver202602032139").sheet1
    
    # 1. G列(UUIDの列)を全部取得して、何行目にあるか探す
    uuid_list = sheet.col_values(7) # 7列目(G列)
    try:
        # スプシは1行目が見出しなので index+1 行目
        row_index = uuid_list.index(target_uuid) + 1
        
        if mode == "UPDATE":
            # 指定した範囲（A列〜G列）を新しいデータで上書き
            sheet.update(f"A{row_index}:G{row_index}", [new_record])
        elif mode == "DELETE":
            # その行を削除
            sheet.delete_rows(row_index)
    except ValueError:
        print("指定されたUUIDが見つかりませんでした")

#スプシからの読み込みを行う関数　Yomikomi()
#戻り値dataは、リスト[['日付', 'モード', '金額', 'カテゴリ', '内容', '記録した日時','UUID'], ...]
def Yomikomi():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('秘密鍵-kakeibofrom202602032126.json', scope)
    client = gspread.authorize(creds)
    SHEET_NAME = "家計簿テストver202602032139" 
    sheet = client.open(SHEET_NAME).sheet1
    
    # 全データを取得（1行目は見出しと想定）
    data = sheet.get_all_values()
    return data

#ページを駆動する部分
async def main(page: ft.Page):
    page.title = "test-アプリ-202602060835"
    page.window_width = 400
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.DARK

    #モード切替(Expense/Income/Analysis)
    current_mode = "Expense"

    #カテゴリ選択を横スクロールにするための準備(初期値、動作設定)
    selected_category = None

    options_expense_list = ["Wagner", "SYC", "交通", "食費", "交際", "勉強,研究", "電話", "娯楽", "美容", "税", "衣服", "旅行", "給与誤差脱漏", "医療", "その他"]
    options_income_list = ["FreeStep", "お小遣い", "その他"]

    # チップが押されたときの動作
    async def on_category_select(e):
        nonlocal selected_category
        # すべてのチップの選択状態を一度オフにする（単一選択にするため）
        for chip in category_chips.controls:
            chip.selected = False
        # 押されたチップだけを光らせる
        e.control.selected = True
        selected_category = e.control.label.value
        page.update()

    #メッセージ表示するやつ(内容はのちのち変更)
    status_label = ft.Text("", color="green", weight="bold")

    #画面に部品を追加(Income/Expenseにおけるレイアウトの指定)
    async def make_recordingpage():
        page.add(
            ft.Row(
                [date_label, dateselect_button],
                alignment=ft.MainAxisAlignment.START # ラベルは左、ボタンは右
            ),
            amount_input,
            ft.Text("カテゴリを選択", size=12, color="grey500"),
            category_chips,
            content_input,
            save_button,
            status_label
        )
    
    #画面に部品を追加(Analysisにおけるレイアウトの指定)
    # ソート状態の管理（どの列か、昇順か）
    sort_column_index = 0  # 0:日付, 1:カテゴリ, 2:金額...
    sort_ascending = False   # True:昇順, False:降順

    #Analysisモードの画面を作製する関数　make_analysispage()
    async def make_analysispage():
    
    # --- 検索パネルと記録一覧の表示 ---
        page.add(ft.Text("記録一覧", size=25, weight="bold"))
        #Analysisモードにおける修正用ダイアログを表示する関数
        async def open_edit_dialog(row_data):
            # --- 1. 選択状態を管理する変数 ---
            # 初期値は今のデータから持ってくる
            current_edit_mode = row_data[1] 
            current_edit_category = row_data[3]

            # モード選択用チップの作成 ---
            mode_choice_expense = ft.Chip(
                label=ft.Text("Expense"),
                selected=(current_edit_mode == "Expense"),
                on_select=lambda e: update_mode("Expense"),
                show_checkmark=True, # 選択時にチェックマークを出すと分かりやすいです
                selected_color=ft.Colors.ORANGE_ACCENT,
            )
            mode_choice_income = ft.Chip(
                label=ft.Text("Income"),
                selected=(current_edit_mode == "Income"),
                on_select=lambda e: update_mode("Income"),
                show_checkmark=True,
                selected_color=ft.Colors.GREEN_400,
            )

            # モードが切り替わった時に変数を更新する関数
            def update_mode(mode_name):
                nonlocal current_edit_mode,all_categories,category_row
                current_edit_mode = mode_name
                # 見た目を更新するためにチップの選択状態を書き換える
                mode_choice_expense.selected = (mode_name == "Expense")
                mode_choice_income.selected = (mode_name == "Income")
                if mode_name == "Expense":
                    all_categories = list(set(options_expense_list))
                if mode_name == "Income":
                    all_categories = list(set(options_income_list))
                
                category_row.controls = [
                    ft.Chip(
                        label=ft.Text(cat),
                        selected=(current_edit_category == cat),
                        on_select=lambda e, c=cat: update_category(c),
                        show_checkmark=True,
                    ) for cat in all_categories
                ]
                page.update()

            # --- 3. カテゴリ選択用チップの作成 ---
            # すべての選択肢を統合
            all_categories = sorted(list(set(options_expense_list + options_income_list)))
            
            category_row = ft.Row(wrap=False,scroll=ft.ScrollMode.ADAPTIVE,spacing=5)
            
            def update_category(cat_name):
                nonlocal current_edit_category
                current_edit_category = cat_name
                # すべてのチップの選択状態を更新
                for chip in category_row.controls:
                    chip.selected = (chip.label.value == cat_name)
                page.update()

            category_row.controls = [
                ft.Chip(
                    label=ft.Text(cat),
                    selected=(current_edit_category == cat),
                    on_select=lambda e, c=cat: update_category(c),
                    show_checkmark=True,
                ) for cat in all_categories
            ]
            edit_category = ft.TextField(label="カテゴリ", value=row_data[3])
            edit_amount = ft.TextField(label="金額", value=str(abs(float(row_data[2]))))
            edit_content = ft.TextField(label="メモ",multiline=True, value=row_data[4])
            
            # 「保存」を押したときの処理
            async def on_save(e):
                status_label.value = "保存中..."
                page.update()
                # 新しい金額を計算
                new_kingaku = float(edit_amount.value) * (-1 if row_data[1] == "Expense" else 1)
                # UUID(index 6)や日付などはそのまま維持したリストを作る
                updated_record = [row_data[0], current_edit_mode, new_kingaku, current_edit_category, edit_content.value, row_data[5], row_data[6]]
                
                await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], updated_record, "UPDATE")
                dialog.open = False
                await refresh_view() # 画面更新

            # 「削除」を押したときの処理
            async def on_delete(e):
                status_label.value = "削除中..."
                page.update()
                await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], mode="DELETE")
                dialog.open = False
                await refresh_view()

            #編集/削除画面の表示要素を規定
            status_label = ft.Text("", color="orange", weight="bold")

            dialog = ft.AlertDialog(
                title=ft.Text("Edit/Delete"),
                content=ft.Column([
                    ft.Text("モード", size=12, color="grey500"),
                    ft.Row([mode_choice_expense, mode_choice_income]),
                    ft.Text("カテゴリ", size=12, color="grey500"),
                    category_row,
                    edit_amount, 
                    edit_content,
                    status_label
                    ], 
                    tight=True),
                actions=[
                    ft.Row(
                        [
                            # 左端：削除ボタン
                            ft.TextButton("削除", on_click=on_delete, icon_color="red"),
                            
                            # 中央〜右：キャンセルと保存をまとめる
                            ft.Row([
                                ft.TextButton("キャンセル", on_click=lambda _: setattr(dialog, "open", False)),
                                ft.TextButton("保存", on_click=on_save),
                            ], alignment=ft.MainAxisAlignment.END)
                        ],
                        # 削除ボタンと（キャンセル・保存セット）を両端に振り分ける
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN 
                    )
                ],
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()    

        #記録一覧の表示のメインルート(エラーがなければここを通る)
        try:
            loading_text = ft.Text("スプレッドシートを読み込み中...", color="orange")
            page.add(loading_text)
            page.update() # ここで一度、画面に「読み込み中」を出す

            # スプシからデータを取得
            raw_data = await asyncio.to_thread(Yomikomi)

            # 1行目は見出しなので残し、2行目以降（データ部分）だけを逆順にします
            header = raw_data[0]
            data_rows = raw_data[1:]

            # 見出しとソート後のデータを再結合
            display_data = [header] + data_rows

            # --- 【重要】ソートの実行 ---
            # lambdaを使って、指定されたインデックス（sort_column_index）の値で並び替え
            data_rows.sort(
                key=lambda x: x[sort_column_index] if sort_column_index != 2 else float(x[2]),
                reverse=not sort_ascending
            )
            # ※金額（index 2）の時は数値として比較するために float() 変換を入れるのがコツです。
            data_table = ft.DataTable(
                #高さ,幅
                data_row_min_height=20,    # 行の最小高さ
                data_row_max_height=40,    # 行の最大高さ
                heading_row_height=20,     # 見出し（ヘッダー）行の高さ
                column_spacing=10,         # 列同士の横の隙間

                sort_column_index=sort_column_index,
                sort_ascending=sort_ascending,
                columns=[
                    ft.DataColumn(ft.Text("日付"), on_sort=sort_column),
                    ft.DataColumn(ft.Text("カテゴリ"), on_sort=sort_column),
                    ft.DataColumn(ft.Text("金額"), numeric=True, on_sort=sort_column),
                    ft.DataColumn(ft.Text("内容"), on_sort=sort_column),
                    ft.DataColumn(ft.Text("edit")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(row[0], color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                            ft.DataCell(ft.Text(row[3], color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                            ft.DataCell(ft.Text(row[2], color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                            ft.DataCell(ft.Text(row[4],no_wrap=False, color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                            #↓編集用アイコンの設定
                            ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT,on_click=lambda e, r=row: page.run_task(open_edit_dialog, r)))                          
                        ]
                    ) for row in data_rows
                ],
            )
            page.add(ft.Column([data_table], scroll=ft.ScrollMode.ALWAYS, expand=True))

        except Exception as e: # どんなエラー（e）が起きたかを取得する
            # record が空の場合は、エラーメッセージを直接表示する
            status_label.value = f"エラー発生: {str(e)}" 
            status_label.color = "red"
            page.add(status_label)
            page.update()
            # コンソール（黒い画面）にも詳細を出す
            print(f"詳細エラーログ: {e}")
            page.update()

        #読み込み中　のメッセージを消去
        if loading_text in page.controls:
            page.controls.remove(loading_text)

    #画面を再読み込み（再構築）する関数を作る
    async def refresh_view():
        page.clean()  # いったん画面の中身を全部消す
        
        # モードによらず必ず表示するものを追加
        page.add(ft.Text("My家計簿ver202602051000", size=20),choice_segment)

        # モードに応じて表示し分ける
        if current_mode == "Analysis":
            # Analysisモードの表示内容
            await make_analysispage()
        else:
            # Expense / Income モードの表示内容
            await make_recordingpage()
        page.update() # 最後に画面を更新

    #Income/Expense/Analysisのモード切り替えについて
    async def mode_handle_change(e):
        nonlocal current_mode, status_label
        if e.control.selected:
            #集合(set)から最初の値を取り出す
            val = list(e.control.selected)[0]
            current_mode = str(val)
            #更新時も「リスト」で上書きする
            choice_segment.selected = [current_mode]

            # チップの中身を現在のモードに合わせて作り直す
            target_list = options_expense_list if current_mode == "Expense" else options_income_list
            category_chips.controls = [
                ft.Chip(
                    label=ft.Text(name),
                    selected=False,
                    on_select=on_category_select,
                    selected_color="blue700",
                    show_checkmark=True,
                ) for name in target_list
            ]

            selected_category = None # 選択をリセット

            status_label = ft.Text("", color="green", weight="bold")

            await refresh_view()

    async def sort_column(e):
        nonlocal sort_column_index, sort_ascending
        # クリックされた列のインデックスを取得
        sort_column_index = e.column_index
        # 昇順・降順を反転させる
        sort_ascending = not sort_ascending
        # 再描画
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
    
    #カテゴリ選択チップの作成
    category_chips = ft.Row(
        scroll=ft.ScrollMode.ADAPTIVE, # 横スクロールを有効に
        controls=[
            ft.Chip(
                label=ft.Text(name), # options_expenseの中身をチップにする
                selected=False,
                on_select=on_category_select,
                selected_color="blue700",
            ) for name in options_expense_list
        ]
    )

    #メモ欄の初期設定
    content_input = ft.TextField(
        label = "メモ",
        keyboard_type=ft.KeyboardType.TEXT,
        multiline = True,
        min_lines=3,
        border_color="bluegrey900",  # ここで色を指定！
        focused_border_color="blue400" # 入力中に枠線の色を変える設定（視認性アップ）
    )

    #入力された値をスプシに保存する関数
    async def save_to_sheets(e):
        nonlocal selected_category
        record = [] #関数の最初でrecord変数を初期化しておくことで、「recordが未定義」のエラーを防止

        try:
            if not amount_input.value or not selected_category :
                # 入力漏れがある場合
                status_label.color = "red"
                status_label.value = f"現在の入力:金額[{amount_input.value}],カテゴリ[{selected_category}]\n金額またはカテゴリが未記入です"
                page.update()
                return
            
            if  amount_input.value.isnumeric()== False:
                #金額欄に入力された文字列がすべて数字ならTrue,そうでなければFalseになる
                status_label.color = "red"
                status_label.value = f"現在の金額欄:{amount_input.value}\n金額欄には0以上の半角数字を入力"
                page.update()
                return

            
            #日付,モード,金額,カテゴリ,メモ,記録入力日時を含むリスト "record"を作成
            #金額については、全角数字で書かれていた場合でもfloat型になおす
            #Expenseモードの選択時のみ、数値に対して自動で「-」をつける

            if current_mode == "Expense":
                kingaku = (-1)*float(amount_input.value)
            else:
                kingaku = float(amount_input.value)

            #ここで、各記録に対して固有の整理番号UUIDを付与する
            #"id"だと組み込み関数と被ってしまうらしい
            id_value = str(uuid.uuid4())

            record = [date_input,current_mode,kingaku, selected_category, content_input.value,datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),id_value]
            
            #「保存中」メッセージを表示
            status_label.color = "orange"
            status_label.value = f"保存中...:{record[0:5:1]}"
            page.update()

            #スプシへの書き込み処理(非同期で実行)
            await asyncio.to_thread(Kakikomi, record)

            # 成功メッセージを作成
            status_label.color = "green"
            status_label.value = f"保存完了:{record[0:5:1]}"
            
            # 入力欄をクリア
            amount_input.value = ""
            selected_category = None
            content_input.value = ""
            for chip in category_chips.controls: chip.selected = False # チップの選択も解除
            page.update()

        except Exception as e: # どんなエラー（e）が起きたかを取得する
            # record が空の場合は、エラーメッセージを直接表示する
            status_label.value = f"エラー発生: {str(e)}" 
            status_label.color = "red"
            page.update()
            # コンソール（黒い画面）にも詳細を出す
            print(f"詳細エラーログ: {e}")
            page.update()

    #保存ボタン作成
    save_button = ft.Button("スプレッドシートに保存",icon="save",on_click=save_to_sheets) 


    #カレンダーを仕込んでおく
    page.overlay.append(date_picker)
    
    await refresh_view()

ft.run(main)
