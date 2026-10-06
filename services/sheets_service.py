"""
services/sheets_service.py

【このコードの目的・機能・挙動】
Google スプレッドシート（Recordingsシート、Settingsシート）との通信を専任で
担当するデータアクセス層（DAO）モジュールです。

【旧コードからの大幅な改善点・動作原理】
1. コネクションのキャッシュ（シングルトン化）:
   旧コードでは関数の呼び出しごとに毎回認証（get_creds）とシートオープンを行っており、
   数秒の通信遅延（オーバーヘッド）が発生していました。
   本モジュールではクライアント接続とWorksheetオブジェクトを内部で保持（キャッシュ）し、
   通信確立の回数を最小限に抑えてレスポンス速度を大幅に向上させます。
2. データのメモリキャッシュと自動無効化:
   スプレッドシートから読み込んだ全レコードをメモリ上に保持し、画面遷移時の
   不要な再取得を防止します。データの追加・更新・削除が発生した際には
   自動的にキャッシュを破棄（または最新化）し、画面とのデータ不整合を完全に防ぎます。
3. google-auth への刷新:
   非推奨となった oauth2client から google.oauth2.service_account へ完全移行しました。
"""

import json
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
        
        # 読み込みデータのメモリキャッシュ
        self._raw_data_cache: Optional[List[List[Any]]] = None

    def _get_credentials(self) -> Credentials:
        """
        環境変数またはローカルファイルからGoogleサービスアカウントの認証情報を生成する
        """
        # 1. 環境変数からの読み込み（JSON文字列）
        if GCP_SERVICE_ACCOUNT_JSON:
            creds_dict = json.loads(GCP_SERVICE_ACCOUNT_JSON)
            return Credentials.from_service_account_info(
                creds_dict,
                scopes=GOOGLE_API_SCOPES
            )

        # 2. ローカルファイルからの読み込み
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
        """メモリ上に保存している明細データキャッシュをクリアする"""
        self._raw_data_cache = None

    # --------------------------------------------------------------------------
    # 明細（Recordings）操作
    # --------------------------------------------------------------------------
    def get_all_records(self, force_reload: bool = False) -> List[List[Any]]:
        """
        全レコードを二次元リスト形式で取得する。
        すでにキャッシュがあり、force_reload=False なら通信を行わずキャッシュを返す。
        """
        if self._raw_data_cache is not None and not force_reload:
            return self._raw_data_cache

        sheet = self._get_recordings_sheet()
        data = sheet.get_all_values()
        self._raw_data_cache = data
        return data

    def add_record(self, record: List[Any]) -> None:
        """
        新しいレコードを行末に追加し、キャッシュを破棄する
        """
        sheet = self._get_recordings_sheet()
        sheet.append_row(record)
        # データが追加されたため、次回取得時に再読み込みされるようキャッシュを無効化
        self.invalidate_cache()
        print(f"[SheetsService] 書き込み成功: {record}")

    def update_or_delete_record(self, target_uuid: str, new_record: Optional[List[Any]] = None, mode: str = "UPDATE") -> None:
        """
        指定したUUIDを持つ行を探し、更新または削除を実行する
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
            
            # 変更を反映するためキャッシュを無効化
            self.invalidate_cache()

        except ValueError:
            print(f"[SheetsService] 指定されたUUIDが見つかりませんでした: {target_uuid}")

    # --------------------------------------------------------------------------
    # カテゴリ（Settings）操作
    # --------------------------------------------------------------------------
    def load_categories(self) -> Tuple[List[str], List[str]]:
        """
        Settingsシートから支出カテゴリ一覧と収入カテゴリ一覧を取得する
        """
        try:
            sheet = self._get_settings_sheet()
            all_values = sheet.get_all_values()

            if not all_values or len(all_values) < 2:
                return [], []

            # 1列目: Expense, 2列目: Income
            expense_list = [row[0] for row in all_values[1:] if len(row) > 0 and row[0]]
            income_list = [row[1] for row in all_values[1:] if len(row) > 1 and row[1]]

            return expense_list, income_list
        except gspread.exceptions.WorksheetNotFound:
            print("[SheetsService] Settingsシートが見つかりません。デフォルト値を使用します。")
            return [], []
        except Exception as e:
            print(f"[SheetsService] カテゴリ読み込みエラー: {e}")
            return [], []

    def save_categories(self, expense_list: List[str], income_list: List[str]) -> None:
        """
        支出カテゴリと収入カテゴリのリストをSettingsシートに保存する
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
        except Exception as e:
            print(f"[SheetsService] カテゴリ保存エラー: {e}")


# アプリケーション全体で使い回すシングルトンインスタンス
sheets_service = SheetsService()