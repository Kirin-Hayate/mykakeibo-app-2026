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

raw_data = Yomikomi()
header = raw_data[0]
raw_record = raw_data[1::]


mode, category, keyword, oldest_date, latest_date , max_amount, min_amount = None,None,None,None,None,None,None
filter_query =[mode, category, keyword, oldest_date, latest_date, max_amount, min_amount]

filter_query[4] = "2026-02-04"

filtered_record = raw_record

#mode で絞る
filtered_record = [row for row in filtered_record if filter_query[0] is None or row[1]== filter_query[0]]
#categoryで絞る
filtered_record = [row for row in filtered_record if filter_query[1] is None or row[3]== filter_query[1]]
#keywordで絞る
filtered_record = [row for row in filtered_record if filter_query[2] is None or filter_query[2] in row[4]]
#oldest_dateで絞る
filtered_record = [row for row in filtered_record if filter_query[3] is None or filter_query[3] <= row[0]]
#latest_dateで絞る
filtered_record = [row for row in filtered_record if filter_query[4] is None or filter_query[4] >= row[0]]
#max_amountで絞る
filtered_record = [row for row in filtered_record if filter_query[5] is None or filter_query[5] >= row[2]]
#min_amount で絞る
filtered_record = [row for row in filtered_record if filter_query[6] is None or filter_query[6] <= row[2]]

print(filtered_record)