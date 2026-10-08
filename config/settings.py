"""
config/settings.py

【このコードの目的・機能・挙動】
アプリケーション全体で共有する環境設定、ファイルパス、タイムゾーン、
およびGoogle API認証スコープを一元管理するモジュールです。

旧コードでは「秘密鍵-kakeibofrom202602032126.json」というファイル名が
コード内にハードコードされていましたが、本モジュールによって .env 経由で
外部注入できるように抽象化しました。
また、Ubuntuサーバー環境がUTCであっても、家計簿の日時処理を一貫して
日本標準時（JST: Asia/Tokyo）として扱えるようタイムゾーン定数を提供します。
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# プロジェクトのルートディレクトリ（my_kakeibo/）を特定
BASE_DIR = Path(__file__).resolve().parent.parent

# .env ファイルの絶対パスを指定して読み込む
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# ==============================================================================
# タイムゾーン設定
# ==============================================================================
# サーバーOS（Linux）のローカル時刻設定に左右されず、常に日本時間で統一
JST = ZoneInfo("Asia/Tokyo")

# ==============================================================================
# Google スプレッドシート関連設定
# ==============================================================================
# 操作対象のスプレッドシート名
SPREADSHEET_NAME = os.getenv("MYKAKEIBO_SPREADSHEET_NAME", "")

# サービスアカウント秘密鍵のJSON文字列（Web公開・環境変数指定用）
GCP_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SERVICE_ACCOUNT_JSON", None)

# 秘密鍵ファイルのパス（指定がなければデフォルトのファイル名を探す）
_key_file_env = os.getenv("GCP_SERVICE_ACCOUNT_FILE")
if _key_file_env:
    JSON_KEY_PATH = Path(_key_file_env)
else:
    # 既存のファイル名との後方互換性を維持
    JSON_KEY_PATH = BASE_DIR / "秘密鍵-kakeibofrom202602032126.json"

# Google APIの認可スコープ
GOOGLE_API_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==============================================================================
# サーバー稼働・ネットワーク設定
# ==============================================================================
# 常時稼働サーバーとしてのリッスンホストおよびポート番号
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8501"))

# アイコンファイルのパス
ICON_PATH = BASE_DIR / "icon_MyKAKEIBO_ver202610081158.ico"