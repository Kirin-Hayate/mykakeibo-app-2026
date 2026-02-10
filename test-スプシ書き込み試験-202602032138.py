import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
sheet.append_row(["2026-02-03", "100", "Test", "疎通確認"])
#この瞬間、PythonからGoogleのサーバーへデータが送信され、スプレッドシートがリアルタイムで更新されます。

print("スプレッドシートへの書き込みに成功しました！")