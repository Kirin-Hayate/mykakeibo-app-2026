"""
services/sheets_service.py

【このコードの目的・機能・挙動】
Google スプレッドシート（Recordingsシート、Settingsシート）との通信を一手に担う
データアクセス層（DAO）モジュールです。

【インメモリキャッシュ高速化＆整合性アーキテクチャ】
1. 完全インメモリキャッシュ（0msレスポンス）:
   初回起動時に取得した明細データ（_raw_data_cache）およびカテゴリ設定（_categories_cache）を
   プロセスのメモリ上に保持します。2回目以降のアクセスやタブ切り替え時、Google APIへの
   HTTPS通信を一切行わずにメモリから即座にデータを返すため、超高速な画面描画を実現します。
2. 差分インプレース更新（キャッシュ破棄待ちの排除）:
   追加（add_record）・更新・削除（update_or_delete_record）が発生した際、スプレッドシートへの
   永続化APIを呼び出すと同時に、メモリ上のキャッシュ配列に対して直接「追記」「該当行置換」「pop削除」を
   実行します。キャッシュを None にして次回アクセスで再取得する従来の方式と違い、変更直後でも
   再フェッチの通信遅延（1〜3秒）を一切挟まず、最新のUIを即時レンダリング可能です。
3. スレッドセーフ（排他制御）:
   threading.Lock を導入し、非同期タスクや複数クライアントからの並行読み書きによる
   キャッシュ配列の破損やデータ競合を防止します。
4. シングルトン運用:
   本モジュール末尾で単一インスタンス（sheets_service）を生成して公開します。
   ローカルPC環境・自宅Xubuntu常時稼働サーバー環境のどちらでも、コードの書き換えなしで
   透過的に機能します。
"""

import json
import threading
from datetime import datetime
from typing import List, Tuple, Optional, Any
import gspread
from google.oauth2.service_account import Credentials

from config.settings import (
    SPREADSHEET_NAME,
    GCP_SERVICE_ACCOUNT_JSON,
    JSON_KEY_PATH,
    GOOGLE_API_SCOPES,
    JST
)


class SheetsService:
    def __init__(self):
        # gspreadクライアントとシートオブジェクトの参照保持用変数
        self._client: Optional[gspread.Client] = None
        self._recordings_sheet: Optional[gspread.Worksheet] = None
        self._settings_sheet: Optional[gspread.Worksheet] = None

        # スレッドセーフ用ロック
        self._lock = threading.Lock()

        # 読み込みデータのメモリキャッシュ
        self._raw_data_cache: Optional[List[List[Any]]] = None
        # カテゴリ一覧のメモリキャッシュ (expense_list, income_list)
        self._categories_cache: Optional[Tuple[List[str], List[str]]] = None

    def _get_credentials(self) -> Credentials:
        """
        環境変数またはローカルファイルからGoogleサービスアカウントの認証情報を生成する
        """
        if GCP_SERVICE_ACCOUNT_JSON:
            creds_dict = json.loads(GCP_SERVICE_ACCOUNT_JSON)
            return Credentials.from_service_account_info(
                creds_dict,
                scopes=GOOGLE_API_SCOPES
            )

        if JSON_KEY_PATH.exists():
            return Credentials.from_service_account_file(
                str(JSON_KEY_PATH),
                scopes=GOOGLE_API_SCOPES
            )

        raise FileNotFoundError(
            f"Google APIの認証情報が見つかりません: {JSON_KEY_PATH}"
        )

    def _get_client(self) -> gspread.Client:
        """
        認証済みgspreadクライアントを返す（すでに生成済みなら使い回す）
        """
        if self._client is None:
            creds = self._get_credentials()
            self._client = gspread.authorize(creds)
        return self._client

    def _get_recordings_sheet(self) -> gspread.Worksheet:
        """Recordings（明細記録）ワークシートの参照を取得・保持する"""
        if self._recordings_sheet is None:
            client = self._get_client()
            self._recordings_sheet = client.open(SPREADSHEET_NAME).worksheet("Recordings")
        return self._recordings_sheet

    def _get_settings_sheet(self) -> gspread.Worksheet:
        """Settings（カテゴリ設定）ワークシートの参照を取得・保持する"""
        if self._settings_sheet is None:
            client = self._get_client()
            self._settings_sheet = client.open(SPREADSHEET_NAME).worksheet("Settings")
        return self._settings_sheet

    # --------------------------------------------------------------------------
    # キャッシュ管理
    # --------------------------------------------------------------------------
    def invalidate_cache(self) -> None:
        """メモリ上に保存している明細データおよびカテゴリキャッシュを完全にクリアする"""
        with self._lock:
            self._raw_data_cache = None
            self._categories_cache = None
            print("[SheetsService] メモリキャッシュをクリアしました")

    # --------------------------------------------------------------------------
    # 明細（Recordings）操作
    # --------------------------------------------------------------------------
    def get_all_records(self, force_reload: bool = False) -> List[List[Any]]:
        """
        全レコードを二次元リスト形式で取得する。
        すでにキャッシュがあり、force_reload=False なら通信を行わずメモリから即座に返す。
        """
        with self._lock:
            if self._raw_data_cache is not None and not force_reload:
                # 外部での破壊的変更を防ぐため浅いコピーで返却
                return [row.copy() for row in self._raw_data_cache]

        # キャッシュ未作成または強制再取得の場合はAPI通信
        sheet = self._get_recordings_sheet()
        data = sheet.get_all_values()

        with self._lock:
            self._raw_data_cache = data
            return [row.copy() for row in self._raw_data_cache]

    def add_record(self, record: List[Any]) -> None:
        """
        新しいレコードを行末に追加する。
        Googleスプレッドシートへの追記と同時に、メモリキャッシュへ即座にインプレース追記する。
        """
        # 1. スプレッドシートへ書き込み
        sheet = self._get_recordings_sheet()
        sheet.append_row(record)
        print(f"[SheetsService] スプレッドシート追記成功: {record}")

        # 2. キャッシュが存在する場合は直接リスト末尾に追加（再取得通信をスキップ）
        with self._lock:
            if self._raw_data_cache is not None:
                self._raw_data_cache.append([str(x) for x in record])
                print("[SheetsService] メモリキャッシュへ差分追加完了")

    def update_or_delete_record(
        self,
        target_uuid: str,
        new_record: Optional[List[Any]] = None,
        mode: str = "UPDATE"
    ) -> None:
        """
        指定したUUIDを持つ行を探し、更新または削除を実行する。
        スプレッドシートへの反映と同時に、メモリキャッシュの該当行を直接書き換える。
        """
        sheet = self._get_recordings_sheet()

        # 7列目(G列: UUID)をすべて取得して該当行を特定
        uuid_list = sheet.col_values(7)

        try:
            # 1行目は見出しのため +1
            row_index = uuid_list.index(target_uuid) + 1

            if mode == "UPDATE" and new_record is not None:
                # A列〜G列を新しいデータで上書き
                sheet.update(range_name=f"A{row_index}:G{row_index}", values=[new_record])
                print(f"[SheetsService] 行更新成功 (行番号: {row_index})")
            elif mode == "DELETE":
                # 指定行を削除
                sheet.delete_rows(row_index)
                print(f"[SheetsService] 行削除成功 (行番号: {row_index})")

            # メモリキャッシュの該当要素を即時インプレース更新
            with self._lock:
                if self._raw_data_cache is not None:
                    target_idx = None
                    for i, row in enumerate(self._raw_data_cache):
                        # G列 (index 6) のUUIDを照合
                        if len(row) > 6 and str(row[6]) == target_uuid:
                            target_idx = i
                            break

                    if target_idx is not None:
                        if mode == "UPDATE" and new_record is not None:
                            self._raw_data_cache[target_idx] = [str(x) for x in new_record]
                            print(f"[SheetsService] メモリキャッシュの該当行を更新: index {target_idx}")
                        elif mode == "DELETE":
                            self._raw_data_cache.pop(target_idx)
                            print(f"[SheetsService] メモリキャッシュから該当行を削除: index {target_idx}")

        except ValueError:
            print(f"[SheetsService] 指定されたUUIDが見つかりませんでした: {target_uuid}")

    # --------------------------------------------------------------------------
    # カテゴリ（Settings）操作
    # --------------------------------------------------------------------------
    def load_categories(self, force_reload: bool = False) -> Tuple[List[str], List[str]]:
        """
        Settingsシートから支出カテゴリ一覧と収入カテゴリ一覧を取得する。
        すでにキャッシュがあり、force_reload=False なら通信を行わずメモリから即座に返す。
        """
        with self._lock:
            if self._categories_cache is not None and not force_reload:
                exp_list, inc_list = self._categories_cache
                return exp_list.copy(), inc_list.copy()

        try:
            sheet = self._get_settings_sheet()
            all_values = sheet.get_all_values()

            if not all_values or len(all_values) < 2:
                return [], []

            # 1列目: Expense, 2列目: Income
            expense_list = [row[0] for row in all_values[1:] if len(row) > 0 and row[0]]
            income_list = [row[1] for row in all_values[1:] if len(row) > 1 and row[1]]

            with self._lock:
                self._categories_cache = (expense_list, income_list)

            return expense_list.copy(), income_list.copy()
        except gspread.exceptions.WorksheetNotFound:
            print("[SheetsService] Settingsシートが見つかりません。デフォルト値を使用します。")
            return [], []
        except Exception as e:
            print(f"[SheetsService] カテゴリ読み込みエラー: {e}")
            return [], []

    def save_categories(self, expense_list: List[str], income_list: List[str]) -> None:
        """
        支出カテゴリと収入カテゴリのリストをSettingsシートに保存し、メモリキャッシュも更新する
        """
        try:
            sheet = self._get_settings_sheet()

            rows = [["Expense", "Income"]]  # 見出しヘッダー
            max_len = max(len(expense_list), len(income_list))

            for i in range(max_len):
                exp = expense_list[i] if i < len(expense_list) else ""
                inc = income_list[i] if i < len(income_list) else ""
                rows.append([exp, inc])

            sheet.clear()
            sheet.update(range_name="A1", values=rows)
            print("[SheetsService] カテゴリ設定を保存しました")

            # メモリキャッシュも最新化
            with self._lock:
                self._categories_cache = (expense_list.copy(), income_list.copy())

        except Exception as e:
            print(f"[SheetsService] カテゴリ保存エラー: {e}")


# アプリケーション全体で使い回すシングルトンインスタンス
sheets_service = SheetsService()