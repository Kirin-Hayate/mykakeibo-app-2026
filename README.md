My家計簿アプリ (Flet + Google Sheets)

慶應ワグネルや理工学部の学生生活を支えるために開発している、自作の家計簿アプリケーションです。
フロントエンドに Flet (Python)、バックエンドに Google Sheets API を採用しています。

主な機能

Expense/Income 記録: カテゴリ選択と金額入力による直感的な記録

Analysis モード: データの絞り込み、ソート機能

可視化レポート: 円グラフによる支出・収入の内訳表示 (Flet PieChart)

クラウド連携: Googleスプレッドシートへのリアルタイム書き込み・読み込み

セットアップ

このプロジェクトを実行するには、以下のライブラリが必要です。

pip install -r requirements.txt


注意事項

セキュリティのため、Google Cloud の秘密鍵（JSON）はリポジトリに含まれていません。

実行には各自の秘密鍵ファイルが必要です。