Set ws = CreateObject("Wscript.Shell")
' 第2引数の 0 が「ウィンドウを非表示にする」という魔法の数字です
ws.run "cmd /c MyKAKEIBO.bat", 0
