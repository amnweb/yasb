import os
import re
import logging
import threading
import requests
from datetime import datetime
from core.validation.widgets.yasb.github import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from PyQt6.QtGui import QDesktopServices,QCursor
from PyQt6.QtWidgets import QMenu, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QScrollArea, QVBoxLayout, QWidgetAction
from PyQt6.QtCore import Qt, QPoint, QTimer, QUrl
logging.getLogger("urllib3").setLevel(logging.WARNING)

class HoverWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)

    def enterEvent(self, event):
        # Change background color on hover
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0.05)")
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Reset background color when not hovering
        self.setStyleSheet("background-color:transparent")
        super().leaveEvent(event)


class GithubWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, label_alt: str, token: str,max_notification: int, only_unread: bool, max_field_size: int, menu_width: int,menu_height: int,menu_offset: str, update_interval: int):
        super().__init__((update_interval * 1000), class_name="github-widget")
        self._menu_open = False
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._token = token if token != 'env' else os.getenv('YASB_GITHUB_TOKEN')
        self._menu_width = menu_width
        self._menu_height = menu_height
        self._menu_offset = menu_offset
        self._max_notification = max_notification
        self._only_unread = only_unread
        self._max_field_size = max_field_size
        self._github_data = []
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")

        self.widget_layout.addWidget(self._widget_container)
        self._create_dynamically_label(self._label_content, self._label_alt_content)
        
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("get_github_data", self.get_github_data)       
        
        self.callback_timer = "get_github_data" 
        self.start_timer()
        
 
        
    def _toggle_label(self):
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
                    label = ClickableLabel(icon, widget_ref=self)
                    label.setProperty("class", class_result)
                    label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                else:
                    label = ClickableLabel(part, widget_ref=self)
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
 
        

    def mark_as_read(self, notification_id, text_label, icon_label):
        for notification in self._github_data:
            if notification['id'] == notification_id:
                notification['unread'] = False
                break
        self._update_label()
        text_label_stylesheet = text_label.styleSheet()
        icon_label_stylesheet = icon_label.styleSheet()
        if "color:" in text_label_stylesheet:
            updated_stylesheet = re.sub(r"color:\s*#[0-9a-fA-F]+", f"color:#9399b2", text_label_stylesheet)
        text_label.setStyleSheet(updated_stylesheet)

        if "color:" in icon_label_stylesheet:
            updated_stylesheet = re.sub(r"color:\s*#[0-9a-fA-F]+", f"color:#9399b2", icon_label_stylesheet)
        icon_label.setStyleSheet(updated_stylesheet) 
        text_label.repaint()
        icon_label.repaint()
    
    
    def show_menu(self, button):
        if self._menu_open:  # Check if the menu is already open
            self._menu_open = False
            return  # Exit the function if the menu is open
        self._menu_open = True  # Set the menu state to open

        def reset_menu_open():
            self._menu_open = False

        global_position = button.mapToGlobal(QPoint(0, button.height()))
        notifications_count = len(self._github_data)
        notifications_unread_count = len([notification for notification in self._github_data if notification['unread']])

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        header_label = QLabel(f"<span style='font-weight:bold'>GitHub</span> Notifications")
        header_label.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.1);font-size:16px;padding:8px;color:white;background-color:rgba(255,255,255,0.05)")

        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border-radius:8px; }
            QScrollBar:vertical { border: none; background:transparent; width: 6px; margin: 4px 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: rgba(20, 25, 36,0); }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.3); min-height: 20px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.5); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {background: rgba(20, 25, 36,0);}
        """)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align items to the top
        scroll_widget.setStyleSheet("background: transparent")
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll_area.setWidget(scroll_widget)

        if notifications_count > 0:
            _menu_height = self._menu_height
            for notification in self._github_data:
                repo_title = notification['title']
                repo_description = f'{notification["type"]}: {notification["repository"]}'
                if len(notification['title']) > self._max_field_size:
                    repo_title = notification['title'][:self._max_field_size - 3] + '...'
                if len(repo_description) > self._max_field_size:
                    repo_description = repo_description[:self._max_field_size - 3] + '...'

                icon_type = '\uf41b' if notification['type'] == 'Issue' else '\uea64' if notification['type'] == 'PullRequest' else '\uea84'
                
                container = HoverWidget()
                icon_label = QLabel(f"{icon_type}")
                unread_text = '#ffffff' if notification['unread'] else '#9399b2'
                unread_icon = '#3fb950' if notification['unread'] else '#9399b2'
                icon_label.setStyleSheet(f"color:{unread_icon};font-size:16px;padding-right:0;padding-left:8px")
                text_label = QLabel(
                    f"{repo_title}<br/>"
                    f"<span style='font-family:Segoe UI;font-size:12px;font-weight:500'>{repo_description}</span>"
                )
                text_label.setStyleSheet(f"color:{unread_text};font-family:Segoe UI;font-weight:600;padding-left:0px;font-size:14px;padding-right:14px")
                container_layout = QHBoxLayout(container)
                container_layout.addWidget(icon_label)
                container_layout.addWidget(text_label, 1)
                container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(0)
                button = QPushButton()
                button.setStyleSheet("""
                    QPushButton {
                        background: rgba(0,0,0,0);
                        border: none;
                        color: white;
                        text-align:left;
                        font-size:14px;
                        padding:6px 8px;
                        height:40px;
                        border-top:1px solid rgba(255,255,255,0.05)
                    }
                """)
 
                button.clicked.connect(lambda checked, nid=notification['id'], text_label=text_label, icon_label=icon_label, url=notification['url']: (self.mark_as_read(nid, text_label, icon_label), QDesktopServices.openUrl(QUrl(url))))
                layout = QVBoxLayout(button)
                layout.addWidget(container)
                layout.setContentsMargins(0, 0, 0, 0)
                button.setLayout(layout)
                scroll_layout.addWidget(button)
        else:
            large_label = QLabel("\uea84")
            large_label.setStyleSheet("font-size:88px;color:#313244")
            scroll_layout.addWidget(large_label, alignment=Qt.AlignmentFlag.AlignCenter)
            no_data = QLabel("No unread notifications")
            no_data.setStyleSheet("font-size:16px;color:#616172")
            scroll_layout.addWidget(no_data, alignment=Qt.AlignmentFlag.AlignCenter)
            _menu_height = 200

        # Add Footer
        footer_label = QLabel(f"Unread notifications ({notifications_unread_count})")
        footer_label.setStyleSheet("border-top:1px solid rgba(255,255,255,0.1);font-size:12px;padding:4px 8px 6px 8px;color:#9399b2;background-color:rgba(255,255,255,0.05)")
        main_layout.addWidget(header_label)
        main_layout.addWidget(scroll_area)
        if notifications_count > 0:
            main_layout.addWidget(footer_label)

        scroll_area.setFixedSize(self._menu_width, _menu_height)

        scroll_menu = QMenu()
        scroll_menu.setStyleSheet("""
            QMenu { background:rgb(20, 25, 36);border: 1px solid rgba(255,255,255,0.1);border-radius:8px }
        """)
        scroll_action = QWidgetAction(scroll_menu)
        scroll_action.setDefaultWidget(main_widget)
        scroll_menu.addAction(scroll_action)
        m_position = QPoint(global_position.x() - self._menu_offset, global_position.y())
        scroll_menu.exec(m_position)

        # Reset the menu state after the menu is closed
        QTimer.singleShot(0, reset_menu_open)

 
        
    def get_github_data(self):
        threading.Thread(target=self._get_github_data).start()

    def _get_github_data(self):
        self._github_data = self._get_github_notifications(self._token)
        QTimer.singleShot(0, self._update_label)
        
 
    def _get_github_notifications(self, token):
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


class ClickableLabel(QLabel):
    def __init__(self, text, parent=None, widget_ref=None):
        super().__init__(text, parent)
        self.widget_ref = widget_ref
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.widget_ref:
            self.widget_ref.show_menu(self)
        if event.button() == Qt.MouseButton.RightButton:
            self.widget_ref._toggle_label() 