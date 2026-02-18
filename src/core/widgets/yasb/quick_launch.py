from PyQt6.QtCore import QAbstractListModel, QEvent, QMimeData, QModelIndex, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDrag,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from core.utils.utilities import LoaderLine, PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.quick_launch.base_provider import ProviderResult
from core.utils.widgets.quick_launch.context_menu import QuickLaunchContextMenuService
from core.utils.widgets.quick_launch.icon_utils import load_and_scale_icon, svg_to_pixmap
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_NO_RESULTS,
    ICON_SEARCH_INPUT,
    ICON_SEARCH_MAIN,
    ICON_SUBMIT,
)
from core.utils.widgets.quick_launch.service import QuickLaunchService
from core.utils.win32.utilities import find_focused_screen
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.quick_launch import QuickLaunchConfig
from core.widgets.base import BaseWidget


class ResultListModel(QAbstractListModel):
    """Model holding ProviderResult items with precomputed icon pixmaps."""

    RESULT_ROLE = Qt.ItemDataRole.UserRole + 1
    ICON_ROLE = Qt.ItemDataRole.UserRole + 2

    _emoji_cache: dict[tuple[str, int, float], QPixmap | None] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[ProviderResult] = []
        self._icons: dict[int, QPixmap] = {}
        self._late_icons: dict[str, QPixmap] = {}
        self._icon_size: int = 0
        self._dpr: float = 1.0

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        default = super().flags(index)
        if not index.isValid():
            return default
        result = self.result_at(index.row())
        if result and result.action_data.get("path"):
            return default | Qt.ItemFlag.ItemIsDragEnabled
        return default

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._results)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._results)):
            return None
        row = index.row()
        result = self._results[row]
        if role == self.RESULT_ROLE:
            return result
        if role == self.ICON_ROLE:
            if result.id and result.id in self._late_icons:
                return self._late_icons[result.id]
            if row not in self._icons:
                pixmap = self._compute_icon(result, self._icon_size, self._dpr)
                self._icons[row] = pixmap
            return self._icons.get(row)
        if role == Qt.ItemDataRole.DisplayRole:
            return result.title
        return None

    def set_results(self, results: list[ProviderResult], icon_size: int, dpr: float):
        """Replace all results. Icons are computed lazily on first access."""
        self.beginResetModel()
        self._results = list(results)
        self._icons.clear()
        self._late_icons.clear()
        self._icon_size = icon_size
        self._dpr = dpr
        self.endResetModel()

    @staticmethod
    def _compute_icon(result: ProviderResult, icon_size: int, dpr: float) -> QPixmap | None:
        if result.icon_path:
            return load_and_scale_icon(result.icon_path, icon_size, dpr)
        if result.icon_char and result.icon_char.lstrip().startswith("<svg"):
            return svg_to_pixmap(result.icon_char, icon_size, dpr)
        if result.icon_char:
            return ResultListModel._render_emoji_pixmap(result.icon_char, icon_size, dpr)
        return None

    @staticmethod
    def _render_emoji_pixmap(char: str, size: int, dpr: float) -> QPixmap | None:
        """
        Render an emoji character to a pixmap.
        We should find a better way to do this without rendering to a large canvas and scanning for bounds,
        but this emoji fonts looks like have a bad gemetry.
        """
        key = (char, size, dpr)
        cached = ResultListModel._emoji_cache.get(key)
        if cached is not None:
            return cached
        target = int(size * dpr)
        render_size = 128
        canvas_size = render_size * 2

        img = QImage(canvas_size, canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji")
        font.setPixelSize(render_size)
        p.setFont(font)
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, char)
        p.end()

        img = img.convertToFormat(QImage.Format.Format_ARGB32)
        width, height = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        raw = bytes(ptr)
        bpl = img.bytesPerLine()
        scan_width = width * 4

        top = 0
        for y in range(height):
            off = y * bpl
            if any(raw[i] for i in range(off + 3, off + scan_width, 4)):
                top = y
                break

        bottom = height - 1
        for y in range(height - 1, top, -1):
            off = y * bpl
            if any(raw[i] for i in range(off + 3, off + scan_width, 4)):
                bottom = y
                break

        left = width
        right = 0
        for y in range(top, bottom + 1):
            off = y * bpl
            row_alphas = raw[off + 3 : off + scan_width : 4]
            l = next((i for i, a in enumerate(row_alphas) if a), None)
            if l is not None:
                if l < left:
                    left = l
                r = len(row_alphas) - 1
                while r >= 0 and not row_alphas[r]:
                    r -= 1
                if r > right:
                    right = r

        if right < left or bottom < top:
            return None

        pad = 2
        crop_rect = QRect(
            max(0, left - pad),
            max(0, top - pad),
            min(width, right - left + 1 + pad * 2),
            min(height, bottom - top + 1 + pad * 2),
        )

        pixmap = QPixmap.fromImage(img.copy(crop_rect)).scaled(
            target, target, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        pixmap.setDevicePixelRatio(dpr)
        ResultListModel._emoji_cache[key] = pixmap
        return pixmap

    def update_icon(self, result_id: str, icon_path: str, icon_size: int, dpr: float):
        """Update an icon that was loaded asynchronously."""
        pixmap = load_and_scale_icon(icon_path, icon_size, dpr)
        if pixmap.isNull():
            return
        self._late_icons[result_id] = pixmap
        for i, r in enumerate(self._results):
            if r.id == result_id:
                idx = self.index(i)
                self.dataChanged.emit(idx, idx, [self.ICON_ROLE])
                break

    def result_at(self, row: int) -> ProviderResult | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None


class ResultItemDelegate(QStyledItemDelegate):
    """Delegate that paints result items using QListView CSS for styling."""

    def __init__(self, icon_size: int, show_icons: bool, desc_style_label: QLabel, parent=None):
        super().__init__(parent)
        self._icon_size = icon_size
        self._show_icons = show_icons
        self._spacing = 12
        self._desc_style_label = desc_style_label

    def _get_desc_font(self) -> QFont:
        """Get description font from CSS style probe."""
        return self._desc_style_label.font()

    def _get_desc_color(self) -> QColor:
        """Get description color from CSS style probe."""
        return self._desc_style_label.palette().color(QPalette.ColorRole.WindowText)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        result: ProviderResult | None = index.data(ResultListModel.RESULT_ROLE)
        title_font = option.font
        title_fm = QFontMetrics(title_font)
        text_h = title_fm.height()
        if result and result.description:
            desc_fm = QFontMetrics(self._get_desc_font())
            text_h += 3 + desc_fm.height()
        content_h = max(text_h, self._icon_size if self._show_icons else 0)
        # Let Qt style system add CSS padding from ::item { padding: ... }
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.icon = QIcon()
        opt.decorationSize = QSize(0, 0)
        style = opt.widget.style() if opt.widget else QApplication.style()
        return style.sizeFromContents(
            QStyle.ContentsType.CT_ItemViewItem, opt, QSize(option.rect.width(), content_h), opt.widget
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipping(True)
        painter.setClipRect(option.rect)

        # Let Qt draw the item background (handles ::item, ::item:hover, ::item:selected CSS)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = QIcon()
        opt.decorationSize = QSize(0, 0)
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, opt.widget)

        result: ProviderResult | None = index.data(ResultListModel.RESULT_ROLE)
        if not result:
            painter.restore()
            return

        # Content rect respecting CSS padding from ::item { padding: ... }
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)
        x = rect.x()

        # Icon
        if self._show_icons:
            icon_y = rect.y() + (rect.height() - self._icon_size) // 2
            icon_pixmap: QPixmap | None = index.data(ResultListModel.ICON_ROLE)
            if icon_pixmap and not icon_pixmap.isNull():
                painter.drawPixmap(x, icon_y, self._icon_size, self._icon_size, icon_pixmap)
            x += self._icon_size + self._spacing

        # Text
        text_w = rect.right() - x
        title_font = option.font
        title_color = option.palette.color(QPalette.ColorRole.Text)
        title_fm = QFontMetrics(title_font)

        if result.description:
            desc_font = self._get_desc_font()
            desc_color = self._get_desc_color()
            desc_fm = QFontMetrics(desc_font)
            text_block_h = title_fm.height() + 3 + desc_fm.height()
            text_y = rect.y() + (rect.height() - text_block_h) // 2

            title_rect = QRect(x, text_y, text_w, title_fm.height())
            painter.setFont(title_font)
            painter.setPen(title_color)
            elided = title_fm.elidedText(result.title, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

            desc_rect = QRect(x, title_rect.bottom() + 3, text_w, desc_fm.height())
            painter.setFont(desc_font)
            painter.setPen(desc_color)
            elided_desc = desc_fm.elidedText(result.description, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(desc_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_desc)
        else:
            text_rect = QRect(x, rect.y(), text_w, rect.height())
            painter.setFont(title_font)
            painter.setPen(title_color)
            elided = title_fm.elidedText(result.title, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        painter.restore()


class ResultListView(QListView):
    """QListView subclass with custom drag support for result items."""

    def startDrag(self, supportedActions):
        index = self.currentIndex()
        if not index.isValid():
            return
        result: ProviderResult | None = index.data(ResultListModel.RESULT_ROLE)
        if not result:
            return
        path = result.action_data.get("path", "")
        if not path:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag.setMimeData(mime)
        pixmap: QPixmap | None = index.data(ResultListModel.ICON_ROLE)
        if pixmap and not pixmap.isNull():
            drag.setPixmap(
                pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction)


class QuickLaunchWidget(BaseWidget):
    validation_schema = QuickLaunchConfig
    _active_instance: "QuickLaunchWidget | None" = None

    def __init__(self, config: QuickLaunchConfig):
        super().__init__(class_name="quick-launch-widget")
        self.config = config

        self._popup: PopupWidget | None = None
        self._dpr = 1.0

        self._result_model: ResultListModel | None = None
        self._selected_index = -1
        self._pending_scroll_value = -1

        self._pending_query_id: str | None = None
        self._pending_search_text: str = ""
        self._loader: LoaderLine | None = None

        self._active_prefix: str | None = None

        self._service = QuickLaunchService.instance()
        self._service.request_refresh.connect(self._on_request_refresh)
        self._service.icon_ready.connect(self._on_icon_ready)
        self._service.query_finished.connect(self._on_query_finished)
        self._service.configure_providers(
            self.config.providers.model_dump(), self.config.max_results, self.config.show_icons
        )

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(self._widget_container)
        build_widget_label(self, self.config.label, None, self.config.label_shadow.model_dump())

        self.register_callback("toggle_quick_launch", self._toggle_quick_launch)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _toggle_quick_launch(self):
        if self.config.animation.enabled:
            AnimationManager.animate(self, self.config.animation.type, self.config.animation.duration)
        active = QuickLaunchWidget._active_instance
        if active is not None and active._popup and active._popup.isVisible() and not active._popup._is_closing:
            active._hide_popup()
        else:
            self._show_popup()

    def _show_popup(self):
        QuickLaunchWidget._active_instance = self
        self._dpr = self.screen().devicePixelRatio()
        if not self._popup:
            self._popup = self._create_popup()
        self._clear_prefix_chip()
        self._popup.search_input.blockSignals(True)
        self._popup.search_input.clear()
        self._popup.search_input.blockSignals(False)
        if self.config.compact_mode:
            self._set_compact_visible(False)
        self._center_popup_on_screen()
        self._popup.show()
        force_foreground_focus(int(self._popup.winId()))
        if not self.config.compact_mode:
            self._loader.start()
            self._update_results("")
        self._popup.search_input.setFocus()
        QTimer.singleShot(0, self._reset_scroll_position)

    def _hide_popup(self):
        if not self._popup or self._popup._is_closing:
            return
        self._pending_query_id = None
        self._stop_loader()
        self._popup.hide_animated()

    def _on_popup_closed(self):
        """Called when the fade-out animation finishes."""
        if not (self._popup and self._popup._is_closing):
            return
        self._pending_query_id = None
        self._active_prefix = None
        self._popup = None
        self._loader = None
        self._result_model = None
        self._selected_index = -1
        if QuickLaunchWidget._active_instance is self:
            QuickLaunchWidget._active_instance = None

    def _stop_loader(self):
        if not self._loader:
            return
        try:
            self._loader.stop()
        except RuntimeError:
            pass

    def _center_popup_on_screen(self):
        if not self._popup:
            return
        screen = self._get_target_screen()
        geo = screen.geometry()
        cfg = self.config.popup
        x = (geo.width() - cfg.width) // 2 + geo.x()
        y = (geo.height() - cfg.height) // 3 + geo.y()
        self._popup.move(x, y)

    def _get_target_screen(self):

        mode = self.config.popup.screen
        if mode == "cursor":
            screen_name = find_focused_screen(follow_mouse=True, follow_window=False)
        elif mode == "focus":
            screen_name = find_focused_screen(follow_mouse=False, follow_window=True)
        else:
            return QApplication.primaryScreen() or QApplication.screens()[0]
        if screen_name:
            for s in QApplication.screens():
                if s.name() == screen_name:
                    return s
        return QApplication.primaryScreen() or QApplication.screens()[0]

    def _set_compact_visible(self, show_results: bool):
        """Toggle results area visibility and resize popup for compact mode."""
        if not self._popup:
            return
        cfg = self.config.popup
        self._popup.content_widget.setVisible(show_results)
        if show_results:
            self._popup.setFixedHeight(cfg.height)
        else:
            # Shrink to just the search bar height
            search_h = self._popup.search_container.sizeHint().height()
            self._popup.setFixedHeight(search_h)

    def _reset_scroll_position(self):
        if self._popup and self._popup.isVisible():
            self._popup.results_view.scrollToTop()

    def _create_popup(self) -> PopupWidget:
        cfg = self.config.popup
        popup = PopupWidget(
            self,
            blur=cfg.blur,
            round_corners=cfg.round_corners,
            round_corners_type=cfg.round_corners_type,
            border_color=cfg.border_color,
            dark_mode=cfg.dark_mode,
        )
        popup.setProperty("class", "quick-launch-popup")
        popup._popup_content.setProperty("class", "container")
        popup.setFixedSize(cfg.width, cfg.height)
        popup._fade_animation.setDuration(40)
        popup._fade_animation.finished.connect(self._on_popup_closed)

        main_layout = QVBoxLayout(popup._popup_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        search_container = QFrame()
        search_container.setProperty("class", "search")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        search_icon = QLabel(ICON_SEARCH_INPUT)
        search_icon.setProperty("class", "search-icon")
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(search_icon)

        prefix_chip = QLabel()
        prefix_chip.setProperty("class", "prefix")
        prefix_chip.setVisible(False)
        search_layout.addWidget(prefix_chip)

        search_input = QLineEdit()
        search_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        search_input.setProperty("class", "search-input")
        search_input.setPlaceholderText(self.config.search_placeholder)
        search_input.textChanged.connect(self._on_search_text_changed)
        search_input.installEventFilter(self)
        search_layout.addWidget(search_input)

        enter_icon = QLabel(ICON_SUBMIT)
        enter_icon.setProperty("class", "search-submit-icon")
        enter_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(enter_icon)
        main_layout.addWidget(search_container)

        self._loader = LoaderLine(search_container)
        self._loader.attach_to_widget(search_container)

        # Results area virtualized QListView with custom delegate for styling and icon support
        results_view = ResultListView()
        results_view.setProperty("class", "results-list-view")
        results_view.setStyleSheet("""
            .results-list-view {
                background: transparent;
                border: none;
                outline: none;
            }
            .results-list-view QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 0;
            }
            .results-list-view QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                min-height: 20px;
                border-radius: 3px;
            }
            .results-list-view QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            .results-list-view QScrollBar::handle:vertical:pressed {
                background: rgba(255, 255, 255, 0.35);
            }
            .results-list-view QScrollBar::add-line:vertical,
            .results-list-view QScrollBar::sub-line:vertical {
                height: 0px;
            }
            .results-list-view QScrollBar::add-page:vertical,
            .results-list-view QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        results_view.setFrameShape(QFrame.Shape.NoFrame)
        results_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        results_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        results_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        results_view.setMouseTracking(True)
        results_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        results_view.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        results_view.setDragEnabled(True)
        results_view.setDragDropMode(QListView.DragDropMode.DragOnly)

        # Model + delegate
        self._result_model = ResultListModel(results_view)
        results_view.setModel(self._result_model)

        # Hidden style probe for description CSS
        desc_style_label = QLabel(results_view)
        desc_style_label.setProperty("class", "description")
        desc_style_label.setVisible(False)

        delegate = ResultItemDelegate(self.config.icon_size, self.config.show_icons, desc_style_label, results_view)
        results_view.setItemDelegate(delegate)

        # View signals
        results_view.clicked.connect(self._on_view_item_clicked)
        results_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        results_view.customContextMenuRequested.connect(self._on_view_context_menu)

        # Results wrapper (holds list view + empty-state overlay)
        results_wrapper = QFrame()
        results_wrapper.setProperty("class", "results")
        wrapper_layout = QVBoxLayout(results_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(results_view)

        # Empty-state widget
        empty_widget = QFrame()
        empty_widget.setProperty("class", "results-empty")
        empty_inner = QVBoxLayout(empty_widget)
        empty_inner.setContentsMargins(0, 0, 0, 0)
        empty_inner.setSpacing(8)
        empty_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel(ICON_SEARCH_INPUT)
        empty_icon.setProperty("class", "results-empty-icon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_inner.addWidget(empty_icon)
        empty_hint = QLabel("Type to search...")
        empty_hint.setProperty("class", "results-empty-text")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_inner.addWidget(empty_hint)
        empty_widget.setVisible(False)
        wrapper_layout.addWidget(empty_widget)

        # Content area results + preview
        content_widget = QFrame()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(results_wrapper, stretch=1)

        preview_frame = QFrame()
        preview_frame.setProperty("class", "preview")
        preview_frame.setFixedWidth(int(cfg.width * 0.4))
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        preview_frame.setVisible(False)
        content_layout.addWidget(preview_frame)

        main_layout.addWidget(content_widget, stretch=1)

        popup.search_container = search_container
        popup.content_widget = content_widget
        popup.prefix_chip = prefix_chip
        popup.search_input = search_input
        popup.results_view = results_view
        popup.empty_widget = empty_widget
        popup.empty_icon = empty_icon
        popup.empty_hint = empty_hint
        popup.preview_frame = preview_frame
        popup.preview_layout = preview_layout
        popup.keyPressEvent = self._handle_key_press

        QShortcut(QKeySequence(Qt.Key.Key_Escape), popup).activated.connect(self._hide_popup)
        return popup

    def _on_search_text_changed(self, search_text: str):
        """Handle text changes in the search input, detecting prefix activation."""
        if not self._popup:
            return
        # Prevent leading spaces in the search input
        stripped = search_text.lstrip()
        if stripped != search_text:
            self._popup.search_input.setText(stripped)
            return
        # Check if the typed text matches a provider prefix
        if not self._active_prefix and search_text:
            for p in self._service.providers:
                if p.prefix and search_text.startswith(p.prefix + " "):
                    remaining = search_text[len(p.prefix) + 1 :]
                    self._set_prefix_chip(p.prefix, remaining)
                    return
        # Compact mode show/hide results based on whether there is text
        if self.config.compact_mode:
            has_text = bool(search_text.strip())
            self._set_compact_visible(has_text)
            if not has_text:
                return
        self._update_results(search_text)

    def _update_results(self, search_text: str):
        if not self._popup:
            return
        full_text = (self._active_prefix + " " + search_text) if self._active_prefix else search_text
        self._pending_search_text = full_text
        if not full_text.strip() and self.config.home_page:
            self._pending_query_id = None
            self._stop_loader()
            self._show_home_page()
            return
        if full_text.strip():
            self._loader.start()
        self._pending_query_id = self._service.async_query(full_text, self.config.max_results)

    def _show_home_page(self):
        """Show provider shortcuts as the home page when search is empty."""
        providers = self._service.providers
        results = []
        for p in providers:
            if not p.prefix:
                continue
            results.append(
                ProviderResult(
                    title=p.prefix,
                    description=f"Activate {p.display_name or p.name}",
                    icon_char=p.icon,
                    provider=p.name,
                    action_data={"_home": True, "prefix": p.prefix},
                )
            )
        self._apply_results(results)

    def _apply_results(self, results: list):
        self._selected_index = -1

        if not results:
            has_text = bool(self._pending_search_text.strip())
            self._set_empty_icon(ICON_NO_RESULTS if has_text else ICON_SEARCH_MAIN)
            self._popup.empty_hint.setText("No results found" if has_text else "Type to search...")
            self._popup.results_view.setVisible(False)
            self._popup.empty_widget.setVisible(True)
            self._result_model.set_results([], 0, 1.0)
            self._clear_preview()
            return

        self._popup.empty_widget.setVisible(False)
        self._popup.results_view.setVisible(True)
        self._result_model.set_results(results, self.config.icon_size, self._dpr)
        self._clear_preview()

        if self._result_model.rowCount() > 0:
            scroll_val = self._pending_scroll_value
            self._pending_scroll_value = -1
            self._set_selected(0)
            if scroll_val >= 0:
                QTimer.singleShot(
                    0,
                    lambda v=scroll_val: (
                        self._popup
                        and self._popup.results_view.verticalScrollBar()
                        and self._popup.results_view.verticalScrollBar().setValue(v)
                    ),
                )

    def _set_empty_icon(self, icon_value: str):
        """Render empty-state icon from either inline SVG or icon-font glyph text."""
        if not self._popup:
            return
        label = self._popup.empty_icon
        if isinstance(icon_value, str) and icon_value.lstrip().startswith("<svg"):
            pixmap = svg_to_pixmap(icon_value, 88, self._dpr)
            if not pixmap.isNull():
                label.setText("")
                label.setPixmap(pixmap)
                return
        label.setPixmap(QPixmap())
        label.setText(icon_value)

    def _on_view_item_clicked(self, model_index):
        """Handle click on a list-view item."""
        if self._popup and self._popup.isActiveWindow():
            self._execute_result(model_index.row())

    def _on_view_context_menu(self, pos):
        """Handle right-click context menu on the list view."""
        index = self._popup.results_view.indexAt(pos)
        if not index.isValid():
            return
        global_pos = self._popup.results_view.viewport().mapToGlobal(pos)
        self._show_item_context_menu(index.row(), global_pos)

    def _show_item_context_menu(self, index: int, global_pos: QPoint):
        if not self._result_model:
            return
        result = self._result_model.result_at(index)
        if not result:
            return

        provider = self._get_provider(result.provider)
        if not provider:
            return

        menu_result = QuickLaunchContextMenuService.show(self.window(), provider, result, global_pos)
        if menu_result.refresh_results and self._popup and self._popup.isVisible():
            sb = self._popup.results_view.verticalScrollBar()
            self._pending_scroll_value = sb.value() if sb else 0
            self._update_results(self._popup.search_input.text())
        if menu_result.close_popup:
            QTimer.singleShot(0, self._hide_popup)

    def _set_selected(self, index: int):
        self._selected_index = index
        if not self._popup or not self._result_model:
            return
        if 0 <= index < self._result_model.rowCount():
            model_index = self._result_model.index(index)
            self._popup.results_view.setCurrentIndex(model_index)
            if index > 0:
                self._popup.results_view.scrollTo(model_index, QListView.ScrollHint.EnsureVisible)
            else:
                self._popup.results_view.scrollToTop()
            self._update_preview(index)
        else:
            self._popup.results_view.clearSelection()
            self._clear_preview()

    def _clear_preview(self):
        """Hide the preview pane and clear its content."""
        if not self._popup:
            return
        layout = self._popup.preview_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._popup.preview_frame.setProperty("class", "preview")
        self._popup.preview_frame.setVisible(False)

    def _update_preview(self, index: int):
        """Update the preview pane based on the selected result."""
        if not self._popup or not self._result_model:
            self._clear_preview()
            return
        result = self._result_model.result_at(index)
        if not result:
            self._clear_preview()
            return
        preview = result.preview
        if not preview:
            self._clear_preview()
            return

        self._clear_preview()
        kind = preview.get("kind", "")
        layout = self._popup.preview_layout

        # Inline edit form
        if kind == "edit" and preview.get("fields"):
            self._render_edit_preview(index, preview, layout)
            return

        # Content area (stretch=1)
        if kind == "text" and preview.get("text"):
            text_area = QScrollArea()
            text_area.setObjectName("preview_text_area")
            text_area.setWidgetResizable(True)
            text_area.setStyleSheet("""
                QScrollArea#preview_text_area {
                    background: transparent; 
                    border: none;
                }
           """)
            text_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            text_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            text_area.setFrameShape(QFrame.Shape.NoFrame)
            text_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            text_label = QLabel(preview["text"])
            text_label.setProperty("class", "preview-text")
            text_label.setWordWrap(True)
            text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            text_area.setWidget(text_label)
            layout.addWidget(text_area, stretch=1)
        elif kind == "image" and preview.get("image_data"):
            img_label = QLabel()
            img_label.setProperty("class", "preview-image")
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap()
            pixmap.loadFromData(preview["image_data"])
            if not pixmap.isNull():
                frame_w = self._popup.preview_frame.width() or int(self.config.popup.width * 0.38)
                scaled = pixmap.scaled(
                    QSize(frame_w - 24, int(self.config.popup.height * 0.55)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled)
            layout.addWidget(img_label, stretch=1)
        else:
            return

        # Metadata frame for all kinds
        title = preview.get("title", "")
        subtitle = preview.get("subtitle", "")
        if title or subtitle:
            meta_frame = QFrame()
            meta_frame.setProperty("class", "preview-meta")
            meta_layout = QVBoxLayout(meta_frame)
            meta_layout.setContentsMargins(0, 0, 0, 0)
            meta_layout.setSpacing(2)
            if title:
                lbl = QLabel(title)
                lbl.setProperty("class", "preview-title")
                lbl.setWordWrap(True)
                meta_layout.addWidget(lbl)
            if subtitle:
                for line in subtitle.split("\n"):
                    if line.strip():
                        lbl = QLabel(line.strip())
                        lbl.setProperty("class", "preview-subtitle")
                        lbl.setWordWrap(True)
                        meta_layout.addWidget(lbl)
            layout.addWidget(meta_frame)

        self._popup.preview_frame.setVisible(True)

    def _render_edit_preview(self, index: int, preview: dict, layout):
        """Render an inline edit form in the preview panel."""
        if not self._popup or not self._result_model:
            return
        result = self._result_model.result_at(index)
        if not result:
            return

        self._popup.preview_frame.setProperty("class", "preview edit")

        fields = preview.get("fields", [])
        save_action = preview.get("action", "save")
        form_widgets: dict = {}

        for field_def in fields:
            fid = field_def.get("id", "")
            label_text = field_def.get("label", "")
            if label_text:
                lbl = QLabel(label_text)
                lbl.setProperty("class", "preview-title")
                layout.addWidget(lbl)

            if field_def.get("type") == "multiline":
                widget = QPlainTextEdit()
                widget.setPlaceholderText(field_def.get("placeholder", ""))
                widget.setPlainText(field_def.get("value", ""))
                widget.setProperty("class", "preview-text-edit")
                layout.addWidget(widget, stretch=1)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(field_def.get("placeholder", ""))
                widget.setText(field_def.get("value", ""))
                widget.setProperty("class", "preview-line-edit")
                layout.addWidget(widget)
            form_widgets[fid] = widget

        # Save / Cancel buttons
        btn_frame = QFrame()
        btn_frame.setProperty("class", "preview-actions")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "preview-btn")
        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "preview-btn save")

        def collect_and_save(_checked=False, _result=result):
            data = {}
            for fid, w in form_widgets.items():
                data[fid] = w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()
            self._handle_preview_action(_result, save_action, data)

        def cancel(_checked=False, _result=result):
            self._handle_preview_action(_result, "cancel", {})

        save_btn.clicked.connect(collect_and_save)
        cancel_btn.clicked.connect(cancel)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addWidget(btn_frame)

        self._popup.preview_frame.setVisible(True)

        # Focus the first field only if the search input doesn't have focus
        first = next(iter(form_widgets.values()), None)
        if first and not self._popup.search_input.hasFocus():
            QTimer.singleShot(0, first.setFocus)

    def _get_provider(self, name: str):
        """Look up a provider by name."""
        return next((p for p in self._service.providers if p.name == name), None)

    def _handle_preview_action(self, result: ProviderResult, action_id: str, data: dict):
        """Forward a preview-panel action to the owning provider."""
        provider = self._get_provider(result.provider)
        if not provider:
            return
        menu_result = provider.handle_preview_action(action_id, result, data)
        if menu_result.close_popup:
            QTimer.singleShot(0, self._hide_popup)
        elif self._popup and self._popup.isVisible():
            self._update_results(self._popup.search_input.text())

    def _on_request_refresh(self):
        """Called by the service when a provider requests a refresh of the current results."""
        if self._popup and self._popup.isVisible():
            self._update_results(self._popup.search_input.text())

    def _on_icon_ready(self, result_id: str, icon_path: str):
        if self._popup and self._popup.isVisible() and self._result_model:
            self._result_model.update_icon(result_id, icon_path, self.config.icon_size, self._dpr)

    def _on_query_finished(self, query_id: str, results: list):
        if query_id != self._pending_query_id:
            return
        if not self._popup or not self._popup.isVisible():
            return
        self._stop_loader()
        self._apply_results(results)

    def _handle_key_press(self, event):
        key = event.key()
        count = self._result_model.rowCount() if self._result_model else 0
        if key == Qt.Key.Key_Down and count > 0:
            self._set_selected(min(self._selected_index + 1, count - 1))
            return event.accept()
        if key == Qt.Key.Key_Up and count > 0:
            self._set_selected(max(self._selected_index - 1, 0))
            return event.accept()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if 0 <= self._selected_index < count:
                self._execute_result(self._selected_index)
            return event.accept()
        if self._popup and not self._popup.search_input.hasFocus():
            # Don't steal focus from edit form fields in the preview panel
            focused = QApplication.focusWidget()
            if focused and self._popup.preview_frame.isAncestorOf(focused):
                return
            self._popup.search_input.setFocus()
            self._popup.search_input.keyPressEvent(event)

    def _execute_result(self, index: int):
        if not self._result_model:
            return
        result = self._result_model.result_at(index)
        if not result:
            return
        # Home page item - activate prefix chip
        if result.action_data.get("_home"):
            prefix = result.action_data.get("prefix", "")
            initial_text = result.action_data.get("initial_text", "")
            if prefix and self._popup:
                self._set_prefix_chip(prefix, initial_text)
            return
        should_close = None
        provider = self._get_provider(result.provider)
        if provider:
            should_close = provider.execute(result)
        if should_close is True:
            QTimer.singleShot(0, self._hide_popup)
        elif should_close is False and self._popup:
            text = self._popup.search_input.text()
            self._update_results(text)
        # None means no action needed (e.g. inline edit form is already visible)

    def _set_prefix_chip(self, prefix: str, initial_text: str = ""):
        """Activate a prefix chip in the search bar."""
        self._active_prefix = prefix
        if self._popup:
            self._popup.prefix_chip.setText(prefix)
            self._popup.prefix_chip.setVisible(True)
            self._popup.search_input.blockSignals(True)
            self._popup.search_input.setText(initial_text)
            self._popup.search_input.blockSignals(False)
            # Set provider-specific placeholder
            provider = next((p for p in self._service.providers if p.prefix == prefix), None)
            if provider:
                self._popup.search_input.setPlaceholderText(provider.input_placeholder)
            self._popup.search_input.setFocus()
            if self.config.compact_mode:
                self._set_compact_visible(True)
            self._update_results(initial_text)

    def _clear_prefix_chip(self):
        """Remove the active prefix chip."""
        self._active_prefix = None
        if self._popup:
            self._popup.prefix_chip.setVisible(False)
            self._popup.prefix_chip.setText("")
            self._popup.search_input.setPlaceholderText(self.config.search_placeholder)

    def eventFilter(self, obj, event):
        """Intercept Backspace on the search input to remove the prefix chip."""
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Backspace
            and self._active_prefix
            and self._popup
            and obj is self._popup.search_input
        ):
            if self._popup.search_input.cursorPosition() == 0 and not self._popup.search_input.hasSelectedText():
                self._clear_prefix_chip()
                text = self._popup.search_input.text()
                if self.config.compact_mode and not text.strip():
                    self._set_compact_visible(False)
                else:
                    self._update_results(text)
                return True
        return super().eventFilter(obj, event)
