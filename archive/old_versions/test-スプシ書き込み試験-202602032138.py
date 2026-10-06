import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 認証設定
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('秘密鍵-kakeibofrom202602032126.json', scope) # ここにファイル名
client = gspread.authorize(creds)

# 2. シートを開く (ご自身で作ったスプレッドシート名に書き換えてください)
# ※シートの「共有」で、サービスアカウントのメールアドレスを追加するのを忘れずに！
SHEET_NAME = "家計簿テストver202602032139" 
sheet = client.open(SHEET_NAME).sheet1

# 3. テスト書き込み
sheet.append_row(["2026-02-03", "100", "Test", "疎通確認"])

print("スプレッドシートへの書き込みに成功しました！")