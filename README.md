# MyKAKEIBO

Google スプレッドシートを永続ストレージとして活用し、Python および Flet（Flutter エンジン）を用いて構築したクロスプラットフォーム対応の個人用家計簿アプリケーションです。

ローカル PC（Windows）での高速・軽量なデスクトップ UI 運用と、常時稼働サーバー（Linux / Xubuntu 等）上でのマルチデバイス対応 Web サーバー運用の双方にシームレスに対応します。

---

## 主な機能と特徴

### 1. 直感的な収支入力（Record View）
- **高速登録**: 金額、カテゴリ、メモ、日付を入力してスプレッドシートへ即時反映。
- **モード切り替え**: SegmentedButton による「支出（Expense）」「収入（Income）」のワンタップ切り替え。
- **チップ選択式カテゴリ**: よく使う項目を素早く入力可能。

### 2. 詳細な一覧と編集・複製（Edit Dialog）
- **明細の柔軟な操作**: 過去データの「修正保存」「新規複製保存」「削除」に対応。
- **タイムゾーン厳密補正**: カレンダー選択（DatePicker）時の UTC シリアライズによる日付ズレを JST（日本標準時: Asia/Tokyo）へ自動補正。

### 3. 高度な推移・収支分析（Timeline Dialog）
- **単一 LineChart 統合アーキテクチャ**:
  - **支出**: 0円ラインから下方向へ広がる半透明オレンジの面描画。
  - **収入**: 0円ラインから上方向へ広がる半透明グリーンの面描画。
  - **収支推移（Balance）**: 最前面を走るシアン色の折れ線グラフ。
- **Max/Min 厳密保証 ＆ 動的ツールチップ**:
  - 全取引データ点の軌跡を保持して正確なピーク値を描画しつつ、要約カード（ツールチップ）の高速表示を両立。

### 4. ハイブリッド実行・最適化アーキテクチャ
- **環境自動切り替え**: `.env` の `APP_ENV` 設定により、Windows デスクトップアプリ形式と常駐 Web サーバー形式を自動分岐。
- **インメモリキャッシュ**: `SheetsService` によるデータ保持とインプレース差分更新により、API 通信のオーバーヘッドを削減。
- **プラットフォーム安定性**: Windows 特有の非同期パイプ切断例外（`WinError 10054`）を安全に吸収し、ダイアログ展開時のプロセス残留（ゾンビ化）を防止。

---

## ディレクトリ構成

```text
mykakeibo_app/
├── .env                                # 環境変数設定（認証情報、ポート、環境指定）
├── main.py                             # エントリーポイント（ルーティング・ライフサイクル管理）
├── requirements.txt                    # 依存ライブラリ一覧
├── icon_MyKAKEIBO_ver202610081158.ico  # アプリアイコン
├── config/
│   └── settings.py                     # パス、タイムゾーン(JST)、APIスコープ設定
├── logic/
│   └── aggregator.py                   # タイムライン集計、ダウンサンプリング、座標計算ロジック
├── services/
│   └── sheets_service.py               # Google Sheets API データアクセス層（DAO・キャッシュ機構）
└── ui/
    ├── state.py                        # アプリケーション状態管理（AppState）
    ├── components/
    │   └── loading.py                  # ローディング表示コンポーネント
    └── views/
        ├── record_view.py              # 支出・収入の入力画面
        ├── analysis_view.py            # 明細一覧・集計画面
        ├── edit_dialog.py              # 明細編集・複製・削除ダイアログ
        ├── timeline_dialog.py          # 収支推移グラフダイアログ
        ├── category_dialog.py          # カテゴリ設定管理ダイアログ
        └── report_dialog.py            # レポート表示ダイアログ
```

---

## セットアップ手順

### 1. 必要要件
- Python 3.11 以上（推奨: 3.12 または 3.13）
- Google Cloud Platform（GCP）サービスアカウントおよび JSON 秘密鍵
- Google スプレッドシート（`Recordings` シート、`Settings` シートを含む）

### 2. ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 3. 環境変数（`.env`）の設定
プロジェクト直下に `.env` ファイルを作成し、必要な設定を記述します。

```ini
# 実行環境設定 ('local' または 'server')
APP_ENV=local

# スプレッドシート設定
MYKAKEIBO_SPREADSHEET_NAME=家計簿スプレッドシート名
GCP_SERVICE_ACCOUNT_FILE=秘密鍵-xxxx.json

# サーバー起動設定（APP_ENV=server の場合）
SERVER_HOST=0.0.0.0
SERVER_PORT=8501
```

---

## 起動方法

### ローカル PC モード（デスクトップ GUI）
`.env` の `APP_ENV=local` を指定して起動します。
```bash
python main.py
```
※ Windows 環境では、コンソールを出さずに起動できる `pythonw.exe` 経由のショートカット作成を推奨します。

### サーバーモード（常駐 Web サーバー）
`.env` の `APP_ENV=server` を指定して起動します。同一 LAN 内のスマートフォンや PC のブラウザから `http://<サーバーのIP>:8501` でアクセス可能です。
```bash
python main.py
```

---

## ライセンス / 注意事項
- 本ソフトウェアは個人利用を目的として設計されています。
- GCP のサービスアカウント秘密鍵ファイル（`.json`）や `.env` は機密情報であるため、Git 追跡から除外（`.gitignore` に追加）してください。