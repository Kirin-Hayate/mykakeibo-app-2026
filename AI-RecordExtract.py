import os
from dotenv import load_dotenv
from google import genai

# 1. .envからAPIキーを読み込む
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("【エラー】.envファイルからGEMINI_API_KEYが見つかりません。")
    exit()

# 2. クライアントの初期化
client = genai.Client(api_key=api_key)

print(api_key)

try:
    # 3. メッセージ送信（モデル名の前に 'models/' を追加）
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite", 
        contents="こんにちは！接続テストです。このメッセージが見えたら成功と答えて。"
    )
    
    print("\n--- Geminiからの返答 ---")
    print(response.text)
    print("------------------------")
    print("テスト成功です！おめでとうございます。")

except Exception as e:
    print(f"\n【エラー発生】APIの呼び出しに失敗しました:\n{e}")