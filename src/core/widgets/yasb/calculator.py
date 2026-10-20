import ast
import operator
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout

from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.calculator import CalculatorConfig
from core.widgets.base import BaseWidget


class CalculatorWidget(BaseWidget):
    """Bar widget that opens a popup calculator on click."""

    validation_schema = CalculatorConfig

    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }
    _UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(self, config: CalculatorConfig):
        super().__init__(class_name=f"calculator-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._expression = ""
        self._result = "0"
        self._just_evaluated = False
        self._menu = None
        self._result_label = None
        self._expr_label = None

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("toggle_label", self._toggle_label)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    # ------------------------------------------------------------------
    # Label handling
    # ------------------------------------------------------------------
    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------
    def _toggle_menu(self):
        if self._menu is not None and self._menu.isVisible():
            self._menu.hide()
            self._menu = None
            return
        self._show_menu()

    def _show_menu(self):
        self._menu = PopupWidget(
            self,
            blur=self.config.menu.blur,
            round_corners=self.config.menu.round_corners,
            round_corners_type=self.config.menu.round_corners_type,
            border_color=self.config.menu.border_color,
        )
        self._menu.setProperty("class", "calculator-popup")
        self._menu.setFixedWidth(self.config.menu.width)

        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Expression display (small, top)
        self._expr_label = QLabel(self._expression)
        self._expr_label.setProperty("class", "expression")
        self._expr_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._expr_label.setFixedHeight(20)
        layout.addWidget(self._expr_label)

        # Result display (large)
        self._result_label = QLabel(self._result)
        self._result_label.setProperty("class", "result")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._result_label.setFixedHeight(48)
        layout.addWidget(self._result_label)

        # Button grid
        grid = QGridLayout()
        grid.setSpacing(4)
        buttons = [
            ("AC", "clear", 0, 0),
            ("⌫", "utility", 1, 0),
            ("%", "utility", 2, 0),
            ("÷", "operator", 3, 0),
            ("7", "number", 0, 1),
            ("8", "number", 1, 1),
            ("9", "number", 2, 1),
            ("×", "operator", 3, 1),
            ("4", "number", 0, 2),
            ("5", "number", 1, 2),
            ("6", "number", 2, 2),
            ("−", "operator", 3, 2),
            ("1", "number", 0, 3),
            ("2", "number", 1, 3),
            ("3", "number", 2, 3),
            ("+", "operator", 3, 3),
            ("±", "utility", 0, 4),
            ("0", "number", 1, 4),
            (".", "number", 2, 4),
            ("=", "equals", 3, 4),
        ]
        for text, css_class, col, row in buttons:
            btn = QPushButton(text)
            btn.setProperty("class", f"button {css_class}")
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _checked=False, t=text: self._on_button(t))
            grid.addWidget(btn, row, col)
        layout.addLayout(grid)

        # Keyboard support
        self._menu.keyPressEvent = self._popup_key_press

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        self._menu.show()

    def _popup_key_press(self, event):
        """Route keyboard input from the popup to the calculator."""
        key = event.key()
        text = event.text()

        key_map = {
            Qt.Key.Key_0: "0",
            Qt.Key.Key_1: "1",
            Qt.Key.Key_2: "2",
            Qt.Key.Key_3: "3",
            Qt.Key.Key_4: "4",
            Qt.Key.Key_5: "5",
            Qt.Key.Key_6: "6",
            Qt.Key.Key_7: "7",
            Qt.Key.Key_8: "8",
            Qt.Key.Key_9: "9",
            Qt.Key.Key_Plus: "+",
            Qt.Key.Key_Minus: "−",
            Qt.Key.Key_Asterisk: "×",
            Qt.Key.Key_Slash: "÷",
            Qt.Key.Key_Percent: "%",
            Qt.Key.Key_Period: ".",
            Qt.Key.Key_Comma: ".",
            Qt.Key.Key_Enter: "=",
            Qt.Key.Key_Return: "=",
            Qt.Key.Key_Equal: "=",
            Qt.Key.Key_Backspace: "⌫",
            Qt.Key.Key_Escape: "AC",
            Qt.Key.Key_ParenLeft: "(",
            Qt.Key.Key_ParenRight: ")",
        }

        if key in key_map:
            mapped = key_map[key]
            if mapped in ("(", ")"):
                if mapped == "(" and self._just_evaluated:
                    self._expression = ""
                    self._just_evaluated = False
                self._expression += mapped
                self._refresh_display()
            else:
                self._on_button(mapped)
            event.accept()
            return

        if text and text.isdigit():
            self._on_button(text)
            event.accept()
            return

        event.ignore()

    # ------------------------------------------------------------------
    # Calculator logic
    # ------------------------------------------------------------------
    def _on_button(self, text):
        if text == "AC":
            self._expression = ""
            self._result = "0"
            self._just_evaluated = False
        elif text == "⌫":
            if self._just_evaluated:
                self._just_evaluated = False
            self._expression = self._expression[:-1]
            if not self._expression:
                self._result = "0"
        elif text == "±":
            self._toggle_sign()
        elif text == "%":
            self._apply_percent()
        elif text == "=":
            self._evaluate()
        elif text in ("+", "−", "×", "÷"):
            self._append_operator(text)
        elif text == ".":
            self._append_decimal()
        else:
            self._append_digit(text)
        self._refresh_display()

    def _append_digit(self, digit):
        if self._just_evaluated:
            self._expression = ""
            self._just_evaluated = False
        if self._expression == "0":
            self._expression = ""
        self._expression += digit
        self._result = self._expression

    def _append_decimal(self):
        if self._just_evaluated:
            self._expression = ""
            self._just_evaluated = False
        current_number = re.split(r"[+−×÷()]", self._expression)[-1]
        if "." not in current_number:
            if not self._expression or self._expression[-1] in "+−×÷(":
                self._expression += "0"
            self._expression += "."
            self._result = self._expression

    def _append_operator(self, op):
        if self._just_evaluated:
            self._expression = self._result
            self._just_evaluated = False
        if not self._expression:
            if op == "−":
                self._expression = "−"
                self._result = self._expression
            return
        last = self._expression[-1]
        if last in "+−×÷(":
            if op == "−" and last != "−":
                self._expression += op
            else:
                self._expression = self._expression[:-1] + op
        else:
            self._expression += op
        self._result = self._expression

    def _toggle_sign(self):
        if self._just_evaluated:
            self._expression = self._result
            self._just_evaluated = False
        if not self._expression:
            self._expression = "−"
        else:
            match = re.search(r"(\d+\.?\d*)$", self._expression)
            if match:
                number_start = match.start()
                prefix = self._expression[:number_start]
                if prefix.endswith("−") and (len(prefix) == 1 or prefix[-2] in "+−×÷("):
                    self._expression = prefix[:-1] + match.group(1)
                else:
                    self._expression = prefix + "−" + match.group(1)
            else:
                self._expression += "−"
        self._result = self._expression

    def _apply_percent(self):
        if self._just_evaluated:
            self._expression = self._result
            self._just_evaluated = False
        match = re.search(r"(\d+\.?\d*)$", self._expression)
        if match:
            value = float(match.group(1)) / 100
            formatted = self._format_number(value)
            self._expression = self._expression[: match.start()] + formatted
            self._result = self._expression

    def _evaluate(self):
        if not self._expression:
            return
        expr = re.sub(r"[+−×÷(]+$", "", self._expression)
        if not expr:
            return
        open_count = expr.count("(")
        close_count = expr.count(")")
        if open_count > close_count:
            expr += ")" * (open_count - close_count)
        try:
            result = self._safe_eval(expr)
        except ZeroDivisionError, ValueError, SyntaxError, TypeError:
            self._result = "Error"
            return
        self._result = self._format_number(result)
        self._expression = self._result
        self._just_evaluated = True

    def _safe_eval(self, expr):
        """Safely evaluate an arithmetic expression using the AST.

        Supports +, -, *, / and parentheses. Rejects anything else.
        """
        normalized = expr.replace("−", "-").replace("×", "*").replace("÷", "/")
        tree = ast.parse(normalized, mode="eval")

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type not in self._BIN_OPS:
                    raise ValueError(f"Unsupported operator: {op_type.__name__}")
                left = _eval(node.left)
                right = _eval(node.right)
                return self._BIN_OPS[op_type](left, right)
            if isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type not in self._UNARY_OPS:
                    raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
                return self._UNARY_OPS[op_type](_eval(node.operand))
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")

        result = _eval(tree)
        if isinstance(result, complex):
            raise ValueError("Result is not a real number")
        if result != result or result in (float("inf"), float("-inf")):
            raise ValueError("Result is not a finite number")
        return float(result)

    @staticmethod
    def _format_number(value):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.10g}"

    def _refresh_display(self):
        if self._result_label is not None:
            self._result_label.setText(self._result)
        if self._expr_label is not None:
            self._expr_label.setText(self._expression if self._expression != self._result else "")
