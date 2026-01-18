import logging

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from core.config import get_config
from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widget_builder import WidgetBuilder
from core.utils.widgets.overlay_container import OverlayBackgroundMedia, OverlayBackgroundShader
from core.validation.widgets.yasb.overlay_container import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class OverlayPanel(QWidget):
    """
    Overlay panel that integrates directly into the bar.
    Positions itself relative to bar sections or specific widgets.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # No window flags - this is a direct child of the bar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Container for the child widget
        self._container = QFrame(self)
        self._container.setProperty("class", "overlay-panel")

        # Layout for the child widget
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._container)

        self._child_widget = None
        self._background_widget = None
        self._pass_through = False

    def set_background_widget(self, widget):
        """Set a background widget that will be positioned behind the child widget."""
        if self._background_widget:
            self._background_widget.setParent(None)
            self._background_widget.deleteLater()

        self._background_widget = widget
        if widget:
            # Set as child of container but don't add to layout
            widget.setParent(self._container)
            # Show the widget first (required for OpenGL initialization)
            widget.show()
            # Position it to cover the entire container
            # Use QTimer to ensure container has valid geometry
            QTimer.singleShot(0, lambda: self._update_background_geometry())
            # Lower it so it appears behind the child widget
            widget.lower()

    def _update_background_geometry(self):
        """Update background widget geometry to match container."""
        if self._background_widget and self._container:
            rect = self._container.rect()
            if rect.isValid() and rect.width() > 0 and rect.height() > 0:
                # Apply offset if widget has offset attributes
                offset_x = getattr(self._background_widget, "media_offset_x", 0)
                offset_y = getattr(self._background_widget, "media_offset_y", 0)

                # Create new rect with offset applied
                adjusted_rect = QRect(rect.x() + offset_x, rect.y() + offset_y, rect.width(), rect.height())
                self._background_widget.setGeometry(adjusted_rect)
            else:
                # Retry after a short delay if container doesn't have valid geometry yet
                QTimer.singleShot(50, self._update_background_geometry)

    def set_child_widget(self, widget):
        """Set the child widget to be displayed in the overlay."""
        if self._child_widget:
            self._layout.removeWidget(self._child_widget)
            self._child_widget.setParent(None)

        self._child_widget = widget
        if widget:
            self._layout.addWidget(widget)

    def set_pass_through(self, enabled: bool):
        """Enable or disable mouse event pass-through."""
        self._pass_through = enabled
        if enabled:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def resizeEvent(self, event):
        """Update background widget geometry when container is resized."""
        super().resizeEvent(event)
        if self._background_widget:
            # Apply offset if widget has offset attributes
            offset_x = getattr(self._background_widget, "media_offset_x", 0)
            offset_y = getattr(self._background_widget, "media_offset_y", 0)

            rect = self._container.rect()
            adjusted_rect = QRect(rect.x() + offset_x, rect.y() + offset_y, rect.width(), rect.height())
            self._background_widget.setGeometry(adjusted_rect)

    def cleanup(self):
        """Clean up the overlay panel."""
        if self._background_widget:
            self._background_widget.setParent(None)
            self._background_widget.deleteLater()
            self._background_widget = None

        if self._child_widget:
            self._layout.removeWidget(self._child_widget)
            self._child_widget.setParent(None)
            self._child_widget = None

        self.setParent(None)
        self.deleteLater()


class OverlayContainerWidget(BaseWidget):
    """
    Container widget that creates an overlay integrated directly into the bar.
    Can contain any child widget configured through YAML.

    New features:
    - Direct bar integration (no separate window)
    - Position relative to specific widgets
    - Proper z-ordering (behind/above)
    - Automatic resize tracking

    Use cases:
    - Background visualization (e.g., cava behind media widget)
    - Decorative overlays
    - Additional information layers
    """

    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        target: str,
        target_widget: str,
        position: str,
        offset_x: int,
        offset_y: int,
        width: str | int,
        height: str | int,
        opacity: float,
        pass_through_clicks: bool,
        z_index: int,
        child_widget_name: str,
        show_toggle: bool,
        toggle_label: str,
        auto_show: bool,
        callbacks: dict[str, str],
        container_padding: dict[str, int],
        container_shadow: dict[str, any],
        label_shadow: dict[str, any],
        background_media: dict[str, any],
        background_shader: dict[str, any],
    ):
        super().__init__(class_name="overlay-container-widget")

        # Configuration
        self._target = target
        self._target_widget = target_widget
        self._position = position  # "behind" or "above"
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._width = width
        self._height = height
        self._opacity = opacity
        self._pass_through_clicks = pass_through_clicks
        self._z_index = z_index
        self._child_widget_name = child_widget_name
        self._show_toggle = show_toggle
        self._toggle_label = toggle_label
        self._auto_show = auto_show
        self._padding = container_padding
        self._container_shadow = container_shadow
        self._label_shadow = label_shadow
        self._background_media = background_media
        self._background_shader = background_shader

        # State
        self._overlay_panel = None
        self._child_widget = None
        self._bar_widget = None
        self._target_widget_ref = None
        self._is_visible = auto_show
        self._update_timer = None  # Debounce timer for geometry updates
        self._is_updating = False  # Prevent recursive updates
        self._is_cleaning_up = False  # Prevent operations during cleanup
        self._media_background = None  # Media background handler
        self._shader_background = None  # Shader background handler
        self._init_retry_count = 0  # Track initialization retries
        self._max_init_retries = 50  # Max 5 seconds (50 * 100ms)

        # Setup UI
        self._setup_ui()

        # Register callbacks
        self.register_callback("toggle_overlay", self._toggle_overlay)
        self.callback_left = callbacks.get("on_left", "toggle_overlay")
        self.callback_middle = callbacks.get("on_middle", "do_nothing")
        self.callback_right = callbacks.get("on_right", "do_nothing")

        # Defer initialization
        QTimer.singleShot(100, self._initialize_overlay)

    def _setup_ui(self):
        """Setup the UI for the widget."""
        logging.info(
            f"OverlayContainerWidget._setup_ui: show_toggle={self._show_toggle}, child={self._child_widget_name}"
        )

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        logging.debug(f"OverlayContainerWidget._setup_ui: margins set to {self._padding}")

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "toggle-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)
        logging.debug("OverlayContainerWidget._setup_ui: widget_container created and added to layout")

        # Toggle button (optional)
        if self._show_toggle:
            from PyQt6.QtWidgets import QSizePolicy

            self._toggle_button = QLabel(self._toggle_label)
            self._toggle_button.setProperty("class", "toggle-button")
            self._toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)

            # Set size policy to prevent toggle button from expanding
            self._toggle_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

            # CRITICAL: Set minimum width via Qt property (cannot be overridden by CSS)
            # This ensures toggle button is ALWAYS visible regardless of user CSS
            self._toggle_button.setMinimumWidth(20)

            # Add inline stylesheet for padding (improves visibility)
            # We use object name selector for specificity
            self._toggle_button.setObjectName("yasb-overlay-toggle")
            self._toggle_button.setStyleSheet("""
                QLabel#yasb-overlay-toggle {
                    min-width: 20px;
                    padding: 0px 4px;
                }
            """)

            add_shadow(self._toggle_button, self._label_shadow)
            self._widget_container_layout.addWidget(self._toggle_button)

            logging.info(
                f"OverlayContainerWidget._setup_ui: Toggle button created with label '{self._toggle_label}', min_width=20"
            )
            logging.debug(f"OverlayContainerWidget._setup_ui: Toggle button visible={self._toggle_button.isVisible()}")
        else:
            # If no toggle, hide the container itself
            logging.warning("OverlayContainerWidget._setup_ui: show_toggle=False, hiding entire widget")
            self.hide()

    def _initialize_overlay(self):
        """Initialize the overlay panel after bar context is available."""
        try:
            logging.debug(f"OverlayContainerWidget._initialize_overlay: Starting initialization (retry {self._init_retry_count}/{self._max_init_retries})")

            # Wait for bar context
            if not hasattr(self, "bar_id") or self.bar_id is None:
                self._init_retry_count += 1
                
                if self._init_retry_count >= self._max_init_retries:
                    logging.error(f"OverlayContainerWidget: Failed to initialize after {self._max_init_retries} retries (5 seconds). bar_id not available.")
                    logging.error(f"OverlayContainerWidget: Widget hierarchy: {self._get_widget_hierarchy()}")
                    return
                
                logging.debug(f"OverlayContainerWidget._initialize_overlay: Waiting for bar_id, retrying in 100ms ({self._init_retry_count}/{self._max_init_retries})")
                QTimer.singleShot(100, self._initialize_overlay)
                return

            logging.info(f"OverlayContainerWidget._initialize_overlay: bar_id={self.bar_id}")

            # Find the bar widget
            self._bar_widget = self._find_bar_widget()
            if not self._bar_widget:
                logging.error("OverlayContainerWidget: Could not find bar widget")
                logging.error(f"OverlayContainerWidget: Widget hierarchy: {self._get_widget_hierarchy()}")
                return

            logging.info(
                f"OverlayContainerWidget._initialize_overlay: Found bar widget: {self._bar_widget.__class__.__name__}"
            )

            # Create child widget
            self._create_child_widget()

            # Create overlay panel
            self._create_overlay_panel()

            # Show if auto_show is enabled
            if self._auto_show:
                logging.info("OverlayContainerWidget._initialize_overlay: auto_show=True, calling _show_overlay()")
                self._show_overlay()
            else:
                logging.info("OverlayContainerWidget._initialize_overlay: auto_show=False, overlay will be hidden")

            # Set initial toggle button state
            if self._show_toggle and hasattr(self, "_toggle_button"):
                if self._is_visible:
                    self._toggle_button.setProperty("class", "toggle-button active")
                else:
                    self._toggle_button.setProperty("class", "toggle-button")
                refresh_widget_style(self._toggle_button)
                logging.debug(
                    f"OverlayContainerWidget._initialize_overlay: Toggle button state set (visible={self._is_visible})"
                )

            # Install event filter for resize tracking
            self._install_event_filters()

            logging.info(f"OverlayContainerWidget initialized with child: {self._child_widget_name}")
            logging.info(
                f"OverlayContainerWidget state: self.isVisible()={self.isVisible()}, _toggle_button.isVisible()={self._toggle_button.isVisible() if hasattr(self, '_toggle_button') else 'N/A'}"
            )

        except Exception as e:
            logging.error(f"OverlayContainerWidget: Error initializing overlay: {e}", exc_info=True)

    def _get_widget_hierarchy(self):
        """Get widget hierarchy for debugging."""
        hierarchy = []
        widget = self
        while widget:
            hierarchy.append(f"{widget.__class__.__name__}")
            widget = widget.parent()
        return " -> ".join(hierarchy)

    def _find_bar_widget(self):
        """Find the bar widget that contains this widget."""
        parent = self.parent()
        while parent:
            if parent.__class__.__name__ == "Bar":
                return parent
            parent = parent.parent()
        return None

    def _create_child_widget(self):
        """Create the child widget dynamically using WidgetBuilder."""
        try:
            # If no child widget name specified, that's OK - user might only want background
            if not self._child_widget_name:
                logging.info(
                    "OverlayContainerWidget: No child_widget_name specified, overlay will only show background"
                )
                return

            config = get_config()
            widgets_config = config.get("widgets", {})

            if self._child_widget_name not in widgets_config:
                logging.error(f"OverlayContainerWidget: Child widget '{self._child_widget_name}' not found in config")
                return

            # Get child widget config
            child_config = widgets_config[self._child_widget_name]

            # If child is a cava widget, limit bars_number based on bar_type to prevent lag
            if child_config.get("type", "").endswith("CavaWidget"):
                options = child_config.get("options", {})
                bar_type = options.get("bar_type", "bars")
                bars_number = options.get("bars_number", 200)

                # Apply performance limits
                if bar_type == "waves_mirrored" and bars_number > 100:
                    logging.warning(
                        f"OverlayContainerWidget: Clamping bars_number from {bars_number} to 100 for waves_mirrored to prevent lag"
                    )
                    options["bars_number"] = 100
                elif bar_type == "waves" and bars_number > 150:
                    logging.warning(
                        f"OverlayContainerWidget: Clamping bars_number from {bars_number} to 150 for waves to prevent lag"
                    )
                    options["bars_number"] = 150

            # Use WidgetBuilder to create the child widget
            widget_builder = WidgetBuilder(widgets_config)
            self._child_widget = widget_builder._build_widget(self._child_widget_name)

            if not self._child_widget:
                logging.error(f"OverlayContainerWidget: Failed to build child widget '{self._child_widget_name}'")
                return

            # Propagate bar context
            try:
                self._child_widget.bar_id = self.bar_id
                self._child_widget.monitor_hwnd = self.monitor_hwnd
                self._child_widget.parent_layout_type = getattr(self, "parent_layout_type", None)
            except Exception as e:
                logging.debug(f"OverlayContainerWidget: Could not propagate bar context: {e}")

            logging.info(f"OverlayContainerWidget: Created child widget '{self._child_widget_name}'")

        except Exception as e:
            logging.error(f"OverlayContainerWidget: Error creating child widget: {e}")

    def _create_overlay_panel(self):
        """Create the overlay panel as a direct child of the bar."""
        logging.debug(
            f"OverlayContainerWidget._create_overlay_panel: child_widget={self._child_widget is not None}, bar_widget={self._bar_widget is not None}"
        )

        # Bar widget is required, but child widget is optional (user might only want background)
        if not self._bar_widget:
            logging.error("OverlayContainerWidget: Cannot create overlay panel without bar widget")
            return

        # Check if we have anything to display (child widget OR background)
        has_background = self._background_shader.get("enabled", False) or self._background_media.get("enabled", False)

        if not self._child_widget and not has_background:
            logging.error("OverlayContainerWidget: Cannot create overlay panel without child widget or background")
            return

        # Create overlay panel as direct child of bar
        logging.info("OverlayContainerWidget._create_overlay_panel: Creating OverlayPanel with bar parent")
        self._overlay_panel = OverlayPanel(self._bar_widget)
        logging.debug(
            f"OverlayContainerWidget._create_overlay_panel: OverlayPanel created, visible={self._overlay_panel.isVisible()}"
        )

        # Priority: shader > media (only one can be active at a time)
        # Shader has priority because it's more advanced and can be customized more

        # Add background shader if enabled
        if self._background_shader.get("enabled", False):
            self._shader_background = OverlayBackgroundShader(self._background_shader, self._overlay_panel._container)
            shader_widget = self._shader_background.get_widget()
            if shader_widget:
                # Set shader widget as background (will be positioned behind child widget)
                self._overlay_panel.set_background_widget(shader_widget)
                logging.info("OverlayContainerWidget: Added background shader to overlay panel")
        # Add background media if enabled and shader is not
        elif self._background_media.get("enabled", False):
            self._media_background = OverlayBackgroundMedia(self._background_media, self._overlay_panel._container)
            media_widget = self._media_background.get_widget()
            if media_widget:
                # Set media widget as background (will be positioned behind child widget)
                self._overlay_panel.set_background_widget(media_widget)
                logging.info("OverlayContainerWidget: Added background media to overlay panel")

        self._overlay_panel.set_child_widget(self._child_widget)

        # Apply opacity using QGraphicsOpacityEffect (works for child widgets)
        if self._opacity < 1.0:
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(self._opacity)
            self._overlay_panel.setGraphicsEffect(opacity_effect)

        self._overlay_panel.set_pass_through(self._pass_through_clicks)

        logging.info("OverlayContainerWidget: Created overlay panel")

    def _install_event_filters(self):
        """Install event filters for resize tracking."""
        if self._bar_widget:
            self._bar_widget.installEventFilter(self)
            logging.debug("OverlayContainerWidget: Installed event filter on bar widget")

        # If targeting a specific widget, install filter on it too
        if self._target == "widget" and self._target_widget:
            target_widget = self._find_target_widget()
            if target_widget:
                self._target_widget_ref = target_widget
                target_widget.installEventFilter(self)
                logging.debug(
                    f"OverlayContainerWidget: Installed event filter on target widget '{self._target_widget}'"
                )

        # If targeting a section, install filters on all widgets in that section
        elif self._target in ["left", "center", "right"]:
            section_container = self._find_section_container(self._target)
            if section_container:
                section_container.installEventFilter(self)
                logging.debug(f"OverlayContainerWidget: Installed event filter on section container '{self._target}'")

                # Also install on widgets inside the section
                for widget in section_container.findChildren(BaseWidget):
                    widget.installEventFilter(self)
                    logging.debug(
                        f"OverlayContainerWidget: Installed event filter on widget {widget.__class__.__name__} in section '{self._target}'"
                    )

    def eventFilter(self, obj, event):
        """Handle events for resize tracking."""
        event_type = event.type()

        if event_type in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide):
            obj_name = obj.__class__.__name__

            # Check if event is from tracked objects
            should_update = False

            if obj == self._bar_widget:
                logging.debug(f"OverlayContainerWidget: Bar widget event: {event_type.name}")
                should_update = True
            elif obj == self._target_widget_ref:
                logging.debug(f"OverlayContainerWidget: Target widget ({obj_name}) event: {event_type.name}")
                should_update = True
            elif isinstance(obj, (BaseWidget, QFrame)):
                # Event from widget in section - update if we're tracking sections
                if self._target in ["left", "center", "right"]:
                    logging.debug(f"OverlayContainerWidget: Section widget ({obj_name}) event: {event_type.name}")
                    should_update = True

            if should_update:
                self._schedule_geometry_update()

        return super().eventFilter(obj, event)

    def _schedule_geometry_update(self):
        """Schedule a geometry update with debouncing to prevent flickering."""
        # Don't schedule updates if we're cleaning up
        if self._is_cleaning_up:
            logging.debug("OverlayContainerWidget: Skipping geometry update during cleanup")
            return
            
        # Don't schedule if timer is None (already cleaned up)
        if self._update_timer is None and hasattr(self, '_is_cleaning_up') and self._is_cleaning_up:
            return
            
        # Cancel any pending update
        if self._update_timer:
            try:
                self._update_timer.stop()
            except (RuntimeError, AttributeError):
                # Timer already destroyed
                return

        # Schedule new update after short delay
        if not self._update_timer:
            try:
                self._update_timer = QTimer(self)
                self._update_timer.setSingleShot(True)
                self._update_timer.timeout.connect(self._update_overlay_geometry)
            except (RuntimeError, AttributeError):
                # Widget already destroyed
                return

        # 50ms debounce - accumulates rapid changes
        try:
            self._update_timer.start(50)
        except (RuntimeError, AttributeError):
            # Timer already destroyed
            pass

    def _find_target_widget(self):
        """Find the target widget by name."""
        if not self._target_widget or not self._bar_widget:
            logging.debug("OverlayContainerWidget: _find_target_widget called without target_widget or bar_widget")
            return None

        logging.debug(f"OverlayContainerWidget: Searching for target widget '{self._target_widget}'")

        try:
            config = get_config()
            widgets_config = config.get("widgets", {})

            # Get the target widget's type
            if self._target_widget not in widgets_config:
                logging.warning(f"OverlayContainerWidget: Widget '{self._target_widget}' not found in config")
                return None

            target_config = widgets_config[self._target_widget]
            target_type = target_config.get("type", "")

            logging.debug(f"OverlayContainerWidget: Target widget type: {target_type}")

            # Extract class name from type (e.g., "yasb.media.MediaWidget" -> "MediaWidget")
            target_class_name = target_type.split(".")[-1] if target_type else ""

            if not target_class_name:
                logging.warning(f"OverlayContainerWidget: Could not determine class for '{self._target_widget}'")
                return None

            # Find all widgets of this type in the bar
            matching_widgets = []
            for widget in self._bar_widget.findChildren(BaseWidget):
                logging.debug(f"OverlayContainerWidget: Checking widget: {widget.__class__.__name__}")
                if widget.__class__.__name__ == target_class_name:
                    matching_widgets.append(widget)
                    logging.debug(f"OverlayContainerWidget: Found matching widget: {widget.__class__.__name__}")

            # If only one match, return it
            if len(matching_widgets) == 1:
                logging.info(
                    f"OverlayContainerWidget: Found target widget '{self._target_widget}' ({target_class_name}) at {matching_widgets[0].geometry()}"
                )
                return matching_widgets[0]
            elif len(matching_widgets) > 1:
                logging.warning(
                    f"OverlayContainerWidget: Multiple widgets of type '{target_class_name}' found ({len(matching_widgets)}). "
                    f"Using the first one."
                )
                return matching_widgets[0]
            else:
                logging.warning(f"OverlayContainerWidget: No widget of type '{target_class_name}' found")
                # List all available widgets for debugging
                all_widgets = [w.__class__.__name__ for w in self._bar_widget.findChildren(BaseWidget)]
                logging.debug(f"OverlayContainerWidget: Available widgets: {all_widgets}")
                return None

        except Exception as e:
            logging.error(f"OverlayContainerWidget: Error finding target widget: {e}", exc_info=True)
            return None

    def _update_overlay_geometry(self):
        """Update overlay geometry based on target configuration."""
        if not self._overlay_panel or not self._bar_widget:
            logging.debug("OverlayContainerWidget: _update_overlay_geometry called without overlay_panel or bar_widget")
            return

        # Prevent recursive updates
        if self._is_updating:
            logging.debug("OverlayContainerWidget: Skipping recursive geometry update")
            return

        self._is_updating = True
        try:
            logging.debug(f"OverlayContainerWidget: Updating geometry with target='{self._target}'")

            # Calculate target geometry
            if self._target == "widget" and self._target_widget:
                logging.debug(
                    f"OverlayContainerWidget: Using widget geometry for target_widget='{self._target_widget}'"
                )
                target_rect = self._calculate_widget_geometry()
            elif self._target == "full":
                logging.debug("OverlayContainerWidget: Using full bar geometry")
                target_rect = self._calculate_full_geometry()
            elif self._target in ["left", "center", "right"]:
                logging.debug(f"OverlayContainerWidget: Using section geometry for section='{self._target}'")
                target_rect = self._calculate_section_geometry(self._target)
            else:  # custom
                logging.debug("OverlayContainerWidget: Using custom geometry")
                target_rect = self._calculate_custom_geometry()

            if target_rect is None:
                logging.warning("OverlayContainerWidget: target_rect is None, cannot set geometry")
                return

            logging.debug(f"OverlayContainerWidget: Calculated rect before offset: {target_rect}")

            # Apply offsets
            if self._offset_x != 0 or self._offset_y != 0:
                target_rect.translate(self._offset_x, self._offset_y)
                logging.debug(
                    f"OverlayContainerWidget: Applied offset ({self._offset_x}, {self._offset_y}), new rect: {target_rect}"
                )

            # Set geometry
            self._overlay_panel.setGeometry(target_rect)
            logging.info(f"OverlayContainerWidget: Set overlay geometry to {target_rect}")

            # Set z-order
            self._update_z_order()

        except Exception as e:
            logging.error(f"OverlayContainerWidget: Error updating geometry: {e}", exc_info=True)
        finally:
            self._is_updating = False

    def _calculate_widget_geometry(self) -> QRect:
        """Calculate geometry relative to target widget."""
        if not self._target_widget_ref:
            self._target_widget_ref = self._find_target_widget()
            if not self._target_widget_ref:
                logging.warning("OverlayContainerWidget: Target widget not found, falling back to full geometry")
                return self._calculate_full_geometry()

        # Get global geometry of target widget
        target_global_pos = self._target_widget_ref.mapToGlobal(QPoint(0, 0))
        bar_global_pos = self._bar_widget.mapToGlobal(QPoint(0, 0))

        # Convert to bar-local coordinates
        local_x = target_global_pos.x() - bar_global_pos.x()
        local_y = target_global_pos.y() - bar_global_pos.y()

        width = self._calculate_dimension(self._width, self._target_widget_ref.width())
        height = self._calculate_dimension(self._height, self._target_widget_ref.height())

        return QRect(local_x, local_y, width, height)

    def _calculate_full_geometry(self) -> QRect:
        """Calculate geometry for full bar coverage."""
        bar_rect = self._bar_widget.rect()

        width = self._calculate_dimension(self._width, bar_rect.width())
        height = self._calculate_dimension(self._height, bar_rect.height())

        return QRect(0, 0, width, height)

    def _calculate_section_geometry(self, section: str) -> QRect:
        """Calculate geometry for a specific section."""
        logging.debug(f"OverlayContainerWidget: Calculating geometry for section '{section}'")
        container = self._find_section_container(section)

        if container:
            # Get position relative to bar
            container_pos = container.pos()
            container_size = container.size()

            logging.debug(
                f"OverlayContainerWidget: Section container found at pos={container_pos}, size={container_size}"
            )

            width = self._calculate_dimension(self._width, container.width())
            height = self._calculate_dimension(self._height, container.height())

            rect = QRect(container_pos.x(), container_pos.y(), width, height)
            logging.debug(f"OverlayContainerWidget: Section geometry calculated: {rect}")
            return rect

        # Fallback
        logging.warning(
            f"OverlayContainerWidget: Section container '{section}' not found, falling back to full geometry"
        )
        return self._calculate_full_geometry()

    def _find_section_container(self, section: str):
        """Find the container widget for a specific section."""
        if not self._bar_widget:
            logging.debug("OverlayContainerWidget: _find_section_container called without bar_widget")
            return None

        class_name = f"container-{section}"
        logging.debug(f"OverlayContainerWidget: Searching for section container with class '{class_name}'")

        containers_found = []
        for child in self._bar_widget.findChildren(QFrame):
            child_class = child.property("class")
            if child_class:
                logging.debug(f"OverlayContainerWidget: Found QFrame with class: {child_class}")
                if class_name in child_class:
                    containers_found.append(child)
                    logging.info(
                        f"OverlayContainerWidget: Found section container '{section}' with class '{child_class}'"
                    )
                    return child

        if not containers_found:
            logging.warning(f"OverlayContainerWidget: No section container found for '{section}'")
            # List all containers for debugging
            all_containers = [
                child.property("class") for child in self._bar_widget.findChildren(QFrame) if child.property("class")
            ]
            logging.debug(f"OverlayContainerWidget: Available containers: {all_containers}")

        return None

    def _calculate_custom_geometry(self) -> QRect:
        """Calculate custom geometry."""
        bar_rect = self._bar_widget.rect()

        width = self._width if isinstance(self._width, int) else bar_rect.width()
        height = self._height if isinstance(self._height, int) else bar_rect.height()

        return QRect(0, 0, width, height)

    def _calculate_dimension(self, dimension: str | int, reference: int) -> int:
        """Calculate actual dimension from configuration value."""
        if isinstance(dimension, int):
            return dimension
        elif dimension == "auto":
            return reference
        else:
            return reference

    def _update_z_order(self):
        """Update z-order based on configuration."""
        if not self._overlay_panel:
            return

        # Use raise_() and lower_() to control stacking
        if self._position == "behind" or self._z_index == -1:
            self._overlay_panel.lower()
        elif self._position == "above" or self._z_index == 1:
            self._overlay_panel.raise_()
        # else z_index == 0, leave at default

    def _toggle_overlay(self):
        """Toggle overlay visibility."""
        if self._is_visible:
            self._hide_overlay()
        else:
            self._show_overlay()

        # Update toggle button visual state
        if self._show_toggle and hasattr(self, "_toggle_button"):
            if self._is_visible:
                self._toggle_button.setProperty("class", "toggle-button active")
            else:
                self._toggle_button.setProperty("class", "toggle-button")
            refresh_widget_style(self._toggle_button)

    def _show_overlay(self):
        """Show the overlay panel."""
        logging.debug(f"OverlayContainerWidget._show_overlay: Called, overlay_panel={self._overlay_panel is not None}")

        if not self._overlay_panel:
            logging.warning("OverlayContainerWidget._show_overlay: No overlay panel, returning early")
            return

        self._is_visible = True
        logging.debug("OverlayContainerWidget._show_overlay: Set _is_visible=True")

        self._update_overlay_geometry()
        logging.debug("OverlayContainerWidget._show_overlay: Updated geometry")

        self._overlay_panel.show()
        logging.info(
            f"OverlayContainerWidget._show_overlay: Called show() on overlay_panel, visible={self._overlay_panel.isVisible()}"
        )

        self._update_z_order()
        logging.debug(
            f"OverlayContainerWidget._show_overlay: Updated z-order (position={self._position}, z_index={self._z_index})"
        )

        logging.info("OverlayContainerWidget: Overlay shown successfully")

    def _hide_overlay(self):
        """Hide the overlay panel."""
        if not self._overlay_panel:
            return

        self._is_visible = False
        self._overlay_panel.hide()

        logging.debug("OverlayContainerWidget: Overlay hidden")

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)

        # When widget becomes visible again (e.g., Media Widget re-activated),
        # restore overlay visibility if it was visible before
        if self._overlay_panel and self._is_visible:
            # Schedule overlay show and geometry update
            QTimer.singleShot(0, self._show_overlay_after_widget_show)

    def _show_overlay_after_widget_show(self):
        """Helper to show overlay after widget is shown."""
        if self._overlay_panel and self._is_visible:
            self._overlay_panel.show()
            self._update_overlay_geometry()
            self._update_z_order()

    def hideEvent(self, event):
        """Handle hide event."""
        super().hideEvent(event)

        if self._overlay_panel:
            self._overlay_panel.hide()

    def cleanup(self):
        """Clean up the widget with defensive error handling to prevent crashes."""
        logging.debug("OverlayContainerWidget: Starting cleanup")
        
        # Mark as cleaning up to prevent new operations
        self._is_cleaning_up = True
        
        # Stop update timer first - CRITICAL to prevent callbacks on destroyed objects
        if self._update_timer:
            try:
                self._update_timer.stop()
                self._update_timer.timeout.disconnect()  # Disconnect all slots
                self._update_timer.deleteLater()
            except (RuntimeError, AttributeError) as e:
                # Timer already deleted or disconnected
                logging.debug(f"OverlayContainerWidget: Timer already cleaned: {e}")
            except Exception as e:
                logging.warning(f"OverlayContainerWidget: Error stopping update timer: {e}")
            finally:
                self._update_timer = None
        
        # Remove ALL event filters to prevent ghost events on destroyed objects
        # This is CRITICAL - event filters on destroyed objects cause segfaults
        try:
            if self._bar_widget:
                try:
                    self._bar_widget.removeEventFilter(self)
                    logging.debug("OverlayContainerWidget: Removed bar event filter")
                except (RuntimeError, AttributeError):
                    # Widget already destroyed
                    pass
                except Exception as e:
                    logging.debug(f"OverlayContainerWidget: Error removing bar event filter: {e}")
                    
            if self._target_widget_ref:
                try:
                    self._target_widget_ref.removeEventFilter(self)
                    logging.debug("OverlayContainerWidget: Removed target widget event filter")
                except (RuntimeError, AttributeError):
                    # Widget already destroyed
                    pass
                except Exception as e:
                    logging.debug(f"OverlayContainerWidget: Error removing target widget event filter: {e}")
                    
            # Remove event filters from section widgets
            if self._target in ["left", "center", "right"] and self._bar_widget:
                try:
                    section_container = self._find_section_container(self._target)
                    if section_container:
                        try:
                            section_container.removeEventFilter(self)
                        except (RuntimeError, AttributeError):
                            pass
                            
                        # Remove from all child widgets
                        try:
                            for widget in section_container.findChildren(BaseWidget):
                                try:
                                    widget.removeEventFilter(self)
                                except (RuntimeError, AttributeError):
                                    # Widget already destroyed
                                    pass
                        except (RuntimeError, AttributeError):
                            # Section container already destroyed
                            pass
                except Exception as e:
                    logging.debug(f"OverlayContainerWidget: Error removing section event filters: {e}")
        except Exception as e:
            logging.warning(f"OverlayContainerWidget: Critical error removing event filters: {e}")
        
        # Clean up backgrounds BEFORE overlay panel to prevent OpenGL context errors
        # Order matters: shader/media widgets must be destroyed before their parent
        if self._shader_background:
            try:
                # Hide first to stop rendering
                shader_widget = self._shader_background.get_widget()
                if shader_widget:
                    try:
                        shader_widget.hide()
                        shader_widget.setParent(None)
                    except (RuntimeError, AttributeError):
                        pass
                        
                self._shader_background.cleanup()
                logging.debug("OverlayContainerWidget: Cleaned up shader background")
            except Exception as e:
                logging.warning(f"OverlayContainerWidget: Error cleaning up shader background: {e}", exc_info=True)
            finally:
                self._shader_background = None

        if self._media_background:
            try:
                # Hide first to stop rendering
                media_widget = self._media_background.get_widget()
                if media_widget:
                    try:
                        media_widget.hide()
                        media_widget.setParent(None)
                    except (RuntimeError, AttributeError):
                        pass
                        
                self._media_background.cleanup()
                logging.debug("OverlayContainerWidget: Cleaned up media background")
            except Exception as e:
                logging.warning(f"OverlayContainerWidget: Error cleaning up media background: {e}", exc_info=True)
            finally:
                self._media_background = None

        # Clean up overlay panel last
        if self._overlay_panel:
            try:
                self._overlay_panel.cleanup()
                logging.debug("OverlayContainerWidget: Cleaned up overlay panel")
            except Exception as e:
                logging.warning(f"OverlayContainerWidget: Error cleaning up overlay panel: {e}", exc_info=True)
            finally:
                self._overlay_panel = None

        # Clear all references to prevent dangling pointers
        self._child_widget = None
        self._bar_widget = None
        self._target_widget_ref = None
        
        logging.info("OverlayContainerWidget: Cleanup completed successfully")
