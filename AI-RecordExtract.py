import os
import glob
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from PIL import Image

# 1. .envからAPIキーを読み込む
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("【エラー】.envファイルからGEMINI_API_KEYが見つかりません。")
    exit()

# 2. クライアントの初期化
client = genai.Client(api_key=api_key)

# 設定
IMAGE_FOLDER = r"C:\Users\hayat\OneDrive\デスクトップ\家計簿アプリの作成\old_records\2024-04"
MODEL_NAME = "gemini-2.5-flash-lite"

# カテゴリ定義
EXPENSE_CATEGORIES = [
    "Wagner", "SYC", "交通", "食費", "交際", "勉強,研究", 
    "電話", "娯楽", "美容", "衣服", "旅行", "医療", "その他"
]
INCOME_CATEGORIES = [
    "FreeStep", "お小遣い", "その他", "チケット収入"
]

# プロンプト作成
PROMPT = f"""
提供された画像を読み取り、家計簿データとして抽出してください。
以下のフォーマットに従い、タブ区切りで1行だけ出力してください。Markdownのコードブロックは不要です。

出力フォーマット:
日付\tモード\t金額\tカテゴリ\t内容

制約:
1. 日付: YYYY-MM-DD形式。
2. モード: "Expense" または "Income"。
3. 金額: 半角数字。
   - Expenseの場合: 負の値 (例: -1000)
   - Incomeの場合: 正の値 (例: 1000)
4. カテゴリ: 以下のリストから選択。
   - Expense: {", ".join(EXPENSE_CATEGORIES)}
   - Income: {", ".join(INCOME_CATEGORIES)}
5. 内容: 画像内のメモや品目。

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

    print(f"対象画像: {len(image_files)}枚")
    print("日付\tモード\t金額\tカテゴリ\t内容\t記録した日時")

    for img_path in image_files:
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
            
            print(f"{text}\t{recorded_at}")
            
            # APIレート制限対策
            time.sleep(10)
            
        except Exception as e:
            print(f"エラー ({os.path.basename(img_path)}): {e}")

if __name__ == "__main__":
    main()
