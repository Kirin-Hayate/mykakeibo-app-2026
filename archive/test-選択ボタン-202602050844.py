import flet as ft

async def main(page: ft.Page):
    current_mode = "Expense"

    async def handle_change(e):
        nonlocal current_mode
        if e.control.selected:
            # 集合(set)から最初の値を取り出す
            val = list(e.control.selected)[0]
            current_mode = str(val)
            
            # 2. 更新時も「リスト」で上書きする
            choice_segment.selected = [current_mode]
            page.update()

    # 2. 部品の定義
    choice_segment = ft.SegmentedButton(
        selected=["Expense"],  
        allow_multiple_selection=False,
        on_change=handle_change,
        segments=[
            ft.Segment(value="Expense", label=ft.Text("Expense")),
            ft.Segment(value="Income", label=ft.Text("Income")),
            ft.Segment(value="Analysis", label=ft.Text("Anlysis"))
        ],
    )
    page.add(choice_segment)

# 起動
ft.app(target=main)