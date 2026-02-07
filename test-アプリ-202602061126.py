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
# Analysisモードの画面を作製する関数
    async def make_analysispage():
        # --- 1. 検索状態の管理（ページを跨いでも保持） ---
        if not hasattr(page, "search_state"):
            page.search_state = {
                "keyword": "",
                "mode": None,
                "category": None
            }

        def update_search(key, value):
            page.search_state[key] = value

        # --- 2. 検索用UIパーツの定義 ---
        keyword_input = ft.TextField(
            label="キーワード検索(メモ)", 
            value=page.search_state["keyword"],
            on_change=lambda e: update_search("keyword", e.control.value),
            expand=True
        )

        # モード選択チップ
        mode_search_chips = ft.Row([
            ft.Chip(
                label=ft.Text("Expense"),
                selected=page.search_state["mode"] == "Expense",
                on_select=lambda e: (update_search("mode", "Expense" if e.selection else None), page.run_task(refresh_view))
            ),
            ft.Chip(
                label=ft.Text("Income"),
                selected=page.search_state["mode"] == "Income",
                on_select=lambda e: (update_search("mode", "Income" if e.selection else None), page.run_task(refresh_view))
            ),
        ])

        search_button = ft.Button(
            "この条件で検索", 
            icon=ft.Icons.SEARCH, 
            on_click=lambda _: page.run_task(refresh_view)
        )

        # --- 3. データの取得とフィルタリング ---
        try:
            raw_data = await asyncio.to_thread(Yomikomi)
            data_rows = raw_data[1:] # 見出しを除外

            filtered_data = []
            for row in data_rows:
                # キーワード絞り込み
                if page.search_state["keyword"] and page.search_state["keyword"].lower() not in row[4].lower():
                    continue
                # モード絞り込み
                if page.search_state["mode"] and row[1] != page.search_state["mode"]:
                    continue
                
                filtered_data.append(row)

            # 合計金額の計算
            total_sum = sum(float(row[2]) for row in filtered_data)

            # --- 4. 画面構成の追加 ---
            page.add(
                ft.ExpansionTile(
                    title=ft.Text("🔍 検索・絞り込み", size=18, weight="bold"),
                    controls=[
                        ft.Container(
                            content=ft.Column([
                                keyword_input,
                                ft.Text("モードで絞り込み", size=12, color="grey500"),
                                mode_search_chips,
                                ft.Row([search_button], alignment=ft.MainAxisAlignment.CENTER),
                            ]),
                            padding=10 
                        )
                    ],
                ),
                ft.Container(
                    content=ft.Text(f"現在の合計収支: ¥{total_sum:,.0f}", size=20, weight="bold", 
                                   color=ft.Colors.GREEN_400 if total_sum >= 0 else ft.Colors.ORANGE_ACCENT),
                    padding=10,
                    bgcolor=ft.Colors.WHITE10,
                    border_radius=10
                ),
                ft.Divider(),
                ft.Text("記録一覧", size=25, weight="bold")
            )

            # --- 5. 編集用ダイアログ関数の定義 ---
            async def open_edit_dialog(row_data):
                current_edit_mode = row_data[1]
                current_edit_category = row_data[3]

                edit_amount = ft.TextField(label="金額", value=str(abs(float(row_data[2]))))
                edit_content = ft.TextField(label="メモ", multiline=True, value=row_data[4])

                async def on_save(e):
                    new_kingaku = float(edit_amount.value) * (-1 if current_edit_mode == "Expense" else 1)
                    updated_record = [row_data[0], current_edit_mode, new_kingaku, current_edit_category, edit_content.value, row_data[5], row_data[6]]
                    await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], updated_record, "UPDATE")
                    dialog.open = False
                    await refresh_view()

                async def on_delete(e):
                    await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], mode="DELETE")
                    dialog.open = False
                    await refresh_view()

                dialog = ft.AlertDialog(
                    title=ft.Text("記録の編集・削除"),
                    content=ft.Column([edit_amount, edit_content], tight=True),
                    actions=[
                        ft.Row([
                            ft.TextButton("削除", on_click=on_delete, color="red"),
                            ft.Row([
                                ft.TextButton("キャンセル", on_click=lambda _: setattr(dialog, "open", False)),
                                ft.TextButton("保存", on_click=on_save),
                            ])
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ]
                )
                page.overlay.append(dialog)
                dialog.open = True
                page.update()

            # --- 6. DataTableの作成 ---
            data_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("日付")),
                    ft.DataColumn(ft.Text("カテゴリ")),
                    ft.DataColumn(ft.Text("金額"), numeric=True),
                    ft.DataColumn(ft.Text("内容")),
                    ft.DataColumn(ft.Text("edit")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(row[0], color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                            ft.DataCell(ft.Text(row[3])),
                            ft.DataCell(ft.Text(row[2])),
                            ft.DataCell(ft.Text(row[4], no_wrap=False)),
                            ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT, on_click=lambda e, r=row: page.run_task(open_edit_dialog, r))),
                        ]
                    ) for row in filtered_data
                ],
            )
            page.add(ft.Column([data_table], scroll=ft.ScrollMode.ALWAYS, expand=True))

        except Exception as e:
            page.add(ft.Text(f"エラー発生: {e}", color="red"))

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
