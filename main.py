import flet as ft
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import asyncio
from datetime import timedelta
import uuid
import math
import os
from dotenv import load_dotenv
from pathlib import Path

# 1. このプログラム本体 (main.py) が置いてあるフォルダの絶対パスを特定する
BASE_DIR = Path(__file__).parent

# 2. 各ファイルへの「確実な住所」を作成する
JSON_KEY_PATH = BASE_DIR / "秘密鍵-kakeibofrom202602032126.json"
ENV_PATH = BASE_DIR / ".env"

# .env の読み込みもこれに合わせると確実です
load_dotenv(dotenv_path=ENV_PATH)


# .envファイルを読み込む
load_dotenv()
# 変数名（Key）を指定して値を取得
spreadsheet_key = os.getenv("MYKAKEIBO_SPREADSHEET_NAME")

#スプシへの書き込みを行う関数 Kakikomi()
def Kakikomi(record):
    # 1.認証フェーズ（「通行証」の準備）ーーーーーーーーーーーーーーーーー
    #scope: 「このアプリはGoogleドライブのどの範囲まで触っていいか？」という権限の範囲を定義しています。
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

    #creds: ~.json（秘密鍵）を読み込み、「私は許可されたプログラムです」というデジタルな通行証を作成しています。
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope) # ここにファイル名

    # 2. 接続フェーズ（「扉」を開ける）
    #authorize: 通行証をGoogleのサーバーに提示し、操作を許可してもらいます。
    client = gspread.authorize(creds)
    #open: インターネット上にある膨大なファイルの中から、名前を頼りに特定のシートを見つけて接続を確立します。
    SHEET_NAME = spreadsheet_key 
    sheet = client.open(SHEET_NAME).worksheet("Recordings")

    # 3. 操作フェーズ（「命令」を送る）
    #append_row: 「一番下の空いている行に、このリストの内容を書き込め」という命令を送ります。
    sheet.append_row(record)
    #この瞬間、PythonからGoogleのサーバーへデータが送信され、スプレッドシートがリアルタイムで更新されます。

    print(f"書き込み成功：内容{record}")

#アプリからスプシ内容の修正と削除を行う関数　UpdateOrDeleteSheet()
# 特定のUUIDを持つ行を探して更新・削除する関数
def UpdateOrDeleteSheet(target_uuid, new_record=None, mode="UPDATE"):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope)
    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_key).worksheet("Recordings")
    
    # 1. G列(UUIDの列)を全部取得して、何行目にあるか探す
    uuid_list = sheet.col_values(7) # 7列目(G列)

    try:
        # スプシは1行目が見出しなので index+1 行目
        row_index = uuid_list.index(target_uuid) + 1
        
        if mode == "UPDATE":
            # 指定した範囲（A列〜G列）を新しいデータで上書き
            sheet.update(range_name=f"A{row_index}:G{row_index}", values=[new_record])
        elif mode == "DELETE":
            # その行を削除
            sheet.delete_rows(row_index)
    except ValueError:
        print("指定されたUUIDが見つかりませんでした")

#スプシからの読み込みを行う関数　Yomikomi()
#戻り値dataは、リスト[['日付', 'モード', '金額', 'カテゴリ', '内容', '記録した日時','UUID'], ...]
def Yomikomi():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope)
    client = gspread.authorize(creds)
    SHEET_NAME = spreadsheet_key 
    sheet = client.open(SHEET_NAME).worksheet("Recordings")
    
    # 全データを取得（1行目は見出しと想定）
    data = sheet.get_all_values()
    return data

# カテゴリ設定を読み込む関数 LoadCategories()
def LoadCategories():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope)
    client = gspread.authorize(creds)
    SHEET_NAME = spreadsheet_key
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope)
        client = gspread.authorize(creds)
        SHEET_NAME = spreadsheet_key
        sheet = client.open(SHEET_NAME).worksheet("Settings")
        # 1列目(Expense)と2列目(Income)を取得（1行目は見出しなので除外）
        expense_list = [x for x in sheet.col_values(1)[1:] if x] # 空文字除去
        income_list = [x for x in sheet.col_values(2)[1:] if x]
        return expense_list, income_list
    except gspread.exceptions.WorksheetNotFound:
        print("Settingsシートが見つかりません。デフォルト値を使用します。")
        return [], []
    except Exception as e:
        print(f"カテゴリ読み込みエラー: {e}")
        return [], []

# カテゴリ設定を保存する関数 SaveCategories()
def SaveCategories(expense_list, income_list):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH), scope)
    client = gspread.authorize(creds)
    SHEET_NAME = spreadsheet_key
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(JSON_KEY_PATH).json, scope)
        client = gspread.authorize(creds)
        SHEET_NAME = spreadsheet_key
        sheet = client.open(SHEET_NAME).worksheet("Settings")
        
        # データを作成（見出し + データ）
        # 行ごとに [Expenseカテゴリ, Incomeカテゴリ] の形にする必要がある
        rows = [["Expense", "Income"]] # ヘッダー
        
        max_len = max(len(expense_list), len(income_list))
        for i in range(max_len):
            exp = expense_list[i] if i < len(expense_list) else ""
            inc = income_list[i] if i < len(income_list) else ""
            rows.append([exp, inc])
            
        # シートをクリアして書き込み
        sheet.clear()
        sheet.update(range_name="A1", values=rows)
        print("カテゴリ設定を保存しました")
        
    except Exception as e:
        print(f"カテゴリ保存エラー: {e}")



#ページを駆動する部分
async def main(page: ft.Page):

    from pathlib import Path
    
    # 画像ファイルへの絶対パスを作る
    BASE_DIR = Path(__file__).parent
    ICON_PATH = BASE_DIR / "Icon_2026-03-09-000233.ico" # 用意した画像の名前に合わせてください
    
    if ICON_PATH.exists():
        page.window.icon = str(ICON_PATH) # タスクバーのアイコンを変更
    print(spreadsheet_key)

    # 現在実行中のメインタスクを保持する変数
    current_task = None

    page.title = "MyKAKEIBO ver.202603090029"
    page.window.width = 400
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.DARK

    # 起動時の読み込みメッセージを表示
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.add(
        ft.Column(
            [
                ft.Text("My家計簿", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Icon(name=ft.Icons.SAVINGS, size=100, color=ft.Colors.WHITE),
                ft.Text("設定を読み込み中...", size=16, color=ft.Colors.ORANGE),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    page.update()

    #モード切替(Expense/Income/Analysis)
    current_mode = "Expense"

    #カテゴリ選択を横スクロールにするための準備(初期値、動作設定)
    selected_category = None
    
    # --- カテゴリの初期化（スプシから読み込み、なければデフォルト） ---
    loaded_expense, loaded_income = await asyncio.to_thread(LoadCategories)
    
    if loaded_expense:
        options_expense_list = loaded_expense
    else:
        options_expense_list = ["Wagner", "SYC", "交通", "食費", "交際", "勉強,研究", "電話", "娯楽", "美容", "税", "衣服", "旅行", "給与誤差脱漏", "医療", "その他"]
        
    if loaded_income:
        options_income_list = loaded_income
    else:
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

    # --- カテゴリ編集ダイアログ ---
    async def open_category_settings(e):
        # 現在のモードのリストを参照
        target_list = options_expense_list if current_mode == "Expense" else options_income_list
        
        new_cat_input = ft.TextField(label="新しいカテゴリ", expand=True, height=40, text_size=14)
        
        # カテゴリリストを表示するColumn
        cat_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, height=300)

        async def render_cat_list():
            cat_list_col.controls.clear()
            # リストをスプレッドシートの順序（リストの順序）で表示
            for cat in target_list:
                cat_list_col.controls.append(
                    ft.Row([
                        ft.Text(cat, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE, 
                            icon_color="red", 
                            data=cat,
                            on_click=delete_category
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            if settings_dialog.open: # ダイアログが開いている時だけ更新
                page.update()

        async def add_category(e):
            if new_cat_input.value and new_cat_input.value not in target_list:
                target_list.append(new_cat_input.value)
                new_cat_input.value = ""
                # スプシに保存
                await asyncio.to_thread(SaveCategories, options_expense_list, options_income_list)
                await render_cat_list()
                page.update()

        async def delete_category(e):
            cat_name = e.control.data
            if cat_name in target_list:
                target_list.remove(cat_name)
                # スプシに保存
                await asyncio.to_thread(SaveCategories, options_expense_list, options_income_list)
                await render_cat_list()
                page.update()

        async def close_settings_dialog(e):
            settings_dialog.open = False
            page.update()
            await asyncio.sleep(0.1)
            page.overlay.remove(settings_dialog)
            page.update()
            await refresh_view()
            page.update() # 画面更新してチップに反映

        settings_dialog = ft.AlertDialog(
            title=ft.Text(f"{current_mode} カテゴリ編集"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([new_cat_input, ft.IconButton(icon=ft.Icons.ADD, on_click=add_category)]),
                    ft.Divider(),
                    cat_list_col
                ], tight=True),
                width=300
            ),
            actions=[
                ft.TextButton("閉じる", on_click=close_settings_dialog)
            ]
        )
        
        # 初回描画
        await render_cat_list()

        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    # --- 簡易電卓機能 ---
    calc_input = ft.TextField(label="計算欄", hint_text="例: 1170 * (40/60)", expand=True, text_size=14)
    calc_result = ft.TextField(label="計算結果", read_only=True, value="", text_size=14)

    def on_calculate(e):
        try:
            if not calc_input.value:
                return
            # Pythonの記法で計算
            result = eval(calc_input.value, {"__builtins__": None}, {})
            
            # 整数なら.0を表示しない
            if isinstance(result, (int, float)):
                if result == int(result):
                    result = int(result)
            
            calc_result.value = str(result)
        except Exception:
            calc_result.value = "Error"
        page.update()

    calc_button = ft.ElevatedButton("計算", on_click=on_calculate)

    #画面に部品を追加(Income/Expenseにおけるレイアウトの指定)
    async def make_recordingpage():
        nonlocal status_label
        
        # カテゴリ設定ボタン
        settings_button = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            tooltip="カテゴリの追加・削除",
            on_click=open_category_settings
        )

        page.add(
            ft.Row(
                [date_label, dateselect_button],
                alignment=ft.MainAxisAlignment.START # ラベルは左、ボタンは右
            ),
            amount_input,
            ft.Text("カテゴリを選択", size=12, color="grey500"),
            category_chips,
            content_input,
            ft.Row([
                save_button,
                settings_button
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            status_label,
            
            ft.Text("簡易電卓", size=12, color="grey500"),
            ft.Row([calc_input, calc_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            calc_result
        )
    
    #画面に部品を追加(Analysisにおけるレイアウトの指定)
    # ソート状態の管理（どの列か、昇順か）
    sort_column_index = 0  # 0:日付, 1:カテゴリ, 2:金額...
    sort_ascending = False   # True:昇順, False:降順

    #Analysisモードの画面を作製する関数　make_analysispage()
    async def make_analysispage():
        
        # エラー表示用に事前に定義しておく
        status_label = ft.Text("", color="green", weight="bold")

        # データ読み込み前にボタンが押された場合の対策
        filtered_data_rows = []

        # --- 検索条件をページに記憶させる（リセット防止） ---
        if not hasattr(page, "filter_query"):
            page.filter_query = [None, None, None, None, None, None, None]

# --- 詳細レポート（円グラフ）を表示する関数（最新版 0.25.0対応） ---
        async def open_detailed_report(e):
            expense_summary = {}
            income_summary = {}
            
            # データの集計
            for row in filtered_data_rows:
                mode = row[1]
                amt = abs(float(row[2])) if row[2] != "" else 0
                cat = row[3]
                if mode == "Expense":
                    expense_summary[cat] = expense_summary.get(cat, 0) + amt
                else:
                    income_summary[cat] = income_summary.get(cat, 0) + amt

            # 集計データをソート（金額の降順）
            sorted_expense = sorted(expense_summary.items(), key=lambda x: x[1], reverse=True)
            sorted_income = sorted(income_summary.items(), key=lambda x: x[1], reverse=True)

            def create_semicircle_chart_and_table(sorted_data, is_expense=True):
                if not sorted_data:
                    return ft.Text("データなし")

                total_val = sum(v for k, v in sorted_data)
                
                # 色と表示形式の設定
                total_color = "orange" if is_expense else "green"
                total_text = f"-¥{total_val:,.0f}" if is_expense else f"¥{total_val:,.0f}"

                palette = [ft.Colors.BLUE, ft.Colors.RED, ft.Colors.GREEN, 
                           ft.Colors.AMBER, ft.Colors.PURPLE, ft.Colors.CYAN, ft.Colors.ORANGE, ft.Colors.TEAL, ft.Colors.PINK]
                
                sections = []
                table_rows = []

                # データ部分のセクション作成
                for i, (cat, val) in enumerate(sorted_data):
                    rank = i + 1
                    percentage = (val / total_val) * 100 if total_val > 0 else 0
                    color = palette[i % len(palette)]
                    
                    # グラフ用セクション（順位のみ表示）
                    sections.append(
                        ft.PieChartSection(
                            value=val,
                            title=str(rank),
                            color=color,
                            radius=50,
                            title_style=ft.TextStyle(size=12, weight="bold", color="white"),
                        )
                    )
                    
                    # テーブル用行（順位/カテゴリ名/割合/金額）
                    table_rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Container(
                                    content=ft.Text(str(rank), color="white", size=9, weight="bold"),
                                    bgcolor=color,
                                    border_radius=10,
                                    width=16, height=16,
                                    alignment=ft.alignment.center
                                )),
                                ft.DataCell(ft.Text(cat, size=12)),
                                ft.DataCell(ft.Text(f"{percentage:.1f}%", size=12)),
                                ft.DataCell(ft.Text(f"¥{val:,.0f}", size=12)),
                            ]
                        )
                    )

                # 半円にするための透明なダミーセクション（合計値と同じサイズ）
                sections.append(
                    ft.PieChartSection(
                        value=total_val,
                        title="",
                        color=ft.Colors.TRANSPARENT,
                        radius=50
                    )
                )

                # チャートの構築
                # start_degree_offset=180 で9時の位置から開始
                # 時計回りにデータが配置され、下半分（透明）で円が閉じる
                chart = ft.PieChart(
                    sections=sections,
                    sections_space=0,
                    center_space_radius=40,
                    start_degree_offset=180,
                    expand=True
                )

                # チャートと合計金額を重ねるためのStack
                chart_stack = ft.Stack(
                    [
                        chart,
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Total", size=10, color="grey"),
                                ft.Text(total_text, size=14, weight="bold", color=total_color)
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            alignment=ft.alignment.center,
                            padding=ft.padding.only(bottom=10) # 中心より少し上に配置
                        )
                    ],
                    alignment=ft.alignment.center
                )

                # テーブルの構築
                table = ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("順位")),
                        ft.DataColumn(ft.Text("カテゴリ")),
                        ft.DataColumn(ft.Text("割合")),
                        ft.DataColumn(ft.Text("金額")),
                    ],
                    rows=table_rows,
                    heading_row_height=0,
                    data_row_min_height=18,
                    column_spacing=10
                )

                # レイアウト調整
                # チャートの下半分は透明なので、高さを制限して余白を削る工夫
                return ft.Column([
                    ft.Container(
                        chart_stack, 
                        height=180, # 円全体(直径180)が収まる高さを確保して描画崩れを防ぐ
                        alignment=ft.alignment.center,
                        # bottomのマイナスを減らして、下のテーブルとの間隔を確保（食い込み防止）
                        margin=ft.margin.only(top=0, bottom=-70) 
                    ), 
                    table
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)

            # コンテンツ生成
            expense_content = create_semicircle_chart_and_table(sorted_expense, is_expense=True)
            income_content = create_semicircle_chart_and_table(sorted_income, is_expense=False)

            def close_report(e):
                report_dialog.open = False
                page.update()


            # ダイアログの表示
            report_dialog = ft.AlertDialog(
                title=ft.Text("収支内訳レポート"),
                content=ft.Container(
                    width=900,
                    height=500,
                    content=ft.Row([
                        ft.Container(
                            width=220, 
                            content=ft.Column([
                                ft.Text("支出の内訳", color="orange", weight="bold"),
                                expense_content,
                            ], scroll=ft.ScrollMode.AUTO)
                        ),
                        ft.VerticalDivider(width=1, color="grey"),
                        ft.Container(
                            width=220, 
                            content=ft.Column([
                                ft.Text("収入の内訳", color="green", weight="bold"),
                                income_content,
                            ], scroll=ft.ScrollMode.AUTO)
                        ),
                    ], scroll=ft.ScrollMode.AUTO, vertical_alignment=ft.CrossAxisAlignment.START)
                ),
                actions=[
                    ft.TextButton("閉じる", on_click=close_report)
                ]
            )
            page.overlay.append(report_dialog)
            report_dialog.open = True
            page.update()

        # --- Timeline (推移グラフ) を表示する関数 ---
        async def open_timeline_dialog(e):
            if not filtered_data_rows:
                return

            # 1. データを日付順にソート
            sorted_rows = sorted(filtered_data_rows, key=lambda x: x[0])

            # 2. 日付ごとに集計
            daily_summary = {} 
            for row in sorted_rows:
                d = row[0]
                mode = row[1]
                val = float(row[2]) if row[2] else 0
                if d not in daily_summary:
                    daily_summary[d] = {"income": 0, "expense": 0}
                if mode == "Income":
                    daily_summary[d]["income"] += val
                elif mode == "Expense":
                    daily_summary[d]["expense"] += val

            # 3. 累積データを計算
            dates = sorted(daily_summary.keys())
            
            # データポイント作成
            data_inc, data_exp, data_bal ,data_date = [], [], [], []
            cum_inc, cum_exp, cum_bal = 0, 0, 0
            
            # タイムスタンプ変換用
            def to_ts(date_str):
                return datetime.strptime(date_str, "%Y-%m-%d").timestamp()

            min_x = to_ts(dates[0])
            max_x = to_ts(dates[-1])
            
            # 1日分の秒数
            day_seconds = 24 * 60 * 60
            # 期間が短すぎる場合の調整
            if max_x == min_x:
                max_x += day_seconds

            for d in dates:
                inc = daily_summary[d]["income"]
                exp = daily_summary[d]["expense"]
                
                cum_inc += inc
                cum_exp += abs(exp) # 支出は絶対値
                cum_bal += (inc + exp)
                
                ts = to_ts(d)
                rel_x = ts - min_x # 開始日を0とする相対座標に変換
                
                # ツールチップに日付と金額を表示
                # tooltip プロパティに直接文字列を入れるのではなく、
                # 文字列が確実にクリーンな状態（余計な引用符がない状態）で渡るようにします。
                data_inc.append(ft.LineChartDataPoint(rel_x, cum_inc, tooltip=f"+{cum_inc:,.0f}|+{inc:,.0f}"))
                data_exp.append(ft.LineChartDataPoint(rel_x, cum_exp, tooltip=f"-{cum_exp:,.0f}|-{abs(exp):,.0f}"))
                data_bal.append(ft.LineChartDataPoint(rel_x, cum_bal, tooltip=f"{cum_bal:,.0f}|{inc + exp:,.0f} \n {d}"))

            # 4. 表示切り替え用のステート
            show_date = True
            show_inc = False
            show_exp = False
            show_bal = True

            # 5. グラフ更新関数
            def update_graph(e=None):
                nonlocal show_inc, show_exp, show_bal
                
                if e:
                    if e.control.data == "inc": show_inc = not show_inc
                    if e.control.data == "exp": show_exp = not show_exp
                    if e.control.data == "bal": show_bal = not show_bal

                # ボタンの見た目更新
                btn_inc.icon = ft.Icons.CHECK_BOX if show_inc else ft.Icons.CHECK_BOX_OUTLINE_BLANK
                btn_inc.style = ft.ButtonStyle(color=ft.Colors.GREEN if show_inc else ft.Colors.GREY)
                
                btn_exp.icon = ft.Icons.CHECK_BOX if show_exp else ft.Icons.CHECK_BOX_OUTLINE_BLANK
                btn_exp.style = ft.ButtonStyle(color=ft.Colors.RED if show_exp else ft.Colors.GREY)
                
                btn_bal.icon = ft.Icons.CHECK_BOX if show_bal else ft.Icons.CHECK_BOX_OUTLINE_BLANK
                btn_bal.style = ft.ButtonStyle(color=ft.Colors.CYAN if show_bal else ft.Colors.GREY)

                line_series = []
                all_visible_points = []

                if show_inc and data_inc:
                    line_series.append(ft.LineChartData(data_inc, color=ft.Colors.GREEN, stroke_width=3))
                    all_visible_points.extend(data_inc)
                if show_exp and data_exp:
                    line_series.append(ft.LineChartData(data_exp, color=ft.Colors.RED, stroke_width=3))
                    all_visible_points.extend(data_exp)
                if show_bal and data_bal:
                    line_series.append(ft.LineChartData(data_bal, color=ft.Colors.CYAN, stroke_width=3))
                    all_visible_points.extend(data_bal)

                # --- Y軸（金額）の計算: キリのいい間隔にする ---
                if all_visible_points:
                    vals = [p.y for p in all_visible_points]
                    raw_min_y, raw_max_y = min(vals), max(vals)
                else:
                    raw_min_y, raw_max_y = 0, 100

                # レンジ計算
                y_range = raw_max_y - raw_min_y
                if y_range == 0: y_range = 100

                # キリのいいインターバルを計算 (1, 2, 5の倍数×10のn乗)
                target_steps = 5
                rough_step = y_range / target_steps
                magnitude = 10 ** math.floor(math.log10(rough_step)) if rough_step > 0 else 1
                normalized_step = rough_step / magnitude
                
                if normalized_step <= 1: nice_step = 1
                elif normalized_step <= 2: nice_step = 2
                elif normalized_step <= 5: nice_step = 5
                else: nice_step = 10
                
                y_interval = nice_step * magnitude

                # min_y, max_y をインターバルの倍数に広げて余裕を持たせる
                chart.min_y = math.floor(raw_min_y / y_interval) * y_interval - y_interval
                chart.max_y = math.ceil(raw_max_y / y_interval) * y_interval + y_interval

                chart.data_series = line_series
                chart.min_x = 0
                chart.max_x = max_x - min_x

                # --- X軸（日付）の計算: 間引き処理 ---
                duration = max_x - min_x
                day_sec = 24 * 3600
                
                # 画面幅に合わせてラベル数を制限（少し緩めて表示数を確保）
                if duration <= 14 * day_sec: # 2週間以内 -> 1日ごと
                    x_interval = day_sec
                    date_fmt = "%m/%d"
                elif duration <= 90 * day_sec: # 3ヶ月以内 -> 1週間ごと
                    x_interval = 7 * day_sec
                    date_fmt = "%m/%d"
                elif duration <= 365 * day_sec: # 1年以内 -> 1ヶ月ごと
                    x_interval = 30 * day_sec
                    date_fmt = "%Y/%m"
                elif duration <= 365 * 3 * day_sec: # 3年以内 -> 3ヶ月ごと
                    x_interval = 90 * day_sec
                    date_fmt = "%Y/%m"
                else: # それ以上 -> 1年(365日)ごと
                    x_interval = 365 * day_sec
                    date_fmt = "%Y"

                # 縦グリッド線 (薄い灰色)
                chart.vertical_grid_lines = ft.ChartGridLines(
                    interval=x_interval,
                    color=ft.Colors.with_opacity(0.2, ft.Colors.GREY),
                    width=1
                )

                # X軸ラベル生成
                labels = []
                # 相対座標(0スタート)でラベルを配置
                curr_rel_x = 0
                while curr_rel_x <= (max_x - min_x):
                    # 表示用テキストは絶対時刻(min_x + rel_x)に戻して生成
                    dt_obj = datetime.fromtimestamp(min_x + curr_rel_x)
                    labels.append(ft.ChartAxisLabel(value=curr_rel_x, label=ft.Text(dt_obj.strftime(date_fmt), size=10, weight="bold")))
                    curr_rel_x += x_interval

                chart.bottom_axis.labels = labels
                chart.bottom_axis.labels_interval = x_interval

                # 横グリッド線 (薄い灰色) - 計算済みのy_intervalを使用
                chart.horizontal_grid_lines = ft.ChartGridLines(
                    interval=y_interval,
                    color=ft.Colors.with_opacity(0.2, ft.Colors.GREY),
                    width=1
                )
                # 左軸ラベルの間隔も合わせる
                chart.left_axis.labels_interval = y_interval

                # サマリー表示 (Max/Min/Current)
                summary_col.controls.clear()
                def make_summary(label, data, color):
                    if not data: return None
                    vals = [p.y for p in data]
                    return ft.Row([
                        ft.Text(f"{label}: ", color=color, weight="bold"),
                        ft.Text(f"Current ¥{vals[-1]:,.0f} / Max ¥{max(vals):,.0f} / Min ¥{min(vals):,.0f}", size=12)
                    ], spacing=5)

                if show_bal: summary_col.controls.append(make_summary("Balance", data_bal, ft.Colors.CYAN))

                if e:
                    timeline_dialog.update()

            # UI部品
            btn_inc = ft.TextButton("Income", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="inc")
            btn_exp = ft.TextButton("Expense", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="exp")
            btn_bal = ft.TextButton("Balance", icon=ft.Icons.CHECK_BOX, on_click=update_graph, data="bal")
            
            chart = ft.LineChart(expand=True, border=ft.border.all(1, ft.Colors.GREY_800),
                                 left_axis=ft.ChartAxis(labels_size=40), bottom_axis=ft.ChartAxis(labels_size=32),
                                 tooltip_bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.GREY_900),
                                )
            summary_col = ft.Column()

            async def close_timeline(e):
                timeline_dialog.open = False
                page.update()
                await asyncio.sleep(0.1)
                if timeline_dialog in page.overlay:
                    page.overlay.remove(timeline_dialog)
                    page.update()

            timeline_dialog = ft.AlertDialog(
                title=ft.Text("推移グラフ"),
                content=ft.Container(width=700, height=500, content=ft.Column([
                    ft.Row([btn_inc, btn_exp, btn_bal], alignment=ft.MainAxisAlignment.CENTER),
                    summary_col, ft.Container(chart, expand=True, padding=10)])),
                actions=[ft.TextButton("閉じる", on_click=close_timeline)]
            )
            page.overlay.append(timeline_dialog); timeline_dialog.open = True; update_graph(); page.update()

        #検索窓呼び出しアイコン,詳細レポート呼び出しアイコンを描画
        page.add(
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.MANAGE_SEARCH, 
                        icon_size=25, # 文字のサイズに合わせると綺麗です
                        on_click=lambda _: page.run_task(open_filter_dialog),
                        tooltip="絞り込み条件を開く" # ホバーした時に説明が出ます
                    ),
                    ft.Text("←filtering", size=10, weight="bold"),

                    ft.IconButton(
                        icon=ft.Icons.PIE_CHART, 
                        icon_size=25, # 文字のサイズに合わせると綺麗です
                        on_click= open_detailed_report,
                        tooltip="詳細な分析を開く" # ホバーした時に説明が出ます
                    ),
                    ft.Text("←detailed report", size=10, weight="bold"),

                    ft.IconButton(
                        icon=ft.Icons.SHOW_CHART, 
                        icon_size=25, 
                        on_click=open_timeline_dialog,
                        tooltip="推移を表示" 
                    ),
                    ft.Text("←timeline", size=10, weight="bold"),
                ],
                alignment=ft.MainAxisAlignment.START, # 左寄せにする（これで隣接します）
                vertical_alignment=ft.CrossAxisAlignment.CENTER, # 上下の中央を揃える
                spacing=5 # 文字とアイコンの間の距離（お好みで調整してください）
            )
        )

        #Analysisモードにおける修正用ダイアログを表示する関数
        async def open_edit_dialog(row_data):
            # --- 1. 選択状態を管理する変数 ---
            # 初期値は今のデータから持ってくる
            current_edit_mode = row_data[1] 
            current_edit_category = row_data[3]
            current_edit_date = row_data[0]

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

            # --- 日付変更用のDatePicker設定 ---
            async def on_edit_date_change(e):
                nonlocal current_edit_date
                if e.control.value:
                    current_edit_date = e.control.value.strftime("%Y-%m-%d")
                    edit_date_button.text = f"日付: {current_edit_date}"
                    page.update()

            try:
                initial_date = datetime.strptime(row_data[0], "%Y-%m-%d")
            except (ValueError, TypeError):
                initial_date = datetime.now()

            edit_date_picker = ft.DatePicker(
                on_change=on_edit_date_change,
                first_date=datetime(2000, 1, 1),
                last_date=datetime(3000, 12, 31),
                value=initial_date
            )
            page.overlay.append(edit_date_picker)

            def open_edit_date_picker(e):
                edit_date_picker.open = True
                page.update()

            edit_date_button = ft.ElevatedButton(
                text=f"日付: {current_edit_date}",
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=open_edit_date_picker
            )

            edit_category = ft.TextField(label="カテゴリ", value=row_data[3])
            edit_amount = ft.TextField(label="金額", value=str(abs(float(row_data[2]))))
            edit_content = ft.TextField(label="メモ",multiline=True, value=row_data[4])
            
            # 「保存」を押したときの処理
            async def on_save(e):
                dialog.open = False
                page.update() 
                page.overlay.remove(edit_date_picker) # DatePickerのお片付け
                page.update()
                await asyncio.sleep(0.1) # アニメーション完了待ち

                status_right.value = "保存中..."
                status_right.color = "orange"
                # オーバーレイからダイアログとDatePickerを完全に削除
                if edit_date_picker in page.overlay:
                    page.overlay.remove(edit_date_picker)
                if dialog in page.overlay:
                    page.overlay.remove(dialog)
                page.update()

                # 画面をクリアして「保存中」を表示（これで古い一覧が即座に消えます）
                page.clean()
                page.add(ft.Text("My家計簿", size=20), choice_segment)
                page.add(ft.Text("データを保存中...", color="orange", size=16))
                page.update()

                # 新しい金額を計算
                new_kingaku = float(edit_amount.value) * (-1 if row_data[1] == "Expense" else 1)
                # UUID(index 6)は維持、日付は新しいものを使用
                updated_record = [current_edit_date, current_edit_mode, new_kingaku, current_edit_category, edit_content.value, row_data[5], row_data[6]]
                
                await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], updated_record, "UPDATE")
                await refresh_view() # 画面更新

            # 「削除」を押したときの処理
            async def on_delete(e):
                dialog.open = False
                page.update() 
                page.overlay.remove(edit_date_picker) # DatePickerのお片付け
                page.update()
                await asyncio.sleep(0.1) # アニメーション完了待ち

                status_left.value = "削除中..."
                status_left.color = "orange"
                # オーバーレイからダイアログとDatePickerを完全に削除
                if edit_date_picker in page.overlay:
                    page.overlay.remove(edit_date_picker)
                if dialog in page.overlay:
                    page.overlay.remove(dialog)
                page.update()

                # 画面をクリアして「削除中」を表示
                page.clean()
                page.add(ft.Text("My家計簿", size=20), choice_segment)
                page.add(ft.Text("データを削除中...", color="orange", size=16))
                page.update()

                await asyncio.to_thread(UpdateOrDeleteSheet, row_data[6], mode="DELETE")
                await refresh_view()

            # 「複製保存」を押したときの処理
            async def on_duplicate(e):
                dialog.open = False
                page.update() 
                page.overlay.remove(edit_date_picker) # DatePickerのお片付け
                page.update()
                await asyncio.sleep(0.1) # アニメーション完了待ち

                # オーバーレイからダイアログとDatePickerを完全に削除
                if edit_date_picker in page.overlay:
                    page.overlay.remove(edit_date_picker)
                if dialog in page.overlay:
                    page.overlay.remove(dialog)
                page.update()

                # 画面をクリアして「保存中」を表示
                page.clean()
                page.add(ft.Text("My家計簿", size=20), choice_segment)
                page.add(ft.Text("データを複製保存中...", color="orange", size=16))
                page.update()

                # 新しい金額を計算
                try:
                    val = float(edit_amount.value)
                except ValueError:
                    val = 0.0
                new_kingaku = val * (-1 if current_edit_mode == "Expense" else 1)
                
                # 新しいUUIDを生成
                new_id = str(uuid.uuid4())
                timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

                # 新規レコード作成
                new_record = [current_edit_date, current_edit_mode, new_kingaku, current_edit_category, edit_content.value, timestamp, new_id]
                
                await asyncio.to_thread(Kakikomi, new_record)
                await refresh_view()

            async def close_edit_dialog(e):
                dialog.open = False
                page.overlay.remove(edit_date_picker) # DatePickerのお片付け
                page.update()
                await asyncio.sleep(0.1)
                if edit_date_picker in page.overlay:
                    page.overlay.remove(edit_date_picker)
                if dialog in page.overlay:
                    page.overlay.remove(dialog)
                page.update()


            #編集/削除画面の表示要素を規定
            status_left = ft.Text("", weight="bold", size=12)
            status_right = ft.Text("", weight="bold", size=12)

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Text("Edit/Delete"),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE, 
                        tooltip="この内容で新規作成(複製)", 
                        on_click=on_duplicate
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                content=ft.Column([
                    ft.Text("日付", size=12, color="grey500"),
                    edit_date_button,
                    ft.Text("モード", size=12, color="grey500"),
                    ft.Row([mode_choice_expense, mode_choice_income]),
                    ft.Text("カテゴリ", size=12, color="grey500"),
                    category_row,
                    edit_amount, 
                    edit_content,
                    ], 
                    tight=True),
                actions=[
                    ft.Row(
                        controls=[
                            # 左グループ：削除ボタンと、その横のラベル
                            ft.Row([
                                ft.TextButton("削除", on_click=on_delete, icon_color="red"),
                                status_left
                            ], spacing=5),
                            
                            # 右グループ：保存ラベルと、保存ボタン
                            ft.Row([
                                status_right,
                                ft.TextButton("キャンセル", on_click=close_edit_dialog),
                                ft.TextButton("保存", on_click=on_save),
                            ], spacing=10)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN # 両端に振り分ける
                    )
                ],
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()    

        #Analysisモードにおける絞り込み条件の入力ダイアログを表示する関数
        async def open_filter_dialog():

            # --- 1. 入力部品の定義 ---
            # プルダウン：モード (空欄許可)
            mode_dd = ft.Dropdown(
                label="",
                options=[ft.dropdown.Option(key="", text="指定なし"),ft.dropdown.Option("Expense"), ft.dropdown.Option("Income")],
                width=110,
                text_size=12,
                value=page.filter_query[0]
            )
            # プルダウン：カテゴリ (空欄許可)
            # --- カテゴリ複数選択の実装 ---
            all_cat_options = sorted(list(set(options_expense_list + options_income_list)))

            
            # 現在の設定値を読み込む（リストでなければ空リストにする）
            initial_cats = page.filter_query[1] if isinstance(page.filter_query[1], list) else []
            selected_cats = set(initial_cats) # 操作用の一時セット

            # 選択状況を表示するテキスト
            cat_status_text = ft.Text(
                value=",".join(sorted(list(selected_cats))) if selected_cats else "指定なし",
                size=12,
                color="white" if selected_cats else "grey",
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True
            )

            # チェックボックスの変更時
            def on_cat_checkbox_change(e):
                if e.control.value:
                    selected_cats.add(e.control.label)
                else:
                    selected_cats.discard(e.control.label)

            # カテゴリ選択ダイアログを閉じる処理
            def close_cat_selector(e):
                cat_selector_dialog.open = False
                # 親ダイアログの表示更新
                cat_status_text.value = ",".join(sorted(list(selected_cats))) if selected_cats else "指定なし"
                cat_status_text.color = "white" if selected_cats else "grey"
                dialog.open = True # 親ダイアログが閉じないように明示的に指定
                page.update()

            # カテゴリ選択ダイアログの構築
            cat_selector_dialog = ft.AlertDialog(
                title=ft.Text("カテゴリを選択"),
                content=ft.Container(
                    content=ft.Column([
                        ft.Checkbox(label=c, value=(c in selected_cats), on_change=on_cat_checkbox_change) 
                        for c in all_cat_options
                    ], scroll=ft.ScrollMode.AUTO),
                    height=300, width=250
                ),
                actions=[ft.TextButton("完了", on_click=close_cat_selector)],
                modal=True # ダイアログ外クリックで閉じないようにする
            )

            # カテゴリ選択ボタン処理
            def open_cat_selector(e):
                # ダイアログ内のチェックボックスの状態を現在の selected_cats に合わせる（再描画）
                col = cat_selector_dialog.content.content
                for checkbox in col.controls:
                    checkbox.value = (checkbox.label in selected_cats)
                # 重複追加を防ぐ
                if cat_selector_dialog not in page.overlay:
                    page.overlay.append(cat_selector_dialog)
                
                cat_selector_dialog.open = True
                page.update()

            cat_select_btn = ft.ElevatedButton("選択", on_click=open_cat_selector, height=30, style=ft.ButtonStyle(padding=5))

            # 直接入力：キーワード
            keyword_tf = ft.TextField(label="keyword", expand=True, text_size=12,value=page.filter_query[2])

            # 直接入力：日付範囲
            oldest_date_tf = ft.TextField(label="date (from)", hint_text="YYYY-MM-DD", width=110, text_size=12,value=page.filter_query[3])
            latest_date_tf = ft.TextField(label="date (to)", hint_text="YYYY-MM-DD", width=110, text_size=12,value=page.filter_query[4])

            # 直接入力：金額範囲
            max_val_str = str(page.filter_query[5]) if page.filter_query[5] is not None else ""
            min_val_str = str(page.filter_query[6]) if page.filter_query[6] is not None else ""
            
            max_amt_tf = ft.TextField(label="amount (max)", width=110, text_size=12, value=max_val_str)
            min_amt_tf = ft.TextField(label="amount (min)", width=110, text_size=12, value=min_val_str)

            # --- 2. 決定ボタンが押された時の処理 ---
            async def on_apply(e):
                # モードの判定：空文字や「指定なし」の場合は None（絞り込みなし）にする
                if not mode_dd.value or mode_dd.value == "指定なし":
                    page.filter_query[0] = None
                else:
                    page.filter_query[0] = mode_dd.value
                # カテゴリの判定（セットが空ならNone、あればリスト化して保存）
                if not selected_cats:
                     page.filter_query[1] = None
                else:
                    page.filter_query[1] = sorted(list(selected_cats))
 
                page.filter_query[2] = keyword_tf.value if keyword_tf.value else None
                page.filter_query[3] = oldest_date_tf.value if oldest_date_tf.value else None
                page.filter_query[4] = latest_date_tf.value if latest_date_tf.value else None
                page.filter_query[5] = float(max_amt_tf.value) if max_amt_tf.value.strip() else None
                page.filter_query[6] = float(min_amt_tf.value) if min_amt_tf.value.strip() else None
                
                dialog.open = False
                page.update() # 一旦閉じる描画を反映
                await asyncio.sleep(0.1) # アニメーション完了を待つ
                page.overlay.remove(dialog) # 完全に削除
                page.update()
                await refresh_view() # 画面を再描画してフィルターを適用

            async def close_filter_dialog(e):
                dialog.open = False
                page.update()
                await asyncio.sleep(0.1) # アニメーション完了を待つ
                page.overlay.remove(dialog) # 完全に削除
                page.update()

            # --- 2.5 All Clearボタンの処理 ---
            def on_clear(e):
                mode_dd.value = ""
                selected_cats.clear()
                cat_status_text.value = "指定なし"
                cat_status_text.color = "grey"
                keyword_tf.value = ""
                oldest_date_tf.value = ""
                latest_date_tf.value = ""
                max_amt_tf.value = ""
                min_amt_tf.value = ""
                page.update()
                
            # --- 3. ダイアログのレイアウト構築 ---
            dialog = ft.AlertDialog(
                modal=True, # ダイアログ外クリックで閉じないようにする
                title=ft.Row([
                    ft.Text("絞り込み条件", size=16, weight="bold"),
                    ft.TextButton("All Clear", icon=ft.Icons.CLEAR_ALL, on_click=on_clear, style=ft.ButtonStyle(color="red"))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                content=ft.Column([
                    # 1行目: モード と カテゴリ（選択系）
                    
                    ft.Row([ft.Text("mode:"), mode_dd], alignment=ft.MainAxisAlignment.START),
                    ft.Row([ft.Text("category:"), cat_select_btn, cat_status_text], alignment=ft.MainAxisAlignment.START),

                    # 2行目: キーワード（単一入力系）
                    ft.Row([
                        ft.Text("keyword:"), keyword_tf
                    ], spacing=10),

                    # 3行目: 日付範囲（期間指定）
                    ft.Row([
                        ft.Text("date  :", size=12), oldest_date_tf, 
                        ft.Text("～"), latest_date_tf
                    ], spacing=5),

                    # 4行目: 金額範囲（数値範囲指定）
                    ft.Row([
                        ft.Text("amount:", size=12), min_amt_tf, 
                        ft.Text("～"), max_amt_tf
                    ], spacing=5),
                    
                ], tight=True, spacing=20), # 各行の間隔を少し広げて見やすくしました
                actions=[
                    ft.TextButton("キャンセル", on_click=close_filter_dialog),
                    ft.Button("絞り込み", icon=ft.Icons.FILTER_ALT, on_click=on_apply),
                ],
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        loading_text = ft.Text("読み込み,絞り込み中...", color="orange")

        #記録一覧の表示のメインルート(エラーがなければここを通る)
        try:
        # --- 適用されているフィルターを明示（条件がある時だけ白く光らせる） ---
            def get_filter_style(value):
                # 値がNoneまたは空文字なら灰色、それ以外（有効な条件）なら白を返す
                return ft.TextStyle(color="white", weight="bold") if value else ft.TextStyle(color="grey600")

            q = page.filter_query
            filtering_message = ft.Text(
                spans=[
                    ft.TextSpan(f"[mode]:{q[0] or 'All'} ", style=get_filter_style(q[0])),
                    ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
                    ft.TextSpan(f"[category]:{','.join(q[1]) if q[1] else 'All'} ", style=get_filter_style(q[1])),
                    ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
                    ft.TextSpan(f"[keyword]:{q[2] or 'None'} ", style=get_filter_style(q[2])),
                    ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
                    ft.TextSpan(f"[date]:{q[3] or 'min'}~{q[4] or 'max'} ", style=get_filter_style(q[3] or q[4])),
                    ft.TextSpan(", ", style=ft.TextStyle(color="grey800")),
                    ft.TextSpan(f"[amount]:{q[6] or 'min'}~{q[5] or 'max'}", style=get_filter_style(q[6] or q[5])),
                ]
            )
            page.add(filtering_message)

            #読み込み中メッセージ
            page.add(loading_text)
            page.update() # ここで一度、画面に「読み込み中」を出す

            #データを絞り込むための関数
            #データと、絞り込み条件filter_query =[mode, category, keyword, oldest_date, latest_date, max_amount, min_amount]を与えると、絞り込み後のデータを返す
            async def filtering(data, filter_query):
                filtered_record = data
                #mode で絞る
                filtered_record = [row for row in filtered_record if filter_query[0] is None or row[1]== filter_query[0]]
                #categoryで絞る (リストに含まれているか)
                if filter_query[1] is not None and len(filter_query[1]) > 0:
                    filtered_record = [row for row in filtered_record if row[3] in filter_query[1]]
                #keywordで絞る (スペース区切りでOR検索)
                if filter_query[2]:
                    keywords = filter_query[2].replace("　", " ").split()
                    filtered_record = [row for row in filtered_record if any(k in row[4] or k in row[3] for k in keywords)]
                #oldest_dateで絞る
                filtered_record = [row for row in filtered_record if filter_query[3] is None or filter_query[3] <= row[0]]
                #latest_dateで絞る
                filtered_record = [row for row in filtered_record if filter_query[4] is None or filter_query[4] >= row[0]]
                #max_amountで絞る
                filtered_record = [row for row in filtered_record if filter_query[5] is None or (row[2] != "" and float(row[2]) <= float(filter_query[5]))]
                #min_amount で絞る
                filtered_record = [row for row in filtered_record if filter_query[6] is None or (row[2] != "" and float(row[2]) >= float(filter_query[6]))]

                return filtered_record

            # スプシからデータを取得
            raw_data = await asyncio.to_thread(Yomikomi)

            # 1行目（見出し）、2行目以降（データ部分）を分離
            header = raw_data[0]
            data_rows = raw_data[1:]

            #データ部分は、filtering関数によって絞り込んで、filtered_data_rowsにする
            filtered_data_rows = await filtering(data_rows, page.filter_query)

            # --- 1. 収支の集計ロジック ---
            # row[2]は金額。
            # 支出合計の集計
            total_expense = sum(
                float(row[2]) if row[2] != "" else 0.0 
                for row in filtered_data_rows if (row[2] != "" and float(row[2]) < 0)
            )

            # 収入合計の集計
            total_income = sum(
                float(row[2]) if row[2] != "" else 0.0 
                for row in filtered_data_rows if (row[2] != "" and float(row[2]) > 0)
            )
            balance = total_income + total_expense # 収支

            # --- 2. 表示用コンポーネントの作成 ---
            summary_card = ft.Container(
                content=ft.Row([
                    # Expense
                    ft.Column([
                        ft.Text("Expense", size=12, color="grey500"),
                        ft.Text(f"{total_expense:,.0f}", color="orange", weight="bold", size=16),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    
                    # Income
                    ft.Column([
                        ft.Text("Income", size=12, color="grey500"),
                        ft.Text(f"+{total_income:,.0f}", color="green", weight="bold", size=16),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),

                    # =
                    ft.Text("=", size=20, color="grey500"),

                    # Balance
                    ft.Column([
                        ft.Text("収支", size=12, color="grey500"),
                        ft.Text(
                            f"{balance:,.0f}", 
                            size=16, 
                            weight="bold",
                            color="green" if balance >= 0 else "orange" # プラスなら緑、マイナスならオレンジ
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=10,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                border=ft.border.all(1, "grey800"),
            )

            # 画面に追加
            page.add(summary_card)

            # 読み込みが完了したのでメッセージを消去
            if loading_text in page.controls:
                page.controls.remove(loading_text)

            # --- 【重要】ソートの実行 ---

            if not filtered_data_rows:
                # 1. 該当データがない場合
                page.add(ft.Text("該当するデータが見つかりませんでした", size=16, color="red"))
                status_label = ft.Text("", color="green", weight="bold")
                page.update()
                
            else:
                #該当データがあるときだけsortを実行する

                # --- 画面幅に応じたレイアウト調整 ---
                # page.width が取得できない場合を考慮してデフォルト値を設定
                current_width = page.width if page.width else 400
                
                # 閾値を設定 (例: 600px以上ならPCライクな広々表示)
                if current_width >= 600:
                    table_column_spacing = 10
                    # メモ欄の幅を動的に計算 (画面幅 - 他の列の概算幅)
                    memo_col_width = max(200, current_width - 450) 
                else:
                    table_column_spacing = 2
                    memo_col_width = 100

                # 表示上の列番号(sort_column_index)と、データ内のインデックスの対応マップ
                # 0(日付) -> 0, 1(カテゴリ) -> 3, 2(金額) -> 2, 3(内容) -> 4
                sort_map = {0: 0, 1: 3, 2: 2, 3: 4}
                target_idx = sort_map.get(sort_column_index, 0)

                # lambdaを使って、指定されたインデックス（sort_column_index）の値で並び替え
                filtered_data_rows.sort(
                    key=lambda x: (float(x[2]) if x[2] else 0) if sort_column_index == 2 else x[target_idx],
                    reverse=not sort_ascending
                )
                # ※金額（index 2）の時は数値として比較するために float() 変換を入れるのがコツです。
                data_table = ft.DataTable(
                    #高さ,幅
                    data_row_min_height=20,    # 行の最小高さ
                data_row_max_height=float("inf"),    # 行の最大高さ
                    heading_row_height=20,     # 見出し（ヘッダー）行の高さ
                    column_spacing=table_column_spacing,          # 列同士の横の隙間を動的に設定

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
                                # widthを指定して強制的に折り返しさせる
                                ft.DataCell(ft.Text(row[4], width=memo_col_width, no_wrap=False, color=ft.Colors.ORANGE_ACCENT if row[1] == "Expense" else ft.Colors.GREEN_400)),
                                #↓編集用アイコンの設定
                                ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.GREY, on_click=lambda e, r=row: page.run_task(open_edit_dialog, r)))                          
                            ]
                        ) for row in filtered_data_rows
                    ],
                )

                page.add(ft.Column([data_table], scroll=ft.ScrollMode.ALWAYS, expand=True))
                page.update()

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
            page.update()

    #画面を再読み込み（再構築）する関数を作る
    async def refresh_view():
        nonlocal current_task
        
        # --- 追加：もし動いているタスクがあれば中断（キャンセル）する ---
        if current_task is not None and not current_task.done():
            current_task.cancel()
            try:
                await current_task # キャンセルが完了するのを待つ
            except asyncio.CancelledError:
                pass # キャンセル成功
        
        page.clean()
        
        # モードによらず必ず表示するものを追加
        page.add(ft.Text("My家計簿", size=20),choice_segment)

        # 4. 【重要】現在のモードのページ作成を「タスク」として1回だけ起動
        # ここで await せずに create_task することで、スムーズに切り替わります
        if current_mode == "Analysis":
            current_task = asyncio.create_task(make_analysispage())
        else:
            current_task = asyncio.create_task(make_recordingpage())
            
        page.update()

    async def sort_column(e):
        nonlocal sort_column_index, sort_ascending
        # クリックされた列のインデックスを取得
        sort_column_index = e.column_index
        # 昇順・降順を反転させる
        sort_ascending = not sort_ascending
        # 再描画
        await refresh_view()

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

#---画面最上部　共通部品(モード切り替えボタン)---
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

#----Expenseモード、Incomeモードの画面の規定----

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
    first_date=datetime(1600, 1, 1), # 選択可能な最小日
    last_date=datetime(3000, 12, 31)  # 選択可能な最大日
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
        height=70, # スクロールバーとチップが重ならないように高さを確保
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
    
    # 読み込み完了後、ページの配置を元に戻す
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START
    await refresh_view()

ft.app(target=main)
