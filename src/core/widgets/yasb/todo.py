import datetime
import json
import logging
import os
import re
import urllib.parse
from functools import partial

from PyQt6.QtCore import QMimeData, QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QCursor, QDrag, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import apply_qmenu_style
from core.validation.widgets.yasb.todo import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class TodoWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    _instances = []

    def __init__(
        self,
        label: str,
        label_alt: str,
        data_path: str,
        container_padding: dict,
        animation: dict,
        menu: dict,
        icons: dict,
        callbacks: dict,
        categories: dict,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="todo-widget")
        TodoWidget._instances.append(self)

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._data_path = data_path
        self._animation = animation
        self._padding = container_padding
        self._menu_config = menu
        self._icons = icons
        self._categories = categories
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._tasks = []
        self._menu = None
        self._selected_category = "default"
        self._category_buttons = []
        self._expanded_task_id = None
        self._show_completed = False
        self._category_filter = None

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._load_tasks()
        self._update_label()

    @classmethod
    def update_all(cls):
        for instance in cls._instances:
            instance._load_tasks()
            instance._update_label()

    def _get_tasks_file_path(self):
        if self._data_path and self._data_path.strip():
            return os.path.expanduser(self._data_path)
        return os.path.join(HOME_CONFIGURATION_DIR, "todo.json")

    def _load_tasks(self):
        try:
            tasks_file = self._get_tasks_file_path()
            if os.path.exists(tasks_file):
                with open(tasks_file, "r", encoding="utf-8") as f:
                    self._tasks = json.load(f)
                self._tasks.sort(key=lambda t: t["order"], reverse=True)
            else:
                self._tasks = []
        except Exception as e:
            logging.error(f"Error loading tasks: {e}")
            self._tasks = []

    def _save_tasks(self):
        try:
            tasks_file = self._get_tasks_file_path()
            with open(tasks_file, "w", encoding="utf-8") as f:
                json.dump(self._tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving tasks: {e}")

    def _add_new_task(self, dialog):
        title = self._title_input.text().strip()
        description = self._desc_input.toPlainText().strip() if self._desc_input else ""
        if not title:
            return
        task_data = {
            "id": int(datetime.datetime.now().timestamp()),
            "title": title,
            "description": description,
            "category": self._selected_category,
            "created_at": datetime.datetime.now().isoformat(),
            "completed": False,
            "order": len(self._tasks),
        }
        self._tasks.insert(0, task_data)
        self._save_tasks()
        TodoWidget.update_all()
        dialog.accept()
        self._show_completed = False
        self._show_menu()

    def _edit_task(self, dialog, task):
        title = self._title_input.text().strip()
        description = self._desc_input.toPlainText().strip() if self._desc_input else ""
        if not title:
            return
        for t in self._tasks:
            if t["id"] == task["id"]:
                t["title"] = title
                t["description"] = description
                t["category"] = self._selected_category
                break
        self._save_tasks()
        TodoWidget.update_all()
        dialog.accept()
        self._show_completed = False
        self._expanded_task_id = task["id"]
        self._show_menu()

    def _show_task_dialog(self, dialog_title, save_button_text, on_save, task=None):
        self._menu.hide()
        self._selected_category = task.get("category", "default") if task else "default"
        dialog = QDialog(self._menu)
        dialog.setWindowTitle(dialog_title)
        dialog.setMinimumSize(500, 200)
        dialog.setProperty("class", "app-dialog")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setSpacing(0)
        dialog_layout.setContentsMargins(0, 0, 0, 0)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(20, 0, 20, 0)

        self._title_input = QLineEdit()
        self.widget_context_menu(self._title_input)
        self._title_input.setPlaceholderText("Task title... (max 100 characters, required)")
        self._title_input.setProperty("class", "title-field")
        if task:
            self._title_input.setText(task["title"])
        self._title_input.textChanged.connect(lambda: self._limit_text_length("title", 100))
        content_layout.addWidget(self._title_input)

        self._desc_input = QTextEdit()
        self._desc_input.insertFromMimeData = lambda source: self._desc_input.insertPlainText(source.text())
        self.widget_context_menu(self._desc_input)
        self._desc_input.setPlaceholderText("Task description... (max 500 characters)")
        if task:
            self._desc_input.setText(task.get("description", ""))
        self._desc_input.textChanged.connect(lambda: self._limit_text_length("description", 500))
        self._desc_input.setProperty("class", "desc-field")
        content_layout.addWidget(self._desc_input)

        category_container = QFrame()
        category_layout = QHBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_container.setProperty("class", "category-container")
        self._category_buttons = []
        for category_name, category_config in self._categories.items():
            category_btn = QPushButton(category_config["label"])
            category_btn.setProperty("class", f"category-button {category_name}")
            category_btn.setCheckable(True)
            category_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            category_btn.clicked.connect(partial(self._select_category, category_name))
            category_layout.addWidget(category_btn)
            self._category_buttons.append((category_name, category_btn))

        for cat_name, btn in self._category_buttons:
            btn.setChecked(cat_name == self._selected_category)

        content_layout.addWidget(category_container)
        dialog_layout.addWidget(content_container)

        button_container = QFrame()
        button_container.setProperty("class", "buttons-container")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        cancel_button = QPushButton("Cancel")
        cancel_button.setProperty("class", "button cancel")
        cancel_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        save_button = QPushButton(save_button_text)
        save_button.setProperty("class", "button add")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(lambda: on_save(dialog, task) if task else on_save(dialog))
        button_layout.addWidget(save_button)

        dialog_layout.addWidget(button_container)

        self._title_input.setFocus()
        dialog.exec()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])

        self._show_alt_label = not self._show_alt_label

        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)

        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

        self._update_label()

    def _get_filtered_tasks(self, completed=None, category=None):
        """Return tasks filtered by completed status and/or category."""
        tasks = self._tasks
        if completed is not None:
            tasks = [t for t in tasks if t.get("completed", False) == completed]
        if category:
            tasks = [t for t in tasks if t.get("category") == category]
        return tasks

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        active_tasks = self._get_filtered_tasks(completed=False)
        completed_tasks = self._get_filtered_tasks(completed=True)
        total_tasks = len(self._tasks)
        active_count = len(active_tasks)
        completed_count = len(completed_tasks)

        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            current_widget = active_widgets[widget_index]

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                current_widget.setText(icon)
            else:
                formatted_text = (
                    part.replace("{count}", str(active_count))
                    .replace("{total}", str(total_tasks))
                    .replace("{completed}", str(completed_count))
                )
                current_widget.setText(formatted_text)
            widget_index += 1

        # Tooltip: show number of tasks per category, skip 0s
        category_counts = {}
        for cat_key, cat_conf in self._categories.items():
            count = len([t for t in self._tasks if t.get("category") == cat_key and not t.get("completed", False)])
            if count > 0:
                category_counts[cat_conf["label"]] = count
        if category_counts:
            tooltip_lines = [f"{label}: {count}" for label, count in category_counts.items()]
            tooltip_text = "\n".join(tooltip_lines)
        else:
            tooltip_text = "No tasks."
        set_tooltip(self._widget_container, tooltip_text)

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_completed = False
        self._expanded_task_id = None
        self._show_menu()

    def _show_menu(self):
        self._menu = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )
        self._menu.setProperty("class", "todo-menu")

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header_container = QFrame()
        header_container.setProperty("class", "header")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        add_task_button = QPushButton(self._icons["add"])
        add_task_button.setProperty("class", "add-task-button")
        add_task_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_task_button.clicked.connect(self._show_add_task_dialog)

        header_layout.addWidget(add_task_button, alignment=Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch()

        self._in_progress_btn = QPushButton("In Progress")
        self._in_progress_btn.setCheckable(True)
        self._in_progress_btn.setChecked(not self._show_completed)
        self._in_progress_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._in_progress_btn.setProperty("class", "tab-buttons in-progress")
        self._in_progress_btn.clicked.connect(lambda: self._set_show_completed(False))

        self._completed_btn = QPushButton("Completed")
        self._completed_btn.setCheckable(True)
        self._completed_btn.setChecked(self._show_completed)
        self._completed_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._completed_btn.setProperty("class", "tab-buttons completed")
        self._completed_btn.clicked.connect(lambda: self._set_show_completed(True))

        self._order_btn = QPushButton(self._icons["sort"])
        self._order_btn.setProperty("class", "tab-buttons sort")
        self._order_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._order_btn.clicked.connect(self._show_sort_menu)

        header_layout.addWidget(self._in_progress_btn)
        header_layout.addWidget(self._completed_btn)
        header_layout.addWidget(self._order_btn)

        main_layout.addWidget(header_container)

        scroll_area = QScrollArea()
        scroll_area.setViewportMargins(0, 0, -4, 0)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_widget = QWidget()
        scroll_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll_widget.setProperty("class", "scroll-widget")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        tasks = self._get_filtered_tasks(completed=False, category=self._category_filter)
        if self._expanded_task_id is None and tasks:
            self._expanded_task_id = tasks[0]["id"]

        self._refresh_task_list(scroll_layout, tasks)

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._menu.show()

    def _show_sort_menu(self):
        menu = QMenu(self._order_btn.window())
        menu.setProperty("class", "context-menu")
        menu.setStyleSheet("""
            QMenu::indicator:checked { background: transparent;color:transparent }
        """)
        apply_qmenu_style(menu)
        sort_by_date = QAction("Sort by date (Newest)", self)
        sort_by_date_old = QAction("Sort by date (Oldest)", self)
        sort_reset = QAction("Reset sorting", self)

        menu.addAction(sort_by_date)
        menu.addAction(sort_by_date_old)
        menu.addAction(sort_reset)

        sort_by_date.triggered.connect(lambda: self._sort_and_filter_tasks(sort_mode="date"))
        sort_by_date_old.triggered.connect(lambda: self._sort_and_filter_tasks(sort_mode="date", reverse=True))
        sort_reset.triggered.connect(lambda: self._sort_and_filter_tasks(sort_mode="default"))
        menu.addSeparator()

        show_all_action = QAction("Show all categories", self)
        show_all_action.triggered.connect(self._clear_category_filter)
        show_all_action.setCheckable(True)
        show_all_action.setChecked(self._category_filter is None)
        menu.addAction(show_all_action)
        for cat_key, cat_config in self._categories.items():
            action = QAction(f"Show only {cat_config['label']}", self)
            action.setCheckable(True)
            action.setChecked(self._category_filter == cat_key)
            action.triggered.connect(lambda checked, c=cat_key: self._sort_and_filter_tasks(category_key=c))
            menu.addAction(action)

        button_pos = self._order_btn.mapToGlobal(self._order_btn.rect().bottomLeft())
        menu_width = menu.sizeHint().width()
        pos = button_pos - QPoint(menu_width - self._order_btn.sizeHint().width(), -6)
        menu.exec(pos)

    def _sort_and_filter_tasks(self, sort_mode=None, category_key=None, reverse=False):
        if category_key is not None:
            self._category_filter = category_key

        if sort_mode == "date" and not reverse:
            self._tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        elif sort_mode == "date" and reverse:
            self._tasks.sort(key=lambda t: t.get("created_at", ""), reverse=False)
        elif sort_mode == "default":
            self._tasks.sort(key=lambda t: t.get("order", ""), reverse=True)
            self._category_filter = None

        # Reset expanded task ID when sorting or filtering
        self._expanded_task_id = None

        self._refresh_menu_task_list()

    def _clear_category_filter(self):
        self._category_filter = None
        TodoWidget.update_all()
        self._refresh_menu_task_list()

    def _set_show_completed(self, show_completed):
        self._show_completed = show_completed
        self._in_progress_btn.setChecked(not show_completed)
        self._completed_btn.setChecked(show_completed)
        if show_completed:
            self._expanded_task_id = None  # Collapse all when switching to completed
        self._refresh_menu_task_list()

    def _refresh_task_list(self, layout, tasks=None):
        """Refresh the task list."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if tasks is None:
            if not self._show_completed:
                tasks = self._get_filtered_tasks(completed=False, category=self._category_filter)
            else:
                tasks = self._get_filtered_tasks(completed=True, category=self._category_filter)

        if tasks:
            for task in tasks:
                self._add_task_to_menu(task, layout, completed=self._show_completed)
        else:
            category_label = ""
            if self._category_filter:
                cat_key = self._category_filter
                cat_conf = self._categories.get(cat_key, {})
                category_label = f" in <b>{cat_conf.get('label', cat_key)}</b>"

            if not self._show_completed:
                msg = (
                    f"No tasks{category_label} yet.<br>Click <b>New Task</b> to create your first task!"
                    if not category_label
                    else f"No tasks{category_label}.<br>Click <b>New Task</b> to create your first task!"
                )
            else:
                msg = f"No completed tasks{category_label} yet."

            no_tasks_icon = QLabel(self._icons["no_tasks"])
            no_tasks_icon.setProperty("class", "no-tasks-icon")
            no_tasks_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            no_tasks_label = QLabel(msg)
            no_tasks_label.setProperty("class", "no-tasks")
            no_tasks_label.setWordWrap(True)
            no_tasks_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            no_tasks_label.setTextFormat(Qt.TextFormat.RichText)
            no_tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_tasks_icon)
            layout.addWidget(no_tasks_label)

    def _refresh_menu_task_list(self):
        """Refresh the task list in the menu if it exists."""
        if hasattr(self, "_menu") and self._menu:
            scroll_areas = self._menu.findChildren(QScrollArea)
            if scroll_areas:
                scroll_area = scroll_areas[0]
                scroll_widget = scroll_area.widget()
                if scroll_widget:
                    # Use filtered tasks for refresh
                    if not self._show_completed:
                        tasks = self._get_filtered_tasks(completed=False, category=self._category_filter)
                    else:
                        tasks = self._get_filtered_tasks(completed=True, category=self._category_filter)
                    self._refresh_task_list(scroll_widget.layout(), tasks)

    def _expand_task(self, task_id):
        self._expanded_task_id = task_id
        self._refresh_menu_task_list()

    def _show_add_task_dialog(self):
        self._show_task_dialog(dialog_title="Add New Task", save_button_text="Add Task", on_save=self._add_new_task)

    def _show_edit_task_dialog(self, task):
        self._show_task_dialog(
            dialog_title="Edit Task", save_button_text="Save Changes", on_save=self._edit_task, task=task
        )

    def widget_context_menu(self, widget):
        def show_custom_menu(point):
            standard_menu = widget.createStandardContextMenu()
            menu = QMenu(widget.window())
            menu.setProperty("class", "context-menu")
            menu.addActions(standard_menu.actions())
            standard_menu.deleteLater()
            apply_qmenu_style(menu)
            for action in menu.actions():
                action.setIconVisibleInMenu(False)
                action.setIcon(QIcon())
            menu.exec(widget.mapToGlobal(point))

        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(show_custom_menu)

    def _limit_text_length(self, field, max_length):
        """Limit the text length for title or description fields."""
        if field == "title":
            text = self._title_input.text()
            if len(text) > max_length:
                self._title_input.blockSignals(True)
                self._title_input.setText(text[:max_length])
                self._title_input.blockSignals(False)
        elif field == "description":
            text = self._desc_input.toPlainText()
            if len(text) > max_length:
                self._desc_input.blockSignals(True)
                self._desc_input.setPlainText(text[:max_length])
                self._desc_input.blockSignals(False)

    def _select_category(self, category_name):
        self._selected_category = category_name
        for cat_name, btn in self._category_buttons:
            btn.setChecked(cat_name == category_name)

    def _add_task_to_menu(self, task, layout, completed=False):
        container = TaskFrame(
            self,
            task,
            completed,
            self._icons,
            self._categories,
            expand_callback=self._expand_task,
            archive_callback=self._archive_task,
            delete_callback=self._delete_task,
            reorder_callback=self._reorder_tasks,
        )
        expanded = self._expanded_task_id == task["id"]
        class_list = [
            "task-item",
            "completed" if completed else "",
            task.get("category", "default"),
            "expanded" if expanded else "",
        ]
        container.setProperty("class", " ".join(filter(None, class_list)))
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        container.setContentsMargins(0, 0, 0, 0)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        checkbox = QPushButton(self._icons["checked"] if completed else self._icons["unchecked"])
        checkbox.setChecked(completed)
        checkbox.setProperty("class", "task-checkbox")
        checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if completed:
            checkbox.setCheckable(True)
            checkbox.setChecked(True)

            def uncomplete_task():
                self._uncomplete_task(task)

            checkbox.clicked.connect(uncomplete_task)
        if not completed:
            checkbox.setCheckable(True)
            checkbox.setChecked(False)

            def delayed_archive(checked, t=task, cb=checkbox):
                cb.setChecked(True)
                cb.setEnabled(False)
                container.setProperty("class", f"task-item completed {task.get('category', 'default')}")
                refresh_widget_style(container)
                checkbox.setText(self._icons["checked"])

                def do_archive():
                    for i, existing_task in enumerate(self._tasks):
                        if existing_task["id"] == t["id"]:
                            self._tasks[i]["completed"] = True
                            break
                    self._save_tasks()
                    TodoWidget.update_all()
                    try:
                        if hasattr(self, "_menu") and self._menu and self._menu.isVisible():
                            self._refresh_menu_task_list()
                    except RuntimeError:
                        pass

                QTimer.singleShot(200, do_archive)

            checkbox.clicked.connect(delayed_archive)
        container_layout.addWidget(checkbox, alignment=Qt.AlignmentFlag.AlignTop)

        text_container = QWidget()
        text_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        title_label = QLabel(task["title"])
        title_label.setProperty("class", "title")
        title_label.setWordWrap(True)

        text_layout.addWidget(title_label)

        if self._expanded_task_id == task["id"]:
            if task.get("description"):
                desc_label = QLabel()
                desc_label.setProperty("class", "description")
                desc_label.setWordWrap(True)
                desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                desc_label.setOpenExternalLinks(True)
                desc = task["description"]

                if not bool(re.search(r"<a\s+href=", desc, re.IGNORECASE)):

                    def replacer(match):
                        url = match.group(1)
                        domain = urllib.parse.urlparse(url).netloc or "link"
                        return f'<a style="text-decoration:none" href="{url}">{domain}</a>'

                    desc = re.sub(r"(https?://[^\s]+)", replacer, desc)
                desc_label.setText(desc)
                if completed:
                    desc_label.setProperty("class", "description completed")
                text_layout.addWidget(desc_label)
            try:
                created_at = datetime.datetime.fromisoformat(task["created_at"])
                now = datetime.datetime.now()
                delta = now - created_at
                if delta.days == 0:
                    if delta.seconds < 60:
                        friendly_date = "Just now"
                    elif delta.seconds < 3600:
                        minutes = delta.seconds // 60
                        friendly_date = f"{minutes} min ago"
                    else:
                        hours = delta.seconds // 3600
                        friendly_date = f"{hours} hour{'s' if hours != 1 else ''} ago"
                elif delta.days == 1:
                    friendly_date = "Yesterday"
                elif 1 < delta.days < 30:
                    friendly_date = f"{delta.days} days ago"
                else:
                    friendly_date = created_at.strftime("%Y-%m-%d")
                date_label_icon = QLabel(self._icons["date"])
                date_label_icon.setProperty("class", "date-icon")
                date_label = QLabel(friendly_date)
                date_label.setProperty("class", "date-text")

                category = task.get("category", "default")
                category_config = self._categories.get(category, {})
                cat_label_icon = QLabel(self._icons["category"])
                cat_label_icon.setProperty("class", f"category-icon {category}")
                cat_label = QLabel(category_config["label"])
                cat_label.setProperty("class", f"category-text {category}")

                edit_btn = QPushButton(self._icons["edit"])
                edit_btn.setProperty("class", "edit-task-button")
                edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                edit_btn.clicked.connect(lambda _, t=task: self._show_edit_task_dialog(t))

                delete_btn = QPushButton(self._icons["delete"])
                delete_btn.setProperty("class", "delete-task-button")
                delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                delete_btn.clicked.connect(lambda _, t=task: self._delete_task(t))

                info_row = QFrame()
                info_row.setProperty("class", "task-info-row")
                info_layout = QHBoxLayout(info_row)
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(0)
                info_layout.addWidget(date_label_icon)
                info_layout.addWidget(date_label)
                info_layout.addWidget(cat_label_icon)
                info_layout.addWidget(cat_label)
                info_layout.addStretch()
                info_layout.addWidget(edit_btn)
                info_layout.addWidget(delete_btn)
                text_layout.addWidget(info_row)
            except (ValueError, TypeError) as e:
                logging.error(f"Error formatting task info: {e}")

        container_layout.addWidget(text_container)
        container.setAcceptDrops(True)
        container._drag_start_position = None
        container._task_id = task["id"]
        container._drop_highlight = False

        layout.addWidget(container)

    def _uncomplete_task(self, task):
        for i, existing_task in enumerate(self._tasks):
            if existing_task["id"] == task["id"]:
                self._tasks[i]["completed"] = False
                break
        self._save_tasks()
        TodoWidget.update_all()
        self._refresh_menu_task_list()

    def _archive_task(self, task):
        for i, existing_task in enumerate(self._tasks):
            if existing_task["id"] == task["id"]:
                self._tasks[i]["completed"] = True
                break
        self._save_tasks()
        TodoWidget.update_all()
        self._remove_task_widget_from_menu(task["id"])

    def _delete_task(self, task):
        self._tasks = [t for t in self._tasks if t["id"] != task["id"]]
        self._save_tasks()
        TodoWidget.update_all()
        self._remove_task_widget_from_menu(task["id"])

    def _remove_task_widget_from_menu(self, task_id):
        """Remove the widget for a given task_id from the menu, and refresh if needed."""
        if hasattr(self, "_menu") and self._menu:
            scroll_areas = self._menu.findChildren(QScrollArea)
            if scroll_areas:
                scroll_area = scroll_areas[0]
                scroll_widget = scroll_area.widget()
                if scroll_widget:
                    layout = scroll_widget.layout()
                    widget_to_remove = None
                    for i in range(layout.count()):
                        w = layout.itemAt(i).widget()
                        if hasattr(w, "_task_id") and w._task_id == task_id:
                            widget_to_remove = w
                            break
                    if widget_to_remove:
                        widget_to_remove.setParent(None)
                    # Only refresh if no task items left after removal
                    task_items_left = [
                        layout.itemAt(i).widget()
                        for i in range(layout.count())
                        if hasattr(layout.itemAt(i).widget(), "_task_id")
                    ]
                    if len(task_items_left) == 0:
                        self._refresh_menu_task_list()

    def _reorder_tasks(self, source_id, target_id):
        try:
            tasks_sorted = sorted(self._tasks, key=lambda t: t["order"], reverse=True)
            source_index = next((i for i, t in enumerate(tasks_sorted) if str(t["id"]) == source_id), -1)
            target_index = next((i for i, t in enumerate(tasks_sorted) if str(t["id"]) == target_id), -1)
            if source_index != -1 and target_index != -1 and source_index != target_index:
                task = tasks_sorted.pop(source_index)
                tasks_sorted.insert(target_index, task)
                for idx, t in enumerate(tasks_sorted):
                    t["order"] = len(tasks_sorted) - idx - 1

                self._tasks = sorted(tasks_sorted, key=lambda t: t["order"], reverse=True)
                self._save_tasks()
                self._refresh_menu_task_list()
        except Exception as e:
            logging.error(f"Failed to reorder tasks: {e}")


class TaskFrame(QFrame):
    def __init__(
        self,
        main_widget,
        task,
        completed,
        icons,
        categories,
        expand_callback,
        archive_callback,
        delete_callback,
        reorder_callback,
    ):
        super().__init__(main_widget)
        self._main_widget = main_widget
        self._drag_start_position = None
        self._task_id = task["id"]
        self._drop_highlight = False
        self._task = task
        self._completed = completed
        self._icons = icons
        self._categories = categories
        self._expand_callback = expand_callback
        self._archive_callback = archive_callback
        self._delete_callback = delete_callback
        self._reorder_callback = reorder_callback

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.pos()
            if self._main_widget._expanded_task_id != self._task_id:
                self._expand_callback(self._task_id)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_position:
            if (event.pos() - self._drag_start_position).manhattanLength() >= 1:
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(self._task_id))
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self._drop_highlight = True
            self.setProperty("class", f"task-item drop-highlight {self._task.get('category', 'default')}")
            refresh_widget_style(self)
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_highlight = False
        self.setProperty("class", f"task-item {self._task.get('category', 'default')}")
        refresh_widget_style(self)
        self.update()

    def dragMoveEvent(self, event):
        scroll_area = self
        while scroll_area and not isinstance(scroll_area, QScrollArea):
            scroll_area = scroll_area.parent()
        if scroll_area:
            global_pos = self.mapToGlobal(event.position().toPoint())
            viewport_pos = scroll_area.viewport().mapFromGlobal(global_pos)
            margin = 40
            if viewport_pos.y() < margin:
                scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().value() - 20)
            elif viewport_pos.y() > scroll_area.viewport().height() - margin:
                scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().value() + 20)
        event.acceptProposedAction()

    def dropEvent(self, event):
        self._drop_highlight = False
        self.setProperty("class", f"task-item {self._task.get('category', 'default')}")
        refresh_widget_style(self)
        self.update()
        source_id = event.mimeData().text()
        target_id = str(self._task_id)
        if source_id != target_id:
            self._reorder_callback(source_id, target_id)
        event.acceptProposedAction()
