"""
Widgets configuration for the YASB setup wizard.
"""

from core.utils.system import is_windows_10

CPU_ICON = "\ue950" if is_windows_10() else "\ueea1"

BASE_WIDGET: dict = {
    "base": {
        "placement": {
            "home": ("left", 0),
            "clock": ("center", 0),
            "volume": ("right", 80),
            "notifications": ("right", 90),
            "power_menu": ("right", 100),
        },
        "config": {
            "home": {
                "type": "yasb.home.HomeWidget",
                "options": {
                    "label": "<span>\ue8a9</span>",
                    "menu_list": [
                        {"title": "User Home", "path": "~"},
                        {"title": "Download", "path": "~\\Downloads"},
                        {"title": "Documents", "path": "~\\Documents"},
                        {"title": "Pictures", "path": "~\\Pictures"},
                    ],
                    "system_menu": True,
                    "power_menu": True,
                    "blur": True,
                    "round_corners": True,
                    "round_corners_type": "normal",
                    "border_color": "System",
                    "alignment": "left",
                    "offset_left": -12,
                },
            },
            "clock": {
                "type": "yasb.clock.ClockWidget",
                "options": {
                    "label": "{%H:%M}<span>{alarm}</span>",
                    "label_alt": "{%a, %d %b %H:%M}",
                    "timezones": [],
                    "calendar": {
                        "blur": True,
                        "round_corners": True,
                        "alignment": "center",
                        "direction": "down",
                        "extended": False,
                        "show_years": True,
                        "show_holidays": False,
                        "show_week_numbers": True,
                    },
                    "callbacks": {
                        "on_left": "toggle_calendar",
                        "on_middle": "toggle_label",
                        "on_right": "context_menu",
                    },
                },
            },
            "volume": {
                "type": "yasb.volume.VolumeWidget",
                "options": {
                    "label": "<span>{icon}</span>",
                    "label_alt": "<span>{icon}</span>{level}",
                    "tooltip": True,
                    "volume_icons": ["\ue74f", "\ue992", "\ue993", "\ue994", "\ue995"],
                    "callbacks": {
                        "on_left": "toggle_volume_menu",
                        "on_right": "toggle_mute",
                    },
                    "audio_menu": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "system",
                        "alignment": "right",
                        "direction": "down",
                        "show_apps": True,
                        "show_app_labels": False,
                        "show_app_icons": True,
                        "show_apps_expanded": False,
                        "app_icons": {
                            "toggle_down": "\ue972",
                            "toggle_up": "\ue971",
                        },
                    },
                },
            },
            "notifications": {
                "type": "yasb.notifications.NotificationsWidget",
                "options": {
                    "label": "<span>\uf2a5</span>",
                    "label_alt": "{count} notifications",
                    "hide_empty": True,
                    "tooltip": False,
                    "callbacks": {
                        "on_left": "toggle_notification",
                        "on_right": "do_nothing",
                        "on_middle": "do_nothing",
                    },
                },
            },
            "power_menu": {
                "type": "yasb.power_menu.PowerMenuWidget",
                "options": {
                    "label": "<span>\ue712</span>",
                    "uptime": True,
                    "show_user": True,
                    "menu_style": "popup",
                    "popup": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "System",
                        "alignment": "right",
                        "offset_left": 12,
                    },
                    "profile_image_size": 64,
                    "buttons": {
                        "lock": ["\udb80\udf41", "Lock"],
                        "signout": ["\udb80\udf43", "Sign out"],
                        "sleep": ["\udb82\udd04", "Sleep"],
                        "hibernate": ["\udb82\udd01", "Hibernate"],
                        "restart": ["\udb81\udc53", "Restart"],
                        "shutdown": ["\udb82\udd06", "Shut Down"],
                        "cancel": ["", "Cancel"],
                    },
                },
            },
        },
    },
}

KOMOREBI_WIDGET: dict = {
    "komorebi": {
        "placement": {
            "komorebi_workspaces": ("left", 20),
        },
        "config": {
            "komorebi_workspaces": {
                "type": "komorebi.workspaces.WorkspaceWidget",
                "options": {
                    "label_workspace_btn": "{name}",
                    "label_workspace_active_btn": "{name}",
                    "label_workspace_populated_btn": "{name}",
                    "label_default_name": "{name}",
                    "label_zero_index": False,
                    "hide_empty_workspaces": False,
                    "hide_if_offline": True,
                },
            },
        },
    },
}

GLAZEWM_WIDGET: dict = {
    "glazewm": {
        "placement": {
            "glazewm_workspaces": ("left", 30),
        },
        "config": {
            "glazewm_workspaces": {
                "type": "glazewm.workspaces.GlazewmWorkspacesWidget",
                "options": {
                    "hide_if_offline": True,
                    "monitor_exclusive": False,
                },
            },
        },
    },
}

WINDOWS_DESKTOPS_WIDGET: dict = {
    "windows_desktops": {
        "placement": {
            "windows_desktops": ("left", 10),
        },
        "config": {
            "windows_desktops": {
                "type": "yasb.windows_desktops.WorkspaceWidget",
                "options": {
                    "label_workspace_btn": "{name}",
                    "label_workspace_active_btn": "{name}",
                    "callbacks": {
                        "on_left": "activate_workspace",
                        "on_middle": "do_nothing",
                        "on_right": "toggle_context_menu",
                    },
                },
            },
        },
    },
}

CPU_WIDGET: dict = {
    "cpu": {
        "placement": {
            "cpu": ("right", 30),
        },
        "config": {
            "cpu": {
                "type": "yasb.cpu.CpuWidget",
                "options": {
                    "label": f"<span>{CPU_ICON}</span> {{info[percent][total]}}%",
                    "label_alt": "{info[freq][current]} MHz",
                    "update_interval": 2000,
                    "hide_decimal": True,
                    "menu": {
                        "enabled": True,
                        "show_graph": True,
                        "show_graph_grid": True,
                        "graph_history_size": 60,
                        "alignment": "center",
                    },
                    "callbacks": {
                        "on_left": "toggle_menu",
                        "on_middle": "do_nothing",
                        "on_right": "toggle_label",
                    },
                },
            },
        },
    },
}

MEMORY_WIDGET: dict = {
    "memory": {
        "placement": {
            "memory": ("right", 40),
        },
        "config": {
            "memory": {
                "type": "yasb.memory.MemoryWidget",
                "options": {
                    "label": "<span>\ue9d9</span> {virtual_mem_free}",
                    "label_alt": "<span>\uefc5</span> VIRT: {virtual_mem_percent}% SWAP: {swap_mem_percent}%",
                    "update_interval": 5000,
                    "hide_decimal": True,
                    "callbacks": {
                        "on_left": "toggle_menu",
                        "on_middle": "do_nothing",
                        "on_right": "toggle_label",
                    },
                    "menu": {
                        "enabled": True,
                        "show_graph": True,
                        "show_graph_grid": True,
                        "graph_history_size": 60,
                        "alignment": "center",
                    },
                },
            },
        },
    },
}

QUICK_LAUNCH_WIDGET: dict = {
    "quick_launch": {
        "placement": {
            "quick_launch": ("left", 5),
        },
        "config": {
            "quick_launch": {
                "type": "yasb.quick_launch.QuickLaunchWidget",
                "options": {
                    "label": "<span>\ue71e</span>",
                    "search_placeholder": "Search applications...",
                    "max_results": 30,
                    "show_icons": True,
                    "icon_size": 16,
                    "compact_text": True,
                    "providers": {
                        "apps": {
                            "enabled": True,
                            "prefix": "*",
                            "priority": 0,
                            "show_recent": True,
                            "max_recent": 5,
                            "show_description": True,
                        },
                    },
                    "popup": {
                        "width": 720,
                        "height": 480,
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "system",
                        "dark_mode": True,
                    },
                    "callbacks": {
                        "on_left": "toggle_quick_launch",
                    },
                    "keybindings": [
                        {
                            "keys": "alt+space",
                            "action": "toggle_quick_launch",
                            "screen": "primary",
                        }
                    ],
                },
            },
        },
    },
}

ACTIVE_WINDOW_WIDGET: dict = {
    "active_window": {
        "placement": {
            "active_window": ("left", 40),
        },
        "config": {
            "active_window": {
                "type": "yasb.active_window.ActiveWindowWidget",
                "options": {
                    "label": "{win[title]}",
                    "label_alt": "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]",
                    "label_no_window": "",
                    "label_icon": True,
                    "label_icon_size": 16,
                    "max_length": 32,
                    "max_length_ellipsis": "...",
                    "monitor_exclusive": False,
                },
            },
        },
    },
}

SYSTRAY_WIDGET: dict = {
    "systray": {
        "placement": {
            "systray": ("right", 20),
        },
        "config": {
            "systray": {
                "type": "yasb.systray.SystrayWidget",
                "options": {
                    "class_name": "systray",
                    "label_collapsed": "\ue972",
                    "label_expanded": "\ue971",
                    "label_position": "right",
                    "pin_click_modifier": "ctrl",
                    "show_unpinned": False,
                    "show_battery": False,
                    "show_volume": False,
                    "icon_size": 16,
                    "use_hook": True,
                    "show_in_popup": True,
                    "icons_per_row": 5,
                    "popup": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "None",
                        "alignment": "center",
                        "direction": "down",
                        "offset_top": 6,
                        "offset_left": 0,
                    },
                },
            },
        },
    },
}

WEATHER_WIDGET: dict = {
    "weather": {
        "placement": {
            "open_meteo": ("right", 60),
        },
        "config": {
            "open_meteo": {
                "type": "yasb.open_meteo.OpenMeteoWidget",
                "options": {
                    "label": "<span>\ue706</span>{temp}",
                    "label_alt": "{location}: Min {min_temp}, Max {max_temp}, Humidity {humidity}",
                    "tooltip": True,
                    "update_interval": 600,
                    "hide_decimal": True,
                    "units": "metric",
                    "callbacks": {
                        "on_left": "toggle_card",
                        "on_middle": "do_nothing",
                        "on_right": "toggle_label",
                    },
                    "icons": {
                        "sunnyDay": "\ue706",
                        "clearNight": "\uec46",
                    },
                    "weather_card": {
                        "blur": True,
                        "alignment": "right",
                        "direction": "down",
                        "icon_size": 32,
                        "show_hourly_forecast": True,
                        "time_format": "24h",
                        "hourly_point_spacing": 76,
                        "hourly_icon_size": 16,
                        "icon_smoothing": True,
                        "temp_line_width": 2,
                        "current_line_color": "#8EAEE8",
                        "current_line_width": 1,
                        "current_line_style": "dot",
                        "hourly_forecast_buttons": {
                            "enabled": False,
                        },
                        "weather_animation": {
                            "enabled": True,
                            "snow_overrides_rain": True,
                            "temp_line_animation_style": "both",
                            "rain_effect_intensity": 1.0,
                            "snow_effect_intensity": 1.0,
                            "scale_with_chance": True,
                        },
                    },
                },
            },
        },
    },
}

GITHUB_WIDGET: dict = {
    "github": {
        "placement": {
            "github": ("right", 50),
        },
        "config": {
            "github": {
                "type": "yasb.github.GithubWidget",
                "options": {
                    "label": "<span>\ueba1</span>",
                    "label_alt": "Notifications {data}",
                    "max_notification": 50,
                    "notification_dot": {
                        "enabled": True,
                        "corner": "top_right",
                        "color": "#ef4747",
                        "margin": [0, 3],
                    },
                    "only_unread": False,
                    "show_comment_count": True,
                    "max_field_size": 54,
                    "update_interval": 300,
                    "icons": {
                        "comment": "\ue90a",
                    },
                    "menu": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "System",
                        "alignment": "center",
                        "direction": "down",
                        "show_categories": True,
                        "categories_order": [
                            "Issue",
                            "PullRequest",
                            "CheckSuite",
                            "Release",
                            "Discussion",
                        ],
                    },
                },
            },
        },
    },
}

MICROPHONE_WIDGET: dict = {
    "microphone": {
        "placement": {
            "microphone": ("right", 70),
        },
        "config": {
            "microphone": {
                "type": "yasb.microphone.MicrophoneWidget",
                "options": {
                    "label": "<span>{icon}</span>",
                    "label_alt": "<span>{icon}</span> {level}",
                    "mute_text": "mute",
                    "icons": {
                        "normal": "\uec71",
                        "muted": "\ue720",
                    },
                    "mic_menu": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "system",
                        "alignment": "right",
                        "direction": "down",
                    },
                    "callbacks": {
                        "on_left": "toggle_mic_menu",
                        "on_middle": "toggle_label",
                        "on_right": "toggle_mute",
                    },
                },
            },
        },
    },
}

MEDIA_WIDGET: dict = {
    "media": {
        "placement": {
            "media": ("right", 10),
        },
        "config": {
            "media": {
                "type": "yasb.media.MediaWidget",
                "options": {
                    "label": "{title}{s}{artist}",
                    "label_alt": "{title}",
                    "separator": " - ",
                    "hide_empty": True,
                    "callbacks": {
                        "on_left": "toggle_media_menu",
                        "on_middle": "do_nothing",
                        "on_right": "do_nothing",
                    },
                    "max_field_size": {
                        "label": 20,
                        "label_alt": 20,
                    },
                    "show_thumbnail": True,
                    "controls_only": False,
                    "controls_left": True,
                    "controls_hide": True,
                    "thumbnail_alpha": 100,
                    "thumbnail_padding": 10,
                    "thumbnail_edge_fade": True,
                    "icons": {
                        "prev_track": "\ue892",
                        "next_track": "\ue893",
                        "play": "\ue768",
                        "pause": "\ue769",
                    },
                    "media_menu": {
                        "blur": True,
                        "round_corners": True,
                        "round_corners_type": "normal",
                        "border_color": "system",
                        "alignment": "center",
                        "direction": "down",
                        "thumbnail_corner_radius": 8,
                        "thumbnail_size": 120,
                        "max_title_size": 60,
                        "max_artist_size": 20,
                        "show_volume_slider": True,
                    },
                    "scrolling_label": {
                        "enabled": True,
                        "style": "bounce",
                        "update_interval_ms": 40,
                    },
                },
            },
        },
    },
}


WIDGETS_CONFIG: dict[str, dict] = {
    **BASE_WIDGET,
    **KOMOREBI_WIDGET,
    **GLAZEWM_WIDGET,
    **WINDOWS_DESKTOPS_WIDGET,
    **CPU_WIDGET,
    **MEMORY_WIDGET,
    **QUICK_LAUNCH_WIDGET,
    **ACTIVE_WINDOW_WIDGET,
    **SYSTRAY_WIDGET,
    **WEATHER_WIDGET,
    **GITHUB_WIDGET,
    **MICROPHONE_WIDGET,
    **MEDIA_WIDGET,
}
