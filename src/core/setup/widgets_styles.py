"""
Widget styles for the YASB setup wizard.
"""

BASE_WIDGET_STYLE: str = """\
/* Home Menu */
.home-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.home-menu {
    background-color: var(--yasb-popup-bg);
}
.home-menu .menu-item {
    color: var(--yasb-fg);
    padding: 8px 48px 8px 16px;
    font-family: var(--system-font);
    font-weight: 600;
}
.home-menu .menu-item:hover {
    background-color: rgba(128, 130, 158, 0.15);
    color: #fff;
}
.home-menu .separator {
    max-height: 1px;
    background-color: rgba(128, 130, 158, 0.3);
}

/* Clock */
.clock-widget .icon.alarm {
    color: var(--yasb-accent);
    padding-left: 4px;
}
.clock-popup.alarm,
.clock-popup.timer,
.clock-popup.calendar {
    min-width: 460px;
    background-color: var(--yasb-popup-bg);
}
.clock-popup.calendar .calendar-table,
.clock-popup.calendar .calendar-table::item {
    background-color: rgba(17, 17, 27, 0);
    color: rgba(162, 177, 196, 0.85);
    font-family: var(--system-font);
    margin: 0;
    padding: 0;
    border: none;
    outline: none;
}
.clock-popup.calendar .calendar-table::item:selected {
    color: #000000;
    font-weight: bold;
    background-color: var(--yasb-accent);
    border-radius: 12px;
}
.clock-popup.calendar .day-label {
    margin-top: 20px;
}
.clock-popup.calendar .day-label,
.clock-popup.calendar .month-label,
.clock-popup.calendar .year-label,
.clock-popup.calendar .date-label {
    font-family: var(--system-font);
    font-size: 16px;
    font-weight: 700;
    min-width: 180px;
    max-width: 180px;
}
.clock-popup.calendar .month-label {
    font-weight: normal;
}
.clock-popup.calendar .year-label {
    font-weight: normal;
}
.clock-popup.calendar .date-label {
    font-size: 88px;
    font-weight: 900;
    margin-top: -20px;
}
.clock-popup.timer .clock-popup-container,
.clock-popup.alarm .clock-popup-container {
    padding: 16px;
    background-color: var(--yasb-dialog-bg);
}
.clock-popup.timer .clock-popup-footer,
.clock-popup.alarm .clock-popup-footer {
    padding: 16px;
    background-color: var(--yasb-dialog-surface)
}
.clock-popup .clock-label-timer {
    font-size: 13px;
    font-family: var(--system-font);
    font-weight: 600;
}
.clock-popup .clock-input-time {
    font-size: 48px;
    background-color: transparent;
    border: none;
    font-family: var(--system-font);
    font-weight: 600;
}
.clock-popup .clock-input-time.colon {
    padding-bottom: 8px;
}
.clock-popup .button {
    border-radius: 4px;
    font-family: var(--system-font);
    font-weight: 600;
    font-size: 13px;
    min-height: 28px;
    min-width: 64px;
    margin: 4px 0;
    background-color: var(--yasb-white-alpha-10);
}
.clock-popup .button.save,
.clock-popup .button.start,
.clock-popup .button.delete,
.clock-popup .button.cancel {
    min-width: 120px;
}
.clock-popup .button.save,
.clock-popup .button.start {
    background-color: var(--yasb-accent);
    color: var(--yasb-accent-fg);
    margin-right: 8px;
}
.clock-popup .button.save:hover,
.clock-popup .button.start:hover {
    background-color: var(--yasb-accent-hover)
}
.clock-popup .button.is-alarm-enabled {
    background-color: var(--yasb-accent);
    color: var(--yasb-accent-fg);
}
.clock-popup .button.is-alarm-enabled:hover {
    background-color: var(--yasb-accent-hover);
}
.clock-popup .button.is-alarm-disabled {
    background-color: var(--yasb-white-alpha-20);
}
.clock-popup .button.day {
    background-color: var(--yasb-white-alpha-10);
    max-height: 20px;
    min-height: 20px;
}
.clock-popup .button.day:checked {
    background-color: var(--yasb-accent);
    color: var(--yasb-accent-fg);
}
.clock-popup .button.quick-option {
    background-color: var(--yasb-white-alpha-10);
}
.clock-popup .button.quick-option:checked {
    background-color: var(--yasb-accent);
    color: var(--yasb-accent-fg);
}
.clock-popup .button:hover {
    background-color: var(--yasb-white-alpha-15);
}
.clock-popup .button:disabled {
    background-color: rgba(100, 100, 100, 0.2);
    color: rgba(150, 150, 150, 0.7);
}
.clock-popup .alarm-input-title {
    font-size: 14px;
    font-family: var(--system-font);
    font-weight: 600;
    color: #d2d6e2;
    background-color: var(--yasb-white-alpha-10);
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    margin-top: 8px;
    outline: none;
    min-width: 300px;
}
.clock-popup .alarm-input-title:focus {
    border: 1px solid var(--yasb-accent);
}
.active-alarm-window {
    background-color: var(--yasb-popup-bg);
    max-width: 500px;
    min-width: 500px;
    padding: 32px;
}
.active-alarm-window .alarm-title-icon {
    font-size: 88px;
    color: #ffffff;
    margin-bottom: 16px;
}
.active-alarm-window .alarm-title {
    font-size: 24px;
    font-family: var(--system-font);
    font-weight: 600;
    color: #ffffff;
    max-width: 500px;
    min-width: 500px;
}
.active-alarm-window .alarm-info {
    font-size: 16px;
    font-family: var(--system-font);
    font-weight: 600;
    color: #b2b6c0;
    margin-bottom: 32px;
}
.active-alarm-window .button {
    border-radius: 4px;
    font-family: var(--system-font);
    font-weight: 600;
    font-size: 13px;
    min-height: 36px;
    min-width: 100px;
    margin: 0 4px;
    background-color: var(--yasb-white-alpha-06);
}
.active-alarm-window .button:hover {
    background-color: var(--yasb-white-alpha-10);
}

/* Power Menu */
.power-menu-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.power-menu-compact {
    min-width: 260px;
    background-color: var(--yasb-popup-bg);
}
.power-menu-compact .profile-info {
    padding: 24px 0 24px 0;
}
.power-menu-compact .profile-info .profile-username {
    font-size: 16px;
    font-weight: 600;
    color: var(--yasb-fg);
    font-family: var(--system-font);
    margin-top: 4px;
}
.power-menu-compact .profile-info .profile-account-type {
    font-size: 12px;
    color: var(--yasb-accent-fg);
    font-weight: 600;
    margin-top: 8px;
    font-family: var(--system-font);
    background-color: var(--yasb-accent);
    padding: 2px 6px 3px 6px;
    border-radius: 4px;
}
.power-menu-compact .profile-info .profile-email {
    font-size: 12px;
    color: var(--yasb-fg-muted);
    margin-top: 2px;
    font-family: var(--system-font);
}
.power-menu-compact .manage-accounts {
    font-size: 12px;
    background-color: var(--yasb-white-alpha-08);
    font-family: var(--system-font);
    font-weight: 600;
    padding: 3px 12px 4px 12px;
    color: var(--yasb-fg);
    margin-top: 16px;
    border-radius: 4px;
    border: 1px solid var(--yasb-white-alpha-10);
}
.power-menu-compact .manage-accounts:hover {
    background-color: var(--yasb-white-alpha-15);
}
.power-menu-compact .buttons {
    margin: 0 12px 12px 12px;
    border-radius: 8px;
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--yasb-white-alpha-10);
}
.power-menu-compact .button {
    padding: 8px 16px;
    background-color: transparent;
    border: none;
    border-radius: 0;
}
.power-menu-compact .button.hover {
    background-color: var(--yasb-white-alpha-03);
}
.power-menu-compact .button.lock.hover {
    border-top-right-radius: 8px;
    border-top-left-radius: 8px;
}
.power-menu-compact .button.shutdown.hover {
    border-bottom-right-radius: 8px;
    border-bottom-left-radius: 8px;
}
.power-menu-compact .button .icon {
    font-size: 16px;
    font-weight: 400;
    color: var(--yasb-fg-muted);
    padding-right: 10px;
    min-width: 20px;
}
.power-menu-compact .button .label {
    font-size: 13px;
    font-weight: 500;
    font-family: var(--system-font);
    color: var(--yasb-fg-muted);
}
.power-menu-compact .icon.hover,
.power-menu-compact .label.hover {
    color: var(--yasb-fg);
}

/* Volume */
.volume-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.audio-menu {
    background-color: var(--yasb-popup-bg);
    min-width: 300px;
}
.audio-menu .system-volume-container .volume-slider {
    border: none;
}
.audio-menu .audio-container .device {
    background-color: transparent;
    border: none;
    padding: 6px 8px 6px 4px;
    margin: 2px 0;
    font-size: 12px;
    border-radius: 4px;
}
.audio-menu .audio-container .device.selected {
    background-color: var(--yasb-white-alpha-08);
}
.audio-menu .audio-container .device:hover {
    background-color: var(--yasb-white-alpha-06);
}
.audio-menu .toggle-apps {
    background-color: transparent;
    border: none;
    padding: 0;
    margin: 0;
    min-height: 24px;
    min-width: 24px;
    border-radius: 4px;
    font-family: var(--icons-font);
}
.audio-menu .toggle-apps.expanded {
    background-color: var(--yasb-white-alpha-10);
}
.audio-menu .toggle-apps:hover {
    background-color: var(--yasb-white-alpha-15);
}
.audio-menu .apps-container {
    padding: 8px;
    margin-top: 20px;
    border-radius: 8px;
    background-color: var(--yasb-white-alpha-06);
}
.audio-menu .apps-container .app-volume .app-icon-container {
    min-width: 40px;
    min-height: 40px;
    max-width: 40px;
    max-height: 40px;
    border-radius: 6px;
    margin-right: 8px;
}
.audio-menu .apps-container .app-volume .app-icon-container:hover {
    background-color: var(--yasb-white-alpha-10);
}"""

KOMOREBI_WIDGET_STYLE: str = """\
/* Komorebi Workspace */
.komorebi-workspaces .ws-btn {
    color: var(--yasb-fg);
    border: none;
    margin: 0 2px;
    padding: 2px 8px;
    outline: none;
    font-family: var(--system-font);
    font-weight: 600;
    border-radius: 3px;
}
.komorebi-workspaces .ws-btn.populated {
    background-color: var(--yasb-surface-alt);
}
.komorebi-workspaces .ws-btn.active {
    color: var(--yasb-accent-fg);
    background-color: var(--yasb-accent);
}"""

GLAZEWM_WIDGET_STYLE: str = """\
/* Glaze Workspace */
.glazewm-workspaces .ws-btn {
    color: var(--yasb-fg);
    border: none;
    margin: 0 2px;
    padding: 2px 8px;
    outline: none;
    font-family: var(--system-font);
    font-weight: 600;
    border-radius: 3px;
}
.glazewm-workspaces .ws-btn.active_populated {
    color: var(--yasb-accent-fg);
    background-color: var(--yasb-accent);
}
.glazewm-workspaces .ws-btn.populated {
    background-color: var(--yasb-surface-alt);
}"""

WINDOWS_DESKTOPS_WIDGET_STYLE: str = """\
/* Windows desktops */
.windows-desktops .ws-btn {
    color: var(--yasb-fg);
    border: none;
    margin: 0px 2px;
    padding: 2px 8px;
    outline: none;
    font-family: var(--system-font);
    font-weight: 600;
    border-radius: 3px;
}
.windows-desktops .ws-btn.active {
    color: var(--yasb-accent-fg);
    background-color: var(--yasb-accent);
}
.windows-desktops-popup.rename {
    min-width: 320px;
    background-color: var(--yasb-dialog-bg);
}
.windows-desktops-popup.rename .windows-desktops-popup-container {
    padding: 16px;
}
.windows-desktops-popup.rename .windows-desktops-popup-footer {
    padding: 16px;
    background-color:var(--yasb-dialog-surface)
}
.windows-desktops-popup .popup-title {
    font-size: 16px;
    font-family: var(--system-font);
    font-weight: 600;
    color: var(--yasb-fg);
    margin-bottom: 4px;
}
.windows-desktops-popup .popup-description {
    font-size: 13px;
    font-family: var(--system-font);
    font-weight: 400;
    color: var(--yasb-fg);
    margin-bottom: 12px;
}
.windows-desktops-popup .rename-input {
    font-size: 14px;
    font-family: var(--system-font);
    font-weight: 600;
    color: var(--yasb-fg);
    background-color: var(--yasb-white-alpha-10);
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    outline: none;
    min-width: 280px;
}
.windows-desktops-popup .rename-input:focus {
    border: 1px solid var(--yasb-accent);
}
.windows-desktops-popup .button {
    border-radius: 4px;
    font-family: var(--system-font);
    font-size: 13px;
    min-height: 28px;
    min-width: 120px;
    margin: 4px 0;
    background-color: var(--yasb-dialog-bg);
}
.windows-desktops-popup .button.save {
    margin-right: 8px;
}
.windows-desktops-popup .button:hover {
    background-color: var(--yasb-white-alpha-15);
}"""

CPU_WIDGET_STYLE: str = """\
/* CPU */
.cpu-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.cpu-widget .icon {
    padding-right: 4px;
}
.cpu-popup {
    background-color: var(--yasb-popup-bg);
    min-width: 400px;
    max-width: 400px;
}
.cpu-popup .header {
    background: transparent;
    padding: 12px 16px;
}
.cpu-popup .header .text {
    font-size: 16px;
    font-family: var(--system-font);
}
.cpu-popup .header .pin-btn {
    font-size: 14px;
    background: transparent;
    font-family: 'Segoe Fluent Icons';
    border: none;
    padding: 6px;
    color: var(--yasb-fg-muted);
}
.cpu-popup .header .pin-btn:hover {
    color: var(--yasb-fg-muted);
}
.cpu-popup .header .pin-btn.pinned {
    color: var(--yasb-fg-muted);
}
.cpu-popup .graph-container {
    background: transparent;
    min-height: 64px;
}
.cpu-popup .cpu-graph {
    color: #0f6bff;
}
.cpu-popup .cpu-graph-grid {
    color: var(--yasb-white-alpha-05);
}
.cpu-popup .graph-title {
    font-size: 12px;
    color: var(--yasb-fg-muted);
    font-family: var(--system-font);
    padding: 0px 0px 4px 14px;
}
.cpu-popup .stats {
    background: transparent;
    padding: 16px;
}
.cpu-popup .stats .stat-item {
    background-color: var(--yasb-white-alpha-03);
    border: 1px solid var(--yasb-white-alpha-04);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px;
}
.cpu-popup .stats .stat-label {
    font-size: 13px;
    color: var(--yasb-fg-muted);
    font-family: var(--system-font);
    font-weight: 400;
    padding: 6px 4px 2px 4px;
}
.cpu-popup .stats .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--yasb-fg);
    font-family: var(--system-font);
    padding: 0 4px 12px 4px;
}"""

MEMORY_WIDGET_STYLE: str = """\
/* Memory */
.memory-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.memory-widget .icon {
    padding-right: 4px;
}
.memory-popup {
    background-color: var(--yasb-popup-bg);
    min-width: 400px;
    max-width: 400px;
}
.memory-popup .header {
    background: transparent;
    padding: 12px 16px;
}
.memory-popup .header .text {
    font-size: 16px;
    font-family: var(--system-font);
}
.memory-popup .header .pin-btn {
    font-size: 14px;
    background: transparent;
    font-family: 'Segoe Fluent Icons';
    border: none;
    padding: 6px;
    color: var(--yasb-fg-muted);
}
.memory-popup .header .pin-btn:hover {
    color: var(--yasb-fg-muted);
}
.memory-popup .header .pin-btn.pinned {
    color: var(--yasb-fg-muted);
}
.memory-popup .graph-container {
    background: transparent;
    min-height: 64px;
}
.memory-popup .memory-graph {
    color: #0f6bff;
}
.memory-popup .memory-graph-grid {
    color: var(--yasb-white-alpha-05);
}
.memory-popup .graph-title {
    font-size: 12px;
    color: var(--yasb-fg-muted);
    font-family: var(--system-font);
    padding: 0px 0px 4px 14px;
}
.memory-popup .stats {
    background: transparent;
    padding: 16px;
}
.memory-popup .stats .stat-item {
    background-color: var(--yasb-white-alpha-03);
    border: 1px solid var(--yasb-white-alpha-04);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px;
}
.memory-popup .stats .stat-label {
    font-size: 13px;
    color: var(--yasb-fg-muted);
    font-family: var(--system-font);
    font-weight: 400;
    padding: 6px 4px 2px 4px;
}
.memory-popup .stats .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--yasb-fg);
    font-family: var(--system-font);
    padding: 0 4px 12px 4px;
}"""

QUICK_LAUNCH_WIDGET_STYLE: str = """\
/* Quick Launch */
.quick-launch-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.quick-launch-popup .container {
    background-color: var(--yasb-popup-bg);
}
.quick-launch-popup .search {
    padding: 12px 16px;
    background-color: transparent;
    border-bottom: 1px solid var(--yasb-white-alpha-15);
}
.quick-launch-popup .search .loader-line {
    color: #449bff;
}
.quick-launch-popup .search .search-icon {
    font-family: 'Segoe Fluent Icons';
    font-size: 18px;
    color: var(--yasb-fg);
    padding-right: 8px;
    min-width: 18px;
}
.quick-launch-popup .search .search-submit-icon {
    font-family: 'Segoe Fluent Icons';
    font-size: 18px;
    color: var(--yasb-fg);
    min-width: 18px;
}
.quick-launch-popup .search .search-input {
    background: transparent;
    border: none;
    color: var(--yasb-fg);
    font-size: 16px;
    font-family: var(--system-font);
    font-weight: 400;
    padding: 4px 0;
}
.quick-launch-popup .search .prefix {
    background: #2167d8;
    border-radius: 6px;
    color: #ffffff;
    padding: -2px 8px 0px 8px;
    margin-top: 2px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 600;
    font-family: var(--system-font);
    max-height: 28px;
}
.quick-launch-popup .results {
    background: transparent;
    padding: 8px;
}
.quick-launch-popup .results-list-view {
    font-size: 14px;
    font-family: var(--system-font);
    font-weight: 600;
    color: var(--yasb-fg);
}
.quick-launch-popup .results-list-view .description {
    color: var(--yasb-fg-muted);
    font-size: 11px;
    font-family: var(--system-font);
    font-weight: 600;
}
.quick-launch-popup .results-list-view .separator {
    color: var(--yasb-fg-muted);
    font-size: 13px;
    font-family: var(--system-font);
    font-weight: 600;
    padding: 4px 0 4px 12px;
}
.quick-launch-popup .results-list-view::item {
    padding: 4px 12px;
    border-radius: 8px;
}
.quick-launch-popup .results-list-view::item:hover,
.quick-launch-popup .results-list-view::item:selected {
    background-color: rgba(128, 130, 158, 0.1);
}
.quick-launch-popup .results-empty-text {
    font-size: 24px;
    font-family: var(--system-font);
    color: rgb(255, 255, 255);
    padding-top: 8px;
}
.quick-launch-popup .preview {
    background: rgba(0, 0, 0, 0);
    border-left: 1px solid var(--yasb-white-alpha-06);
}
.quick-launch-popup .preview .preview-text {
    font-size: 13px;
    color: var(--yasb-white-alpha-85);
    padding: 8px 12px;
    font-family: var(--system-font);
    background-color: var(--yasb-white-alpha-03);
    border: none;
}
.quick-launch-popup .preview .preview-image {
    background-color: var(--yasb-white-alpha-03);
    padding: 8px 12px;
}
.quick-launch-popup .preview .preview-meta {
    padding: 6px 12px;
    border-top: 1px solid var(--yasb-white-alpha-06);
    font-family: var(--system-font);
}
.quick-launch-popup .preview .preview-meta .preview-title {
    font-size: 14px;
    font-weight: 600;
    color: rgb(255, 255, 255);
    font-family: var(--system-font);
    margin-bottom: 10px;
    margin-left: -2px;
}
.quick-launch-popup .preview .preview-meta .preview-subtitle {
    font-size: 12px;
    color: var(--yasb-white-alpha-80);
    font-family: var(--system-font);
    padding-bottom: 1px;
}
.quick-launch-popup .preview.edit .preview-title {
    font-size: 13px;
    font-family: var(--system-font);
    font-weight: 600;
    color: #ffffff;
    padding: 8px 12px 4px 12px;
}
.quick-launch-popup .preview.edit .preview-line-edit {
    background: var(--yasb-white-alpha-06);
    border: 1px solid var(--yasb-white-alpha-10);
    border-radius: 4px;
    color: #ffffff;
    font-size: 13px;
    font-family: var(--system-font);
    padding: 6px 8px;
    margin: 0 12px;
}
.quick-launch-popup .preview.edit .preview-line-edit:focus {
    border-color: var(--yasb-white-alpha-30);
}
.quick-launch-popup .preview.edit .preview-text-edit {
    background: var(--yasb-white-alpha-06);
    border: 1px solid var(--yasb-white-alpha-10);
    border-radius: 4px;
    color: #ffffff;
    font-size: 13px;
    font-family: var(--system-font);
    padding: 6px 8px;
    margin: 0 12px;
}
.quick-launch-popup .preview.edit .preview-text-edit:focus {
    border-color: var(--yasb-white-alpha-30);
}
.quick-launch-popup .preview.edit .preview-actions {
    padding: 8px 12px;
}
.quick-launch-popup .preview.edit .preview-btn {
    background: rgb(45, 46, 48);
    border: none;
    border-radius: 4px;
    color: var(--yasb-white-alpha-80);
    font-size: 12px;
    font-family: var(--system-font);
    font-weight: 600;
    padding: 4px 16px;
}
.quick-launch-popup .preview.edit .preview-btn:hover {
    background: rgb(59, 60, 63);
}
.quick-launch-popup .preview.edit .preview-btn.save {
    background: rgb(12, 81, 190);
    color: #ffffff;
}
.quick-launch-popup .preview.edit .preview-btn.save:hover {
    background: rgb(19, 90, 204);
}"""

ACTIVE_WINDOW_WIDGET_STYLE: str = """\
/* Active Windows Title */
.active-window-widget .icon {
    padding-right: 4px;
    padding-bottom: 0;
}"""

SYSTRAY_WIDGET_STYLE: str = """\
/* System Tray */
.systray {
    padding-right: 2px;
}
.systray:hover {
    background-color: var(--yasb-white-alpha-08);
}
.systray .button {
    border-radius: 4px;
    padding: 2px;
    background: transparent;
    border: none;
    outline: none;
}
.systray .button:hover {
    background: var(--yasb-white-alpha-20);
}
.systray .button.drag-over {
    background: var(--yasb-white-alpha-40);
}
.systray .pinned-container.drop-target {
    background: var(--yasb-white-alpha-10);
}
.systray .unpinned-visibility-btn {
    border-radius: 4px;
    height: 20px;
    width: 16px;
    border: none;
    outline: none;
    padding-right: 0;
    font-family: var(--icons-font);
}
.systray .unpinned-visibility-btn:checked {
    background: transparent;
}
.systray-popup .button.drag-over {
    background-color: var(--yasb-white-alpha-20);
}
.systray .pinned-container.pinned-container.drop-target {
    background-color: var(--yasb-white-alpha-10);
}
.systray-popup {
    background-color: var(--yasb-popup-bg);
    padding: 4px;
}
.systray-popup .button {
    padding: 10px;
    margin: 0;
    border: 0;
    border-radius: 6px;
}
.systray-popup .button:hover {
    background-color: var(--yasb-white-alpha-05);
}"""

WEATHER_WIDGET_STYLE: str = """\
/* Open Meteo */
.open-meteo-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.open-meteo-widget .icon {
    color: #F6E3B4;
    padding-right: 4px;
}
.open-meteo-card {
    background-color: var(--yasb-popup-bg);
    min-width: 500px;
}
.open-meteo-card-today .label {
    font-size: 13px;
    font-family: var(--system-font);
    font-weight: 400;
    color: var(--yasb-fg-muted);
}
.open-meteo-card-today .label.location {
    font-size: 32px;
    font-weight: 700;
    font-family: var(--system-font);
    color: var(--yasb-fg);
}
.open-meteo-card-today .label.sunrisesunset {
    font-size: 18px;
    font-family: var(--system-font);
    font-weight: 600;
    color: rgb(201, 204, 159);
}
.open-meteo-card-today .label.sunrisesunset-icon {
    font-size: 16px;
    color: rgb(201, 204, 159);
    font-family: 'Segoe Fluent Icons';
    font-weight: 600;
}
.open-meteo-card-day {
    border: 1px solid var(--yasb-white-alpha-10);
    border-radius: 8px;
    background-color: rgba(0, 0, 0, 0);
    padding: 4px;
    min-width: 70px;
}
.open-meteo-card-day .day-name {
    font-family: var(--system-font);
    color: var(--yasb-fg-muted);
    font-size: 12px;
    font-weight: 600;
}
.open-meteo-card-day .day-temp-max {
    font-family: var(--system-font);
    font-weight: 700;
    font-size: 16px;
    color: var(--yasb-fg);
}
.open-meteo-card-day .day-temp-min {
    font-family: var(--system-font);
    color: var(--yasb-fg);
    font-weight: 400;
    font-size: 13px;
}
.open-meteo-card-day.active {
    background-color: var(--yasb-white-alpha-05);
    border: 1px solid var(--yasb-white-alpha-08);
}
.open-meteo-card-day:hover {
    background-color: var(--yasb-white-alpha-05);
    border: 1px solid var(--yasb-white-alpha-08);
}
.open-meteo-card .hourly-container {
    border: none;
    background-color: transparent;
    min-height: 120px;
}
.open-meteo-card .hourly-data {
    font-size: 11px;
    font-weight: 700;
    font-family: var(--system-font);
}
.open-meteo-card .hourly-data.temperature {
    background-color: #c9be48;
}
.open-meteo-card .hourly-data.rain {
    background-color: #4a90e2;
}
.open-meteo-card .hourly-data.snow {
    background-color: #a0c4ff;
}
.open-meteo-card .hourly-data .hourly-rain-animation {
    color: rgba(150, 200, 25, 1);
    background-color: rgba(0, 0, 0, 0);
}
.open-meteo-card .hourly-data .hourly-snow-animation {
    color: rgba(255, 255, 255, 0.5);
    background-color: rgba(0, 0, 0, 0);
}
.open-meteo-card .hourly-data-buttons {
    margin-top: 11px;
    margin-left: 11px;
}
.open-meteo-card .hourly-data-button {
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
    max-width: 24px;
    max-height: 24px;
    font-size: 14px;
    color: var(--yasb-white-alpha-30);
    border: 1px solid transparent;
}
.open-meteo-card .hourly-data-button.active {
    color: #fff;
    background-color: var(--yasb-white-alpha-10);
    border: 1px solid var(--yasb-white-alpha-10);
}
.open-meteo-card .search-head {
    font-size: 18px;
    font-family: var(--system-font);
    font-weight: 600;
    color: var(--yasb-fg);
}
.open-meteo-card .search-description {
    font-size: 14px;
    font-family: var(--system-font);
    font-weight: 400;
    color: var(--yasb-white-alpha-70);
    padding-bottom: 8px;
}
.open-meteo-card .no-data-icon {
    font-size: 88px;
}
.open-meteo-card .no-data-text {
    font-size: 16px;
    font-family: var(--system-font);
    font-weight: 400;
}
.open-meteo-card .search-input {
    padding: 8px 12px;
    border: 1px solid #5e6070;
    border-radius: 6px;
    background-color: rgba(17, 17, 27, 0.1);
    color: #cdd6f4;
    font-family: var(--system-font);
    font-size: 14px;
}
.open-meteo-card .search-input:focus {
    border: 1px solid #89b4fa;
    background-color: rgba(17, 17, 27, 0.2);
}
.open-meteo-card .search-results {
    border: 1px solid #45475a00;
    border-radius: 6px;
    background-color: rgba(0, 0, 0, 0);
    color: #cbced8;
    font-size: 13px;
    font-family: var(--system-font);
}
.open-meteo-card .search-results::item {
    padding: 6px;
}
.open-meteo-card .search-results::item:hover {
    background-color: var(--yasb-white-alpha-05);
}"""

GITHUB_WIDGET_STYLE: str = """\
/* GitHub */
.github-widget .icon {
    font-family: var(--icons-font-fallback);
}
.github-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.github-menu {
    background-color: var(--yasb-popup-bg);
    height: 700px;
    min-height: 0;
    min-width: 500px;
}
.github-menu .header {
    font-size: 18px;
    font-weight: 400;
    font-family: var(--system-font);
    padding: 12px 0 8px 12px;
    color: white;
}
.github-menu .footer {
    font-size: 12px;
    padding: 8px 8px 8px 8px;
}
.github-menu .footer .label {
    color: #9399b2;
    font-family: var(--system-font);
}
.github-menu .footer .label:hover {
    color: #b5b9c7;
}
.github-menu .contents {
    background-color: transparent;
}
.github-menu .contents .section-header {
    font-family: var(--system-font);
    font-size: 16px;
    margin: 16px 16px 8px 16px;
    color: #dbe0f1;
}
.github-menu .contents .section {
    margin: 0 12px 0 12px;
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--yasb-white-alpha-10);
    border-radius: 14px;
}
.github-menu .contents .item {
    padding: 10px 0;
}
.github-menu .contents .item .comment-count {
    font-family: var(--system-font);
    padding-right: 12px;
    font-weight: 600;
    color: #747d86;
}
.github-menu .contents .item .comment-icon {
    font-size: 14px;
    padding-top: 4px;
    padding-right: 6px;
    color: #747d86;
    font-family: var(--icons-font);
}
.github-menu .contents .item.first {
    border-top: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
.github-menu .contents .item.last {
    border-bottom: none;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}
.github-menu .contents .item:hover {
    background-color: var(--yasb-white-alpha-03);
}
.github-menu .contents .item .title,
.github-menu .contents .item .description {
    color: #9aa0a5;
    font-family: var(--system-font);
}
.github-menu .contents .item .title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 1px;
}
.github-menu .contents .item .description {
    font-size: 12px;
    font-weight: 600;
    margin-top: 1px;
    margin-left: 1px;
    color: #878c91;
}
.github-menu .contents .item.new .title,
.github-menu .contents .item.new .description {
    color: #ffffff;
}
.github-menu .contents .item .icon {
    font-size: 18px;
    color: #848992;
    min-width: 36px;
    max-width: 36px;
    padding-left: 8px;
    font-family: var(--icons-font-fallback);
}
.github-menu .contents .item .icon.issue {
    color: #3fb950;
}
.github-menu .contents .item .icon.issue.closed {
    color: #ab7df8;
}
.github-menu .contents .item .icon.pullrequest {
    color: #3fb950;
}
.github-menu .contents .item .icon.pullrequest.merged {
    color: #ab7df8;
}
.github-menu .contents .item .icon.pullrequest.draft {
    color: #848992;
}
.github-menu .contents .item .icon.discussion {
    color: #848992;
}
.github-menu .contents .item .icon.discussion.answered {
    color: #3fb950;
}
.github-menu .contents .item .icon.release {
    color: #848992;
}
.github-menu .contents .item .icon.checksuite {
    color: #f38ba8;
}"""

MICROPHONE_WIDGET_STYLE: str = """\
/* Microphone */
.microphone-widget:hover {
    background-color: var(--yasb-white-alpha-08);
}
.microphone-widget .icon {
    font-size: 14px;
}
.microphone-widget .icon.no-device {
    color: #a3a3a3;
    font-size: 14px;
}
.microphone-menu {
    background-color: var(--yasb-popup-bg);
    min-width: 300px;
}
.microphone-menu .system-volume-container .volume-slider {
    border: none;
}
.microphone-menu .microphone-container .device {
    background-color: transparent;
    border: none;
    padding: 6px 8px 6px 4px;
    margin: 2px 0;
    font-size: 12px;
    border-radius: 4px;
}
.microphone-menu .microphone-container .device.selected {
    background-color: var(--yasb-white-alpha-08);
}
.microphone-menu .microphone-container .device:hover {
    background-color: var(--yasb-white-alpha-06);
}"""

MEDIA_WIDGET_STYLE: str = """\
/* Media */
.media-widget {
    padding: 0;
    margin: 0;
}
.media-widget .label {
    padding: 0px 8px;
}
.media-widget .btn {
    color: #9498a8;
    padding: 0 4px;
    margin: 0;
    font-family: 'Segoe Fluent Icons';
    font-weight: 400;
}
.media-widget .btn:hover {
    color: #babfd3;
}
.media-widget .btn.play {
    font-size: 16px;
}
.media-widget .btn.disabled:hover,
.media-widget .btn.disabled {
    color: #4e525c;
    font-size: 12px;
    background-color: rgba(0, 0, 0, 0);
}
.media-widget .progress-bar {
    max-height: 2px;
    background-color: transparent;
    margin-left: 5px;
    border: none;
}
.media-widget .progress-bar::chunk {
    background-color: #0078D4ee;
    border-radius: 2px;
}
.media-menu {
    min-width: 440px;
    max-width: 440px;
    background-color: rgba(31, 39, 49, 0.5);
}
.media-menu .title,
.media-menu .artist,
.media-menu .source {
    font-size: 14px;
    font-weight: 600;
    margin-left: 10px;
    font-family: var(--system-font);
}
.media-menu .artist {
    font-size: 13px;
    color: #6c7086;
    margin-top: 0px;
}
.media-menu .source {
    font-size: 11px;
    color: #000;
    border-radius: 3px;
    background-color: #4cc2ff;
    padding: 2px 4px;
    font-weight: 600;
    font-family: var(--system-font);
    margin-top: 10px;
}
.media-menu .btn {
    font-family: 'Segoe Fluent Icons';
    font-size: 14px;
    font-weight: 400;
    margin: 10px 2px 0px 2px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    border-radius: 20px;
}
.media-menu .btn.prev {
    margin-left: 10px;
}
.media-menu .btn:hover {
    color: white;
    background-color: var(--yasb-white-alpha-10);
}
.media-menu .btn.play {
    background-color: var(--yasb-white-alpha-10);
    font-size: 20px;
}
.media-menu .btn.disabled:hover,
.media-menu .btn.disabled {
    color: #4e525c;
    background-color: rgba(0, 0, 0, 0);
}
.media-menu .playback-time {
    font-size: 13px;
    font-family: var(--system-font);
    color: #7f849c;
    margin-top: 16px;
    min-width: 100px;
}
.media-menu .progress-slider {
    height: 10px;
    margin: 5px 4px;
    border-radius: 3px;
}
.media-menu .progress-slider::groove {
    background: transparent;
    height: 2px;
    border-radius: 3px;
    background: var(--yasb-white-alpha-10);
}
.media-menu .progress-slider::groove:hover {
    background: transparent;
    height: 6px;
    border-radius: 3px;
    background: var(--yasb-white-alpha-20);
}
.media-menu .progress-slider::sub-page {
    background: white;
    border-radius: 3px;
    height: 4px;
}
.media-menu .app-volume-container {
    background-color: var(--yasb-white-alpha-05);
    padding: 8px 6px;
    border-radius: 12px;
    margin-left: 10px;
}
.media-menu .app-volume-container .volume-slider::groove {
    background: var(--yasb-white-alpha-10);
    width: 2px;
    border-radius: 3px;
}
.media-menu .app-volume-container .volume-slider::add-page {
    background: white;
    border-radius: 3px;
}
.media-menu .app-volume-container .volume-slider::groove:hover {
    background: var(--yasb-white-alpha-10);
    width: 6px;
    border-radius: 3px;
}
.media-menu .app-volume-container .volume-slider::sub-page {
    background: var(--yasb-white-alpha-10);
    border-radius: 3px;
}
.media-menu .app-volume-container .mute-button,
.media-menu .app-volume-container .unmute-button {
    font-size: 16px;
    color: #ffffff;
    font-family: 'Segoe Fluent Icons';
    margin-top: 4px;
}
.media-menu .app-volume-container .unmute-button {
    color: #a0a0a0;
}"""

WIDGET_STYLES: dict[str, str] = {
    "base": BASE_WIDGET_STYLE,
    "komorebi": KOMOREBI_WIDGET_STYLE,
    "glazewm": GLAZEWM_WIDGET_STYLE,
    "windows_desktops": WINDOWS_DESKTOPS_WIDGET_STYLE,
    "cpu": CPU_WIDGET_STYLE,
    "memory": MEMORY_WIDGET_STYLE,
    "quick_launch": QUICK_LAUNCH_WIDGET_STYLE,
    "active_window": ACTIVE_WINDOW_WIDGET_STYLE,
    "systray": SYSTRAY_WIDGET_STYLE,
    "weather": WEATHER_WIDGET_STYLE,
    "github": GITHUB_WIDGET_STYLE,
    "microphone": MICROPHONE_WIDGET_STYLE,
    "media": MEDIA_WIDGET_STYLE,
}
