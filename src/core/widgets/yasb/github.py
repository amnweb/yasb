import os
import re
import logging
import threading
import requests
from settings import DEBUG
from datetime import datetime
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.github import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from PyQt6.QtGui import QDesktopServices,QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QScrollArea, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QPoint, QTimer, QUrl
from core.utils.widgets.animation_manager import AnimationManager
logging.getLogger("urllib3").setLevel(logging.WARNING)

class GithubWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            token: str,
            tooltip: bool,
            max_notification: int,
            only_unread: bool,
            max_field_size: int,
            menu: dict[str, str],
            icons: dict[str, str],
            update_interval: int,
            animation: dict[str, str],
            container_padding: dict[str, int]
        ):
        super().__init__((update_interval * 1000), class_name="github-widget")
  
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._token = token if token != 'env' else os.getenv('YASB_GITHUB_TOKEN')
        self._tooltip = tooltip
        self._menu_popup = menu
        self._icons = icons
        self._max_notification = max_notification
        self._only_unread = only_unread
        self._max_field_size = max_field_size
        self._animation = animation
        self._padding = container_padding
        
        self._github_data = []
        
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])

        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")

        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("get_github_data", self.get_github_data) 
        
        callbacks = {
            "on_left": "toggle_menu",
            "on_right": "toggle_label"
        }
        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        
        self.callback_timer = "get_github_data" 
        self.start_timer()
        
 
    def _toggle_menu(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self.show_menu()
                       
    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)    
                self._widget_container_layout.addWidget(label)
                
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets
        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)
        

    def _update_label(self):
        notification_count = len([notification for notification in self._github_data if notification['unread']])
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        # Split label content and filter out empty parts
        label_parts = [part.strip() for part in re.split(r'(<span.*?>.*?</span>)', active_label_content) if part]
        
        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue
            
            current_widget = active_widgets[widget_index]
            icon = ''
            
            if '<span' in part and '</span>' in part:
                icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                current_widget.setText(icon)
                if self._tooltip:
                    current_widget.setToolTip(f'Notifications {notification_count}')
                # Update class based on notification count
                current_classes = current_widget.property("class").split()
                notification_class = "new-notification"
                if notification_count > 0:
                    current_classes.append(notification_class)
                else:
                    current_classes = [cls for cls in current_classes if cls != notification_class]
                current_widget.setProperty("class", " ".join(current_classes))
 
            else:
                formatted_text = part.format(data=notification_count)
                current_widget.setText(formatted_text)
            current_widget.style().unpolish(current_widget)
 
        

    def mark_as_read(self, notification_id, container_label):
        for notification in self._github_data:
            if notification['id'] == notification_id:
                notification['unread'] = False
                break
        self._update_label()
        current_classes = container_label.property("class").split()
        if "new" in current_classes:
            current_classes.remove("new")
        container_label.setProperty("class", " ".join(current_classes))
        container_label.setStyleSheet(container_label.styleSheet())
        container_label.repaint()


    def mark_as_read_notification_on_github(self, notification_id):
        headers = {
            'Authorization': f'token {self._token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/notifications/threads/{notification_id}'
        try:
            response = requests.patch(url, headers=headers)
            response.raise_for_status()
            if DEBUG:
                logging.info(f"Notification {notification_id} marked as read on GitHub.")
        except requests.HTTPError as e:
            logging.error(f"HTTP Error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}, in most cases this error when there is no internet connection.")


    def _handle_mouse_press_event(self, event, notification_id, url, container_label):
        self.mark_as_read(notification_id, container_label)
        self._menu.hide()
        QDesktopServices.openUrl(QUrl(url))
        self.mark_as_read_notification_on_github(notification_id)


    def _create_container_mouse_press_event(self, notification_id, url, container_label):
        def mouse_press_event(event):
            self._handle_mouse_press_event(event, notification_id, url, container_label)
        return mouse_press_event


    def show_menu(self):
        notifications_count = len(self._github_data)
        notifications_unread_count = len([notification for notification in self._github_data if notification['unread']])

        self._menu = PopupWidget(self, self._menu_popup['blur'], self._menu_popup['round_corners'], self._menu_popup['round_corners_type'], self._menu_popup['border_color'])
        self._menu.setProperty('class', 'github-menu')
        self._menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self._menu.setWindowFlag(Qt.WindowType.Popup)
        self._menu.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel(f"<span style='font-weight:bold'>GitHub</span> Notifications")
        header_label.setProperty("class", "header")
        main_layout.addWidget(header_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_area.setViewportMargins(0, 0, -4, 0)  # overlay the scrollbar 6px to the left
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        main_layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_widget.setProperty("class", "contents")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll_area.setWidget(scroll_widget)

        if notifications_count > 0:
            for notification in self._github_data:
                repo_title = notification['title']
                repo_description = f'{notification["type"]}: {notification["repository"]}'
                repo_title = (notification['title'][:self._max_field_size - 3] + '...') if len(notification['title']) > self._max_field_size else notification['title']
                repo_description = (repo_description[:self._max_field_size - 3] + '...') if len(repo_description) > self._max_field_size else repo_description

                icon_type = {
                    'Issue': self._icons['issue'],
                    'PullRequest': self._icons['pull_request'],
                    'Release': self._icons['release'],
                    'Discussion': self._icons['discussion']
                }.get(notification['type'], self._icons['default'])

                new_item_class = 'new' if notification['unread'] else ""
                  
                container = QWidget()
                container.setProperty("class", f"item {new_item_class}")
                container.setContentsMargins(0, 0, 8, 0)
                container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                
                icon_label = QLabel(f"{icon_type}")
                icon_label.setProperty("class", "icon")
                
                title_label = QLabel(repo_title)   
                title_label.setProperty("class", "title")
                
                description_label = QLabel(repo_description)              
                description_label.setProperty("class", "description")
                
                text_content = QWidget()
                text_content_layout = QVBoxLayout(text_content)
                text_content_layout.addWidget(title_label)
                text_content_layout.addWidget(description_label)
                text_content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                text_content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                text_content_layout.setContentsMargins(0, 0, 0, 0)
                text_content_layout.setSpacing(0)
                
                container_layout = QHBoxLayout(container)
                container_layout.addWidget(icon_label)
                container_layout.addWidget(text_content, 1)
                container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(0)
                scroll_layout.addWidget(container)

                container.mousePressEvent = self._create_container_mouse_press_event(notification['id'], notification['url'], container)
                #container.mousePressEvent = self._create_container_mouse_press_event(notification['id'], notification['url'])
        else:
            large_label = QLabel(self._icons['github_logo'])
            large_label.setStyleSheet("font-size:88px;font-weight:400")
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.4)
            large_label.setGraphicsEffect(opacity_effect)

            no_data = QLabel("No unread notifications")
            no_data.setStyleSheet("font-size:18px;font-weight:400;font-family: Segoe UI")
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.5)
            no_data.setGraphicsEffect(opacity_effect)

            # Create a vertical layout to center the widgets
            center_layout = QVBoxLayout()
            center_layout.addStretch()
            center_layout.addWidget(large_label, alignment=Qt.AlignmentFlag.AlignCenter)
            center_layout.addWidget(no_data, alignment=Qt.AlignmentFlag.AlignCenter)
            center_layout.addStretch()

            # Add the center layout to the scroll layout
            scroll_layout.addLayout(center_layout)
        if notifications_count > 0:
            footer_label = QLabel(f"Unread notifications ({notifications_unread_count})")
            footer_label.setProperty("class", "footer")
            main_layout.addWidget(footer_label)

        self._menu.adjustSize()
        widget_global_pos = self.mapToGlobal(QPoint(0, self.height() + self._menu_popup['distance']))

        if self._menu_popup['direction'] == 'up':
            global_y = self.mapToGlobal(QPoint(0, 0)).y() - self._menu.height() - self._menu_popup['distance']
            widget_global_pos = QPoint(self.mapToGlobal(QPoint(0, 0)).x(), global_y)

        if self._menu_popup['alignment'] == 'left':
            global_position = widget_global_pos
        elif self._menu_popup['alignment'] == 'right':
            global_position = QPoint(
                widget_global_pos.x() + self.width() - self._menu.width(),
                widget_global_pos.y()
            )
        elif self._menu_popup['alignment'] == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (self.width() - self._menu.width()) // 2,
                widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos

        self._menu.move(global_position)
        self._menu.show()

        
    def get_github_data(self):
        threading.Thread(target=self._get_github_data).start()

    def _get_github_data(self):
        self._github_data = self._get_github_notifications(self._token)
        QTimer.singleShot(0, self._update_label)
        
 
    def _get_github_notifications(self, token):
        if DEBUG:
            logging.info(f"Check for GitHub notifications at {datetime.now()}")
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        params = {
            'all': 'false' if self._only_unread else 'true',
            'participating': 'false',
            'per_page': self._max_notification
        }

        try:
            response = requests.get('https://api.github.com/notifications', headers=headers, params=params)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            notifications = response.json()
            result = []
            if notifications:
                for notification in notifications:
                    repo_full_name = notification['repository']['full_name']
                    subject_type = notification['subject']['type']
                    subject_url = notification['subject']['url']
                    unread = notification['unread']

                    if subject_type == 'Issue':
                        github_url = subject_url.replace('api.github.com/repos', 'github.com')
                    elif subject_type == 'PullRequest':
                        github_url = subject_url.replace('api.github.com/repos', 'github.com').replace('/pulls/', '/pull/')
                    elif subject_type == 'Release':
                        github_url = f'https://github.com/{repo_full_name}/releases'
                    elif subject_type == 'Discussion':
                        github_url = subject_url.replace('api.github.com/repos', 'github.com')
                    else:
                        github_url = notification['repository']['html_url']
                    
                    result.append({
                        'id': notification['id'],
                        'repository': repo_full_name,
                        'title': notification['subject']['title'],
                        'type': subject_type,
                        'url': github_url,
                        'unread': unread
                    })
                return result
            else:
                return []

        except requests.ConnectionError:
            logging.error("No internet connection. Unable to fetch notifications.")
            return []  # Return an empty list or handle as needed
        except requests.HTTPError as e:
            logging.error(f"HTTP Error occurred: {e.response.status_code} - {e.response.text}")
            return []  # Handle other HTTP errors as needed
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            return []  # Handle any other exceptions