import ast
import logging
import math
import operator
import re

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_CALCULATOR

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_MAX_EXPONENT = 10000

_NAMES: dict[str, float | object] = {
    "pi": math.pi,
    "e": math.e,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _safe_eval(expr: str) -> int | float:
    """Evaluate a math expression safely via AST."""
    return _eval(ast.parse(expr, mode="eval").body)


def _eval(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > _MAX_EXPONENT:
            logging.error("Calculator: exponent too large (max %d)", _MAX_EXPONENT)
            return 0
        return _OPS[type(node.op)](left, right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _NAMES
        and callable(_NAMES[node.func.id])
    ):
        return _NAMES[node.func.id](*(_eval(a) for a in node.args))
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    raise ValueError("Unsupported expression")


# Must contain at least one digit and one operator or math function
_MATH_PATTERN = re.compile(r"^[\d\s\+\-\*/\.\(\)\%\^,a-z]+$", re.IGNORECASE)


class CalculatorProvider(BaseProvider):
    """Evaluate math expressions inline."""

    name = "calculator"
    display_name = "Calculator"
    input_placeholder = "Type a math expression..."
    icon = ICON_CALCULATOR

    def match(self, text: str) -> bool:
        text = text.strip()
        # Match configured prefix or auto-detect math expressions
        if self.prefix and text.startswith(self.prefix):
            return True
        if not _MATH_PATTERN.match(text):
            return False
        # Must contain at least one digit and one operator
        has_digit = any(c.isdigit() for c in text)
        has_operator = any(c in text for c in "+-*/%^") or any(
            fn in text.lower() for fn in ("sqrt", "sin", "cos", "log")
        )
        return has_digit and has_operator

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text) if text.startswith("=") else text.strip()
        if not query:
            return [
                ProviderResult(
                    title="Type a math expression",
                    description="e.g. 2+2, sqrt(144), 15% of 200",
                    icon_char=ICON_CALCULATOR,
                    provider=self.name,
                )
            ]
        try:
            # Replace ^ with ** for Python exponentiation
            expr = query.replace("^", "**")
            # Handle "X% of Y" pattern
            percent_match = re.match(r"([\d.]+)\s*%\s*of\s+([\d.]+)", expr, re.IGNORECASE)
            if percent_match:
                pct, val = float(percent_match.group(1)), float(percent_match.group(2))
                result_val = (pct / 100) * val
            else:
                result_val = _safe_eval(expr)

            # Format result
            if isinstance(result_val, float):
                if result_val == int(result_val) and abs(result_val) < 1e15:
                    display = str(int(result_val))
                else:
                    display = f"{result_val:g}"
            else:
                display = str(result_val)

            return [
                ProviderResult(
                    title=display,
                    description=f"{query} - press Enter to copy",
                    icon_char=ICON_CALCULATOR,
                    provider=self.name,
                    action_data={"value": display},
                )
            ]
        except Exception:
            return [
                ProviderResult(
                    title=query,
                    description="Continue typing a valid expression",
                    icon_char=ICON_CALCULATOR,
                    provider=self.name,
                )
            ]

    def execute(self, result: ProviderResult) -> bool:
        value = result.action_data.get("value", "")
        if value:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(value)
        return True
