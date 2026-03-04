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

# 1. .envからAPIキーを読み込む
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY_2")

if not api_key:
    print("【エラー】.envファイルからGEMINI_API_KEY_2が見つかりません。")
    exit()

# 2. クライアントの初期化
client = genai.Client(api_key=api_key)

# 設定
IMAGE_FOLDER = r"C:\Users\hayat\OneDrive\デスクトップ\家計簿アプリの作成\old_records\2024"
MODEL_NAME = "gemini-2.5-flash-lite"

# カテゴリ定義
EXPENSE_CATEGORIES = [
    "Wagner", "SYC", "交通", "食費", "交際", "勉強,研究", 
    "電話", "娯楽", "美容", "衣服", "旅行", "医療", "その他","税"
]
INCOME_CATEGORIES = [
    "FreeStep", "お小遣い", "その他", "SYC","Wagner", "NEXA","TAS","Spacerise"
]

# プロンプト作成
PROMPT = f"""
提供された画像を読み取り、家計簿データとして抽出してください。
以下のフォーマットに従い、コンマ(,)で区切りで1行だけ出力してください。Markdownのコードブロックは不要です。

出力フォーマット:
日付,モード,金額,カテゴリ,内容

制約:
1. 日付: YYYY-MM-DD形式。
2. モード: "Expense" または "Income"。
3. 金額: 半角数字。
   - Expenseの場合: 負の値 (例: -1000)
   - Incomeの場合: 正の値 (例: 1000)
4. カテゴリ: 以下のリストから選択。
   - Expense: {", ".join(EXPENSE_CATEGORIES)}
   - Income: {", ".join(INCOME_CATEGORIES)}
5. 内容: 画像内のメモや品目。内容がない場合は空欄とする。
ただし、カテゴリが「Freestep誤差脱漏」の場合は、その金額をIncomeモードで記録してください。
たとえば、FreeStep誤差脱漏カテゴリの1000円の支出は、IncomeモードでFreeStepカテゴリの負の収入-1000として記録すること。

画像から読み取れない場合は、文脈から推測するか、不明としてください。
"""

def main():
    # 画像ファイルの検索
    image_files = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.heic"]:
        image_files.extend(glob.glob(os.path.join(IMAGE_FOLDER, ext)))
    
    if not image_files:
        print(f"フォルダ '{IMAGE_FOLDER}' に画像が見つかりませんでした。")
        return

    # 移行先フォルダの作成
    processed_dir = os.path.join(IMAGE_FOLDER, "移行済記録")
    os.makedirs(processed_dir, exist_ok=True)

    print(f"対象画像: {len(image_files)}枚")
    print("日付\tモード\t金額\tカテゴリ\t内容\t記録した日時")

    for img_path in image_files:
        # リトライ処理を追加
        max_retries = 5
        for attempt in range(max_retries):
            try:
                image = Image.open(img_path)
                
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[PROMPT, image]
                )
                
                # 結果のクリーニング
                text = response.text.strip()
                # コードブロック記号があれば除去
                text = text.replace("```tsv", "").replace("```", "").strip()
                
                # 記録日時
                recorded_at = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                
                # 文字列をカンマで分割してリストに変換
                record_list = text.split(',')
                # 各要素の余分な空白を除去
                record_list = [item.strip() for item in record_list]
                # 記録日時を追加
                record_list.append(recorded_at)
                # UUIDを追加 (アプリ側の仕様に合わせて一意なIDを付与)
                record_list.append(str(uuid.uuid4()))

                print(f"書き込みデータ: {record_list}")
                Kakikomi(record_list)
                
                # APIレート制限対策（成功時）
                time.sleep(10)

                # 画像を移動
                shutil.move(img_path, os.path.join(processed_dir, os.path.basename(img_path)))
                print(f"移動しました: {os.path.basename(img_path)}")

                break # 成功したらループを抜ける
                
            except Exception as e:
                error_str = str(e)
                # レート制限エラー(429)の場合
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait_time = 70 # エラーメッセージ(約56秒)より長めに待機
                    print(f"【制限検知】API利用制限にかかりました。{wait_time}秒待機して再試行します... ({attempt + 1}/{max_retries})")
                    print(f"対象ファイル: {os.path.basename(img_path)}")
                    time.sleep(wait_time)
                else:
                    print(f"エラー ({os.path.basename(img_path)}): {e}")
                    break # その他のエラーはスキップ

if __name__ == "__main__":
    start=time.time()
    main()
    print(f"処理時間合計: {time.time()-start}s")
