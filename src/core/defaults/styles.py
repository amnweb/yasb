def get_default_styles() -> str:
    return """\
/* 
This is default and very simple styles file for Yasb. 
For more information about configuration options, please visit the Wiki https://github.com/amnweb/yasb/wiki
*/
:root {
    --mauve: #cba6f7;
    --red: #f38ba8;
    --yellow: #ffd16d;
    --blue: #448fff;
    --lavender: #b4befe;
    --text1: #d4d9eb;
    --text2: #8f929e;
    --text3: #9399b2;
    --text4: #7f849c;
    --bg-color1: #191919;
    --bg-color2: #333333;
}
* {
    font-size: 12px;
    color: var(--text1);
    font-weight: 600;
    font-family: "JetBrainsMono NFP";
}
.yasb-bar {
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
}
/* Global styles for ToolTip */
.tooltip {
    background-color: var(--bg-color1);
    border-radius: 4px;
    color: var(--text1);
    padding: 5px 10px;
    font-size: 12px;
    font-family: 'Segoe UI';
    font-weight: 600;
    margin-top: 4px;
}
/* Global context menu style */
.context-menu,
.context-menu .menu-checkbox {
    background-color: var(--bg-color1);
    padding: 4px 0px;
    font-family: 'Segoe UI';
    font-size: 12px;
    color: var(--text1)
}
.context-menu {
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.075);
}
.context-menu::right-arrow {
    width: 8px;
    height: 8px;
    padding-right: 24px;
}
.context-menu::item,
.context-menu .menu-checkbox {
    background-color: transparent;
    padding: 6px 12px;
    margin: 2px 6px;
    border-radius: 6px;
    min-width: 100px;
}

.context-menu::item:selected,
.context-menu .menu-checkbox:hover {
    background-color: var(--bg-color2);
    color: #FFFFFF;
}
.context-menu::separator {
    height: 1px;
    background-color: #404040;
    margin: 4px 8px;
}
.context-menu::item:disabled {
    color: #666666;
    background-color: transparent;
}
.context-menu .menu-checkbox .checkbox {
    border: none;
    padding: 8px 16px;
    font-size: 12px;
    margin: 0;
    color: var(--text1);
    font-family: 'Segoe UI'
}
.context-menu .submenu::item:disabled {
    margin: 0;
    padding-left: 16px;
}
.context-menu .menu-checkbox .checkbox:unchecked {
    color: var(--text2)
}
.context-menu .menu-checkbox .checkbox::indicator {
    width: 12px;
    height: 12px;
    margin-left: 0px;
    margin-right: 8px;
}
.context-menu .menu-checkbox .checkbox::indicator:unchecked {
    background: #444444;
    border-radius: 2px;
}
.context-menu .menu-checkbox .checkbox::indicator:checked {
    background: var(--blue);
    border-radius: 2px;
}
.context-menu .menu-checkbox .checkbox:focus {
    outline: none;
}
.widget {
    padding: 0 12px;
    margin: 0;
}
.icon {
    font-size: 16px;
}
.widget .label {
    padding: 0px 2px;
}
.komorebi-active-layout {
    padding: 0
}
.komorebi-workspaces .offline-status {
    color: var(--text4);
    font-size: 12px;
    padding: 0 0 0 4px;
    font-weight: 600;
}
.komorebi-workspaces .ws-btn {
    border: none;
    background-color: var(--text4);
    margin: 0 3px;
    height: 9px;
    width: 9px;
    border-radius: 4px;
}
.komorebi-workspaces .ws-btn:hover {
    color: var(--text2);
}
.komorebi-workspaces .ws-btn.populated {
    background-color: var(--lavender);
}
.komorebi-workspaces .ws-btn.active {
    background-color: var(--blue);
    width: 36px;
}
.power-menu-widget .label {
    color: #f38ba8;
    font-size: 13px;
}
.power-menu-popup {
    background-color: rgba(255, 255, 255, 0.04);
    padding: 32px;
    border-radius: 32px;
}
.power-menu-popup .button {
    padding: 0;
    min-width: 140px;
    max-width: 140px;
    min-height: 80px;
    border-radius: 12px;
    background-color: #ffffff11;
    border: 8px solid rgba(255, 255, 255, 0)
}
.power-menu-popup .button.hover {
    background-color: #134c96;
    border: 8px solid #134c96;
}
.power-menu-popup .button .label {
    font-size: 13px;
    font-weight: 600;
    font-family: 'Segoe UI';
    color: #a9a9ac;
}
.power-menu-popup .button .icon {
    font-size: 32px;
    color: rgba(255, 255, 255, 0.4)
}
.power-menu-popup .button.hover .label,
.power-menu-popup .button.hover .icon {
    color: #ffffff
}
.power-menu-popup .profile-info {
    padding: 0 0 16px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background-color: transparent;
    margin-bottom: 16px;
}
.power-menu-popup .profile-info .profile-username {
    font-size: 24px;
    font-weight: 600;
    color: #cdd6f4;
    margin-top: 0;
    font-family: 'Segoe UI';
}
.power-menu-popup .profile-info .profile-account-type {
    font-size: 15px;
    color: rgba(205, 214, 244, 0.6);
    margin-top: 8px;
    font-family: 'Segoe UI'
}
.power-menu-popup .profile-info .profile-email {
    font-size: 13px;
    color: rgba(205, 214, 244, 0.4);
    margin-top: 4px;
    font-family: 'Segoe UI'
}
.power-menu-overlay {
    background-color: rgba(0, 0, 0, 0.15);
}
.power-menu-overlay .uptime {
    font-size: 16px;
    margin-bottom: 20px;
    color: #9ea2b4;
    font-weight: 600;
}
.microphone-widget {
    padding: 0 6px 0 6px;
}
.microphone-widget .icon {
    font-size: 18px;
}
.microphone-widget .icon {
    color: var(--mauve);
}
.volume-widget .icon {
    font-size: 17px;
    color: var(--blue);
    margin: 0px 2px 0 0;
}
.open-meteo-widget,
.volume-widget {
    padding: 0 6px;
}
.open-meteo-widget .icon {
    font-size: 18px;
    margin: 0 2px 1px 0;
    color: var(--yellow);
}
.open-meteo-widget .label {
    font-size: 13px;
    font-family: "Segoe UI";
    font-weight: 400;
    color: rgba(255, 255, 255, 0.8);
    padding-left: 4px;
}
.open-meteo-card {
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
    min-width: 500px;
}
.open-meteo-card-today .label {
    font-size: 13px;
    font-family: "Segoe UI";
    font-weight: 400;
    color: rgb(163, 163, 163);
}
.open-meteo-card-today .label.location {
    font-size: 32px;
    font-weight: 700;
    font-family: "Segoe UI";
    color: rgb(255, 255, 255);
}
.open-meteo-card-today .label.sunrisesunset {
    font-size: 18px;
    font-family: "Segoe UI";
    font-weight: 600;
    color: rgb(201, 204, 159);
}
.open-meteo-card-today .label.sunrisesunset-icon {
    font-size: 18px;
    color: rgb(201, 204, 159);
    font-family: "JetBrainsMono NFP";
}
.open-meteo-card-day {
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background-color: rgba(0, 0, 0, 0);
    padding: 4px;
    min-width: 70px;
}
.open-meteo-card-day .day-name {
    font-family: "Segoe UI";
    color: rgba(255, 255, 255, 0.6);
    font-size: 12px;
    font-weight: 600;
}
.open-meteo-card-day .day-temp-max {
    font-family: "Segoe UI";
    font-weight: 700;
    font-size: 16px;
    color: rgb(255, 255, 255);
}
.open-meteo-card-day .day-temp-min {
    font-family: "Segoe UI";
    color: rgb(255, 255, 255);
    font-weight: 400;
    font-size: 13px;
}
.open-meteo-card-day.active {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
}
.open-meteo-card-day:hover {
    background-color: rgba(255, 255, 255, 0.04);
}
.open-meteo-card .hourly-container {
    border: none;
    background-color: transparent;
    min-height: 120px;
}
.open-meteo-card .hourly-data {
    font-size: 11px;
    font-weight: 700;
    font-family: "Segoe UI";
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
    color: rgba(150, 200, 255, 40);
    background-color: rgba(0, 0, 0, 0);
}
.open-meteo-card .hourly-data .hourly-snow-animation {
    color: rgba(255, 255, 255, 150);
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
    color: rgba(255, 255, 255, 0.3);
    border: 1px solid transparent;
}
.open-meteo-card .hourly-data-button.active {
    color: #fff;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.open-meteo-card .search-head {
    font-size: 18px;
    font-family: "Segoe UI";
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
}
.open-meteo-card .search-description {
    font-size: 14px;
    font-family: "Segoe UI";
    font-weight: 400;
    color: rgba(255, 255, 255, 0.7);
    padding-bottom: 8px;
}
.open-meteo-card .no-data-icon {
    font-size: 88px;
}
.open-meteo-card .no-data-text {
    font-size: 16px;
    font-family: "Segoe UI";
    font-weight: 400;
}
/* search dialog */
.open-meteo-card .search-input {
    padding: 8px 12px;
    border: 1px solid #5e6070;
    border-radius: 6px;
    background-color: rgba(17, 17, 27, 0.1);
    color: #cdd6f4;
    font-family: "Segoe UI";
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
    font-family: "Segoe UI";
}
.open-meteo-card .search-results::item {
    padding: 6px;
}
.open-meteo-card .search-results::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}
.media-widget {
    padding: 0;
    margin: 0;
    border-radius: 0;
}
.media-widget .btn {
    color: #7a7f8b;
    padding: 0 4px;
    margin: 0;
    font-family: "JetBrainsMono NFP";
    font-weight: 400;
    font-size: 20px;
}
.media-widget .btn:hover {
    color: #babfd3;
}
.media-widget .btn.play {
    font-size: 24px;
    color: #989caa;
}
.media-widget .btn.disabled:hover,
.media-widget .btn.disabled {
    color: #4e525c;
    background-color: rgba(0, 0, 0, 0);
    font-size: 20px;
}
.media-menu {
    min-width: 420px;
    max-width: 420px;
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
}
.media-menu .title,
.media-menu .artist,
.media-menu .source {
    font-size: 14px;
    font-weight: 600;
    margin-left: 10px;
    font-family: 'Segoe UI'
}
.media-menu .artist {
    font-size: 13px;
    color: #6c7086;
    margin-top: 0px;
    margin-bottom: 8px;
}
.media-menu .source {
    font-size: 11px;
    color: #000;
    font-weight: normal;
    border-radius: 3px;
    background-color: #bac2de;
    padding: 2px 4px;

}
.media-menu .source.firefox {
    background-color: #ff583b;
    color: #ffffff;
}
.media-menu .source.spotify {
    background-color: #199143;
    color: #ffffff;
}
.media-menu .source.edge {
    background-color: #0078d4;
    color: #ffffff;
}
.media-menu .source.windows-media {
    background-color: #0078d4;
    color: #ffffff;
}

.media-menu .btn {
    font-family: "Segoe Fluent Icons";
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
    background-color: rgba(255, 255, 255, 0.1);
}
.media-menu .btn.play {
    background-color: rgba(255, 255, 255, 0.1);
    font-size: 20px
}
.media-menu .btn.disabled:hover,
.media-menu .btn.disabled {
    color: #4e525c;
    background-color: rgba(0, 0, 0, 0);
}

.media-menu .playback-time {
    font-size: 13px;
    font-family: 'Segoe UI';
    color: #7f849c;
    margin-top: 20px;
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
    background: rgba(255, 255, 255, 0.1);

}
.media-menu .progress-slider::groove:hover {
    background: transparent;
    height: 6px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.2);
}
.media-menu .progress-slider::sub-page {
    background: white;
    border-radius: 3px;
    height: 4px;
}
.home-widget {
    padding: 0 4px 0 12px;
}
.home-widget .icon {
    color: var(--lavender);
}
.home-widget .icon:hover {
    color: var(--text1);
}
.home-menu {
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
}
.home-menu .menu-item {
    padding: 8px 48px 9px 16px;
    font-size: 12px;
    font-family: 'Segoe UI';
    color: var(--text1);
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
.notification-widget {
    padding: 0 0px 0 4px;
}
.notification-widget .icon {
    font-size: 14px;
}
.notification-widget .icon.new-notification {
    color: var(--blue);
}

.calendar {
    background-color: var(--bg-color1);
    border-radius: 8px;
    border: 1px solid var(--bg-color2);
}
.calendar .calendar-table,
.calendar .calendar-table::item {
    background-color: rgba(17, 17, 27, 0);
    color: rgba(162, 177, 196, 0.85);
    font-family: "Segoe UI";
    margin: 0;
    padding: 0;
    border: none;
    outline: none;
}
.calendar .calendar-table::item:selected {
    color: #000000;
    background-color: var(--blue);
    border-radius: 10px;
}
.calendar .day-label {
    margin-top: 20px;
}
.calendar .day-label,
.calendar .month-label,
.calendar .date-label,
.calendar .week-label,
.calendar .holiday-label {
    font-family: "Segoe UI";
    font-size: 16px;
    color: #fff;
    font-weight: 700;
    min-width: 180px;
    max-width: 180px;
}
.calendar .week-label,
.calendar .holiday-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(162, 177, 196, 0.85);
}
.calendar .holiday-label {
    color: rgba(162, 177, 196, 0.85);
    font-weight: 700;
}
.calendar .month-label {
    font-weight: normal;
}
.calendar .date-label {
    font-size: 88px;
    font-weight: 900;
    color: rgb(255, 255, 255);
    margin-top: -20px;
}"""
