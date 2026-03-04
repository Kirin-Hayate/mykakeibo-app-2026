import vertexai
from vertexai.generative_models import GenerativeModel, Image
import os
import glob
import time
import shutil
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import asyncio
from datetime import timedelta
import uuid
import math
import vertexai
from vertexai.generative_models import GenerativeModel, Image
import os
import glob
import time
import shutil
import uuid
import csv
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定 ---
PROJECT_ID = "kakeibofrom202602032126"
LOCATION = "us-central1" 
IMAGE_FOLDER = r"C:\Users\hayat\OneDrive\デスクトップ\家計簿アプリの作成\old_records\2024"
# 移行済みのフォルダ名
PROCESSED_DIR_NAME = "移行済記録"

# Vertex AIの初期化（APIキーは不要になります）
vertexai.init(project=PROJECT_ID, location=LOCATION)
# 300ドル枠を使うならこのモデルが最もコスパが良いです
model = GenerativeModel("gemini-2.5-flash")

# カテゴリ定義
EXPENSE_CATEGORIES = ["Wagner", "SYC", "交通", "食費", "交際", "勉強,研究", "電話", "娯楽", "美容", "衣服", "旅行", "医療", "その他","税"]
INCOME_CATEGORIES = ["FreeStep", "お小遣い", "その他", "SYC","Wagner", "NEXA","TAS","Spacerise"]

PROMPT = f"""
提供された画像を読み取り、家計簿データとして抽出してください。
以下のフォーマットに従い、コンマ(,)で区切りで1行だけ出力してください。

出力フォーマット:
日付,モード,金額,カテゴリ,内容

制約:
1. 日付: YYYY-MM-DD形式。
2. モード: "Expense" または "Income"。
3. 金額: 半角数字（' や , は含めない）。
   - Expenseの場合: 負の値 (例: -1000)
   - Incomeの場合: 正の値 (例: 1000)
4. カテゴリ: リストから選択。
   - Expense: {", ".join(EXPENSE_CATEGORIES)}
   - Income: {", ".join(INCOME_CATEGORIES)}
5. 内容: メモ等。

※重要: 「FreeStep誤差脱漏」の場合は、Incomeモード、FreeStepカテゴリ、負の金額で出力。
"""


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
    sheet = client.open(SHEET_NAME).worksheet("old_records")

    # 3. 操作フェーズ（「命令」を送る）
    #append_row: 「一番下の空いている行に、このリストの内容を書き込め」という命令を送ります。
    sheet.append_row(record)
    #この瞬間、PythonからGoogleのサーバーへデータが送信され、スプレッドシートがリアルタイムで更新されます。

    print(f"書き込み成功：内容{record}")

def main():
    image_files = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        image_files.extend(glob.glob(os.path.join(IMAGE_FOLDER, ext)))
    
    if not image_files:
        print(f"画像が見つかりません。")
        return

    processed_dir = os.path.join(IMAGE_FOLDER, PROCESSED_DIR_NAME)
    os.makedirs(processed_dir, exist_ok=True)

    for img_path in image_files:
        filename = os.path.basename(img_path)
        try:
            # Vertex AI形式での画像読み込み
            image = Image.load_from_file(img_path)
            
            # AI解析
            response = model.generate_content([PROMPT, image])
            text = response.text.strip().replace("'", "")
            
            # CSV/スプシ用整形
            record_list = [item.strip() for item in text.split(',')]
            record_list.append(datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
            record_list.append(str(uuid.uuid4()))

            # スプレッドシートへ書き込み
            Kakikomi(record_list)
            
            # 移動
            shutil.move(img_path, os.path.join(processed_dir, filename))
            print(f"完了: {filename}")
            
            # Vertex AIは無料枠でもAI Studioより制限が緩いですが、1秒程度待つと安定します
            time.sleep(1)

        except Exception as e:
            print(f"エラー ({filename}): {e}")
            # クォータ（制限）エラーの場合は長めに待機
            if "429" in str(e):
                time.sleep(60)

if __name__ == "__main__":
    start = time.time()
    main()
    print(f"処理時間:{start - time.time():.2f}s")
