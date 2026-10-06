"""
logic/filter_sort.py

【このコードの目的・機能・挙動】
明細データの絞り込み（フィルタリング）および列ごとの並び替え（ソート）を
担当するロジックモジュールです。

旧コードにあった複雑なリスト内包表記による多段フィルタを関数としてカプセル化し、
全角スペースを半角スペースに正規化してキーワードでOR検索する機能や、
日付範囲・金額範囲の判定仕様を維持しています。
"""

from typing import List, Any, Optional


def filter_records(data_rows: List[List[Any]], filter_query: List[Any]) -> List[List[Any]]:
    """
    明細データリストに対して、filter_queryの各条件を適用して絞り込む。

    filter_query の構造:
      [0]: mode (str or None) -> "Expense" または "Income"
      [1]: categories (list of str or None) -> 該当カテゴリのいずれかに一致
      [2]: keyword (str or None) -> スペース区切りOR検索（内容またはカテゴリに部分一致）
      [3]: oldest_date (str or None) -> "YYYY-MM-DD" 以上
      [4]: latest_date (str or None) -> "YYYY-MM-DD" 以下
      [5]: max_amount (float or None) -> 金額の上限
      [6]: min_amount (float or None) -> 金額の下限
    """
    filtered = data_rows

    # 1. モードで絞り込み
    mode = filter_query[0]
    if mode:
        filtered = [row for row in filtered if len(row) > 1 and row[1] == mode]

    # 2. カテゴリで絞り込み（複数選択対応）
    categories = filter_query[1]
    if categories and len(categories) > 0:
        filtered = [row for row in filtered if len(row) > 3 and row[3] in categories]

    # 3. キーワードで絞り込み（全角・半角スペース区切りによるOR検索）
    keyword_str = filter_query[2]
    if keyword_str:
        keywords = keyword_str.replace(" ", " ").split()
        if keywords:
            filtered = [
                row for row in filtered
                if any((len(row) > 4 and k in str(row[4])) or (len(row) > 3 and k in str(row[3])) for k in keywords)
            ]

    # 4. 開始日（date from）で絞り込み
    oldest_date = filter_query[3]
    if oldest_date:
        filtered = [row for row in filtered if len(row) > 0 and row[0] >= oldest_date]

    # 5. 終了日（date to）で絞り込み
    latest_date = filter_query[4]
    if latest_date:
        filtered = [row for row in filtered if len(row) > 0 and row[0] <= latest_date]

    # 6. 金額（上限）で絞り込み
    max_amt = filter_query[5]
    if max_amt is not None:
        def _check_max(r):
            try:
                return r[2] != "" and float(r[2]) <= float(max_amt)
            except (ValueError, IndexError):
                return False
        filtered = [row for row in filtered if _check_max(row)]

    # 7. 金額（下限）で絞り込み
    min_amt = filter_query[6]
    if min_amt is not None:
        def _check_min(r):
            try:
                return r[2] != "" and float(r[2]) >= float(min_amt)
            except (ValueError, IndexError):
                return False
        filtered = [row for row in filtered if _check_min(row)]

    return filtered


def sort_records(data_rows: List[List[Any]], sort_column_index: int, ascending: bool) -> List[List[Any]]:
    """
    指定された列インデックスに基づいて明細リストをソートする。
    sort_column_index の対応:
      0: 日付 (row[0])
      1: カテゴリ (row[3])
      2: 金額 (row[2] の数値比較)
      3: 内容・メモ (row[4])
    """
    sort_map = {0: 0, 1: 3, 2: 2, 3: 4}
    target_idx = sort_map.get(sort_column_index, 0)

    if sort_column_index == 2:
        # 金額列は数値として比較
        def _amount_key(row):
            try:
                return float(row[2]) if len(row) > 2 and row[2] != "" else 0.0
            except ValueError:
                return 0.0
        return sorted(data_rows, key=_amount_key, reverse=not ascending)
    else:
        # 文字列として比較
        return sorted(
            data_rows,
            key=lambda row: str(row[target_idx]) if len(row) > target_idx else "",
            reverse=not ascending
        )