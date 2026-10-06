@echo off
chcp 65001 > nul

%~dp0
cd /d %~dp0
:: ↑ 「このバッチファイルがある場所」に自動で移動する魔法の呪文です

call .venv\Scripts\activate
python main.py
pause