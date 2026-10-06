"""
logic/calculator.py

【このコードの目的・機能・挙動】
入力画面にある簡易電卓機能（例: 1170 * (40/60)）の計算式を安全に解釈・計算する
独立モジュールです。

【旧コードからの大幅な改善点・動作原理】
旧コードでは eval(calc_input.value, {"__builtins__": None}, {}) を使用していましたが、
Web公開時における悪意ある構文の注入や予期せぬ挙動のリスクを完全には排除できませんでした。
本モジュールでは、Python標準の `ast`（抽象構文木）を利用して、
「数値」および「四則演算（+ - * /）」のみを再帰的に走査・計算します。
これにより、不正な関数実行やシステムコマンドの実行リスクをゼロにし、
計算エラー時も安全に "Error" を返します。
"""

import ast
import operator
from typing import Union

# 許可する二項演算子と対応する演算関数のマッピング
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,  # 単項マイナス（例: -5）
    ast.UAdd: operator.pos,  # 単項プラス（例: +5）
}


def _eval_node(node: ast.AST) -> Union[int, float]:
    """
    ASTの各ノードを再帰的に評価し、許可された演算のみを実行する内部関数
    """
    # 数値リテラルの場合（Python 3.8+ では ast.Constant）
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("数値以外の定数は許可されていません")

    # 二項演算の場合（例: A + B, A * B）
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _ALLOWED_OPERATORS:
            left_val = _eval_node(node.left)
            right_val = _eval_node(node.right)
            
            # ゼロ除算の防止
            if op_type is ast.Div and right_val == 0:
                raise ZeroDivisionError("0で除算することはできません")
                
            return _ALLOWED_OPERATORS[op_type](left_val, right_val)
        raise ValueError(f"許可されていない演算子です: {op_type}")

    # 単項演算の場合（例: -A, +A）
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _ALLOWED_OPERATORS:
            val = _eval_node(node.operand)
            return _ALLOWED_OPERATORS[op_type](val)
        raise ValueError(f"許可されていない単項演算子です: {op_type}")

    raise ValueError("無効な式構造です")


def safe_calculate(expression: str) -> str:
    """
    数式文字列を受け取り、安全に計算した結果の文字列を返す。
    整数として割り切れる場合は小数点以下を表示しない（例: 5.0 -> 5）。
    不正な文字が含まれる場合や計算不可能な場合は "Error" を返す。
    """
    if not expression or not expression.strip():
        return ""

    try:
        # 文字列をASTノードにパース（式モード）
        parsed_ast = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(parsed_ast.body)

        # 整数値であれば .0 を削って整数表現にする
        if isinstance(result, (int, float)):
            if result == int(result):
                return str(int(result))
            # 小数点以下がある場合は丸め誤差を考慮して有効数字を整える
            return str(round(result, 4))
        
        return str(result)
    except Exception:
        return "Error"