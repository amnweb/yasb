import json
import logging
import re
import time
from datetime import datetime

import psutil
from PyQt6.QtWidgets import QApplication

from core.utils.utilities import app_data_path


class TrafficDataManager:
    """Manages traffic data storage, loading, and calculations for all interfaces"""

    # Class-level storage for interface data
    _interface_data: dict[
        str, dict
    ] = {}  # {interface: {total_bytes_sent, total_bytes_recv, today_sent, today_recv, etc}}
    _global_data_folder = None
    _interface_last_save_times: dict[str, float] = {}  # Track save time per interface
    _quit_handler_registered = False  # Track if global quit handler is registered

    @classmethod
    def setup_global_data_storage(cls):
        """Setup global data storage directory (class-level, called once)"""
        if cls._global_data_folder is not None:
            return

        try:
            cls._global_data_folder = app_data_path()

            # Register quit handler once when data storage is set up
            cls._register_cleanup_handlers()

        except Exception as e:
            logging.debug(f"Error setting up global net data storage: {e}")

    @classmethod
    def _register_cleanup_handlers(cls):
        """Register application quit handler to save all interface data"""
        if cls._quit_handler_registered:
            return

        try:
            app_inst = QApplication.instance()
            if app_inst is not None:
                app_inst.aboutToQuit.connect(cls.destroy)
                cls._quit_handler_registered = True

        except Exception as e:
            logging.error(f"Error registering global quit handler: {e}")

    @classmethod
    def destroy(cls):
        """Save data for all active interfaces on application quit"""
        try:
            saved_interfaces = []
            for interface in cls._interface_data.keys():
                if cls._interface_data[interface].get("_loaded", False):
                    cls.save_interface_data(interface)
                    saved_interfaces.append(interface)

        except Exception as e:
            logging.error(f"Error saving interfaces on quit: {e}")

    @classmethod
    def get_interface_data_file(cls, interface: str):
        """Get the data file path for a specific interface"""
        if cls._global_data_folder is None:
            return None

        # Sanitize interface name for filename
        safe_interface = re.sub(r'[<>:"/\\|?*\s]', "_", interface.lower())
        if safe_interface == "auto":
            safe_interface = "system_auto"

        return cls._global_data_folder / f"yasb_traffic_{safe_interface}.json"

    @classmethod
    def initialize_interface(cls, interface: str):
        """Initialize interface data if not already loaded"""
        if interface in cls._interface_data and cls._interface_data[interface].get("_loaded", False):
            return cls._interface_data[interface]["session_start_sent"], cls._interface_data[interface][
                "session_start_recv"
            ]

        # Initialize defaults
        cls._interface_data[interface] = {
            "total_bytes_sent": 0,
            "total_bytes_recv": 0,
            "today_sent": 0,
            "today_recv": 0,
            "today_date": None,
            "session_start_sent": None,
            "session_start_recv": None,
            "today_start_sent": None,
            "today_start_recv": None,
            "session_start_time": time.time(),
            "_loaded": False,
        }

        # Initialize save time
        if interface not in cls._interface_last_save_times:
            cls._interface_last_save_times[interface] = time.time()

        # Load from file
        cls._load_from_file(interface)
        cls.initialize_today_tracking(interface)

        # Mark as loaded
        cls._interface_data[interface]["_loaded"] = True

        return cls._interface_data[interface]["session_start_sent"], cls._interface_data[interface][
            "session_start_recv"
        ]

    @classmethod
    def get_session_duration(cls, interface: str):
        """Get how long ago the session started as a human readable string"""
        if interface not in cls._interface_data:
            return "just now"

        start_time = cls._interface_data[interface].get("session_start_time", time.time())
        seconds_ago = time.time() - start_time

        if seconds_ago < 60:
            return f"{int(seconds_ago)} sec"
        elif seconds_ago < 3600:  # Less than 1 hour
            minutes = int(seconds_ago // 60)
            return f"{minutes} min" if minutes > 1 else "1 min"
        elif seconds_ago < 86400:  # Less than 1 day
            hours = int(seconds_ago // 3600)
            minutes = int((seconds_ago % 3600) // 60)
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h" if hours > 1 else "1h"
        else:  # 1 day or more
            days = int(seconds_ago // 86400)
            hours = int((seconds_ago % 86400) // 3600)
            if hours > 0:
                return f"{days}d {hours}h"
            else:
                return f"{days}d" if days > 1 else "1d"

    @classmethod
    def _load_from_file(cls, interface: str):
        """Load data from JSON file"""
        data_file = cls.get_interface_data_file(interface)
        if data_file and data_file.exists():
            try:
                with open(data_file, "r") as f:
                    data = json.load(f)

                cls._interface_data[interface]["total_bytes_sent"] = data.get("total_sent", 0)
                cls._interface_data[interface]["total_bytes_recv"] = data.get("total_recv", 0)
                cls._interface_data[interface]["today_sent"] = data.get("today_sent", 0)
                cls._interface_data[interface]["today_recv"] = data.get("today_recv", 0)
                cls._interface_data[interface]["today_date"] = data.get("today_date", None)

            except Exception as e:
                logging.error(f"Error loading traffic data for interface {interface}: {e}")

    @classmethod
    def _apply_alignment(cls, text: str, max_length: int, alignment: str) -> str:
        """Apply text alignment based on parameters"""
        if max_length <= 0:
            return text

        if alignment == "right":
            return str.rjust(text, max_length)
        elif alignment == "center":
            return str.center(text, max_length)
        else:  # default to left
            return str.ljust(text, max_length)

    @classmethod
    def calculate_network_data(
        cls,
        interface: str,
        previous_sent: int,
        previous_recv: int,
        session_sent: int,
        session_recv: int,
        interval_seconds: int,
        speed_unit: str,
        hide_decimal: bool,
        speed_threshold: dict,
        max_label_length: int = 0,
        max_label_length_align: str = "left",
    ):
        """Calculate all network data including speeds, totals, and handle counter resets"""
        try:
            current_io = cls.get_interface_io_counters(interface)
            if not current_io:
                return None

            # Calculate differences
            upload_diff = current_io.bytes_sent - previous_sent
            download_diff = current_io.bytes_recv - previous_recv

            # Handle counter resets
            reset_occurred = False
            if current_io.bytes_sent < previous_sent:
                upload_diff = 0
                reset_occurred = True

            if current_io.bytes_recv < previous_recv:
                download_diff = 0
                reset_occurred = True

            # Update today tracking and total data
            cls.update_today_and_total_tracking(interface, current_io)

            # Handle periodic saving
            if cls.should_save_data(interface):
                cls.save_interface_data(interface)

            # Calculate speeds per second
            upload_speed_per_sec = upload_diff / interval_seconds if interval_seconds > 0 else 0
            download_speed_per_sec = download_diff / interval_seconds if interval_seconds > 0 else 0

            # Get thresholds
            upload_threshold = speed_threshold.get("min_upload", 0) if speed_threshold else 0
            download_threshold = speed_threshold.get("min_download", 0) if speed_threshold else 0

            # Format data
            upload_speed = cls.format_speed(upload_speed_per_sec, speed_unit, hide_decimal, upload_threshold)
            download_speed = cls.format_speed(download_speed_per_sec, speed_unit, hide_decimal, download_threshold)

            raw_upload_speed = cls.format_speed(upload_speed_per_sec, speed_unit, False, upload_threshold)
            raw_download_speed = cls.format_speed(download_speed_per_sec, speed_unit, False, download_threshold)

            # Get today totals
            today_sent, today_recv = cls.get_today_totals(interface)
            today_uploaded = cls.format_data_size(today_sent)
            today_downloaded = cls.format_data_size(today_recv)

            # Calculate session totals (handle session resets)
            if reset_occurred:
                session_uploaded = cls.format_data_size(0)
                session_downloaded = cls.format_data_size(0)
            else:
                session_uploaded = cls.format_data_size(current_io.bytes_sent - session_sent)
                session_downloaded = cls.format_data_size(current_io.bytes_recv - session_recv)

            # Get all-time totals
            total_sent, total_recv = cls.get_total_data(interface)
            alltime_uploaded = cls.format_data_size(total_sent)
            alltime_downloaded = cls.format_data_size(total_recv)
            session_duration = cls.get_session_duration(interface)

            return {
                "upload_speed": cls._apply_alignment(upload_speed, max_label_length, max_label_length_align),
                "download_speed": cls._apply_alignment(download_speed, max_label_length, max_label_length_align),
                "raw_upload_speed": raw_upload_speed,
                "raw_download_speed": raw_download_speed,
                "today_uploaded": cls._apply_alignment(today_uploaded, max_label_length, max_label_length_align),
                "today_downloaded": cls._apply_alignment(today_downloaded, max_label_length, max_label_length_align),
                "session_uploaded": cls._apply_alignment(session_uploaded, max_label_length, max_label_length_align),
                "session_downloaded": cls._apply_alignment(
                    session_downloaded, max_label_length, max_label_length_align
                ),
                "session_duration": session_duration,
                "alltime_uploaded": cls._apply_alignment(alltime_uploaded, max_label_length, max_label_length_align),
                "alltime_downloaded": cls._apply_alignment(
                    alltime_downloaded, max_label_length, max_label_length_align
                ),
                "current_io": current_io,
                "reset_occurred": reset_occurred,
            }

        except Exception as e:
            logging.error(f"Error calculating network data for {interface}: {e}")
            return None

    @classmethod
    def save_interface_data(cls, interface: str):
        """Save traffic data for a specific interface"""
        if interface not in cls._interface_data:
            return

        data_file = cls.get_interface_data_file(interface)
        if data_file is None:
            return

        try:
            interface_data = cls._interface_data[interface]
            data = {
                "interface": interface,
                "total_sent": interface_data["total_bytes_sent"],
                "total_recv": interface_data["total_bytes_recv"],
                "today_sent": interface_data["today_sent"],
                "today_recv": interface_data["today_recv"],
                "today_date": interface_data["today_date"],
            }

            with open(data_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logging.error(f"Error saving traffic data for {interface}: {e}")

    @classmethod
    def initialize_today_tracking(cls, interface: str):
        """Initialize today tracking for current day for a specific interface"""
        try:
            if interface not in cls._interface_data:
                return

            today = datetime.now().strftime("%Y-%m-%d")

            # Get current system counters for this interface
            current_io = cls.get_interface_io_counters(interface)
            if not current_io:
                return

            # Session baseline is ONLY set once per interface (when first instance loads)
            if (
                cls._interface_data[interface]["session_start_sent"] is None
                or cls._interface_data[interface]["session_start_recv"] is None
            ):
                cls._interface_data[interface]["session_start_sent"] = current_io.bytes_sent
                cls._interface_data[interface]["session_start_recv"] = current_io.bytes_recv

            # Check if it's a new day
            if cls._interface_data[interface]["today_date"] != today:
                # New day - reset today counters and set new baseline
                cls._interface_data[interface]["today_date"] = today
                cls._interface_data[interface]["today_sent"] = 0
                cls._interface_data[interface]["today_recv"] = 0
                cls._interface_data[interface]["today_start_sent"] = current_io.bytes_sent
                cls._interface_data[interface]["today_start_recv"] = current_io.bytes_recv
            else:
                # Same day - calculate baseline from existing today data
                cls._interface_data[interface]["today_start_sent"] = (
                    current_io.bytes_sent - cls._interface_data[interface]["today_sent"]
                )
                cls._interface_data[interface]["today_start_recv"] = (
                    current_io.bytes_recv - cls._interface_data[interface]["today_recv"]
                )

        except Exception as e:
            logging.error(f"Error initializing today tracking for {interface}: {e}")
            if interface in cls._interface_data:
                cls._interface_data[interface]["today_start_sent"] = 0
                cls._interface_data[interface]["today_start_recv"] = 0
                if cls._interface_data[interface]["session_start_sent"] is None:
                    cls._interface_data[interface]["session_start_sent"] = 0
                if cls._interface_data[interface]["session_start_recv"] is None:
                    cls._interface_data[interface]["session_start_recv"] = 0

    @classmethod
    def get_interface_io_counters(cls, interface: str):
        """Get IO counters for a specific interface"""
        try:
            if interface.lower() == "auto":
                return psutil.net_io_counters()
            else:
                io_counters = psutil.net_io_counters(pernic=True)
                if interface in io_counters:
                    return io_counters[interface]
                else:
                    return psutil.net_io_counters()
        except Exception as e:
            logging.error(f"Error getting IO counters for {interface}: {e}")
            return None

    @classmethod
    def update_today_and_total_tracking(cls, interface: str, current_io):
        """Update today tracking and total data for a specific interface"""
        try:
            if interface not in cls._interface_data:
                return

            today = datetime.now().strftime("%Y-%m-%d")

            # Check if day has changed
            if cls._interface_data[interface]["today_date"] != today:
                # Day changed - finalize yesterday's data and reset for today
                cls._interface_data[interface]["today_date"] = today
                cls._interface_data[interface]["today_start_sent"] = current_io.bytes_sent
                cls._interface_data[interface]["today_start_recv"] = current_io.bytes_recv
                cls._interface_data[interface]["today_sent"] = 0
                cls._interface_data[interface]["today_recv"] = 0
                return

            # Normal tracking - calculate today's totals and incremental changes
            previous_today_sent = cls._interface_data[interface]["today_sent"]
            previous_today_recv = cls._interface_data[interface]["today_recv"]

            # Update today's data based on current counters
            if (
                cls._interface_data[interface]["today_start_sent"] is not None
                and cls._interface_data[interface]["today_start_recv"] is not None
            ):
                # Handle counter resets
                if current_io.bytes_sent >= cls._interface_data[interface]["today_start_sent"]:
                    cls._interface_data[interface]["today_sent"] = (
                        current_io.bytes_sent - cls._interface_data[interface]["today_start_sent"]
                    )
                if current_io.bytes_recv >= cls._interface_data[interface]["today_start_recv"]:
                    cls._interface_data[interface]["today_recv"] = (
                        current_io.bytes_recv - cls._interface_data[interface]["today_start_recv"]
                    )

            # Calculate how much today's data increased
            today_diff_sent = cls._interface_data[interface]["today_sent"] - previous_today_sent
            today_diff_recv = cls._interface_data[interface]["today_recv"] - previous_today_recv

            # Update total data by the same amount that today's data increased
            if today_diff_sent > 0:
                cls._interface_data[interface]["total_bytes_sent"] += today_diff_sent
            if today_diff_recv > 0:
                cls._interface_data[interface]["total_bytes_recv"] += today_diff_recv

        except Exception as e:
            logging.error(f"Error updating today and total tracking for {interface}: {e}")

    @classmethod
    def get_today_totals(cls, interface: str):
        """Get today's upload/download totals for a specific interface"""
        try:
            if interface not in cls._interface_data:
                return 0, 0

            return cls._interface_data[interface]["today_sent"], cls._interface_data[interface]["today_recv"]
        except Exception as e:
            logging.debug(f"Error getting today totals for {interface}: {e}")
        return 0, 0

    @classmethod
    def get_total_data(cls, interface: str):
        """Get total upload/download data for a specific interface"""
        if interface not in cls._interface_data:
            return 0, 0
        return cls._interface_data[interface]["total_bytes_sent"], cls._interface_data[interface]["total_bytes_recv"]

    @classmethod
    def get_session_baseline(cls, interface: str):
        """Get session baseline for a specific interface"""
        if interface not in cls._interface_data:
            return 0, 0
        return cls._interface_data[interface]["session_start_sent"], cls._interface_data[interface][
            "session_start_recv"
        ]

    @classmethod
    def reset_interface_data(cls, interface: str):
        """Reset all data for a specific interface"""
        try:
            if interface not in cls._interface_data:
                return

            # Get current IO counters for new baseline
            current_io = cls.get_interface_io_counters(interface)
            if not current_io:
                return

            # Reset all tracked data
            cls._interface_data[interface]["total_bytes_sent"] = 0
            cls._interface_data[interface]["total_bytes_recv"] = 0
            cls._interface_data[interface]["today_sent"] = 0
            cls._interface_data[interface]["today_recv"] = 0
            cls._interface_data[interface]["session_start_sent"] = current_io.bytes_sent
            cls._interface_data[interface]["session_start_recv"] = current_io.bytes_recv
            cls._interface_data[interface]["today_start_sent"] = current_io.bytes_sent
            cls._interface_data[interface]["today_start_recv"] = current_io.bytes_recv
            cls._interface_data[interface]["today_date"] = datetime.now().strftime("%Y-%m-%d")

            cls.save_interface_data(interface)

        except Exception as e:
            logging.error(f"Error resetting interface data for {interface}: {e}")

    @classmethod
    def should_save_data(cls, interface: str):
        """Check if data should be saved for a specific interface (every 10 seconds per interface)"""
        current_time = time.time()
        if interface not in cls._interface_last_save_times:
            cls._interface_last_save_times[interface] = current_time
            return True

        if current_time - cls._interface_last_save_times[interface] >= 10:
            cls._interface_last_save_times[interface] = current_time
            return True
        return False

    @classmethod
    def format_data_size(cls, bytes_value):
        """Format data size in bytes to human readable format"""
        if bytes_value >= 1024**4:  # TB
            return f"{bytes_value / (1024**4):.3f} TB"
        elif bytes_value >= 1024**3:  # GB
            return f"{bytes_value / (1024**3):.2f} GB"
        elif bytes_value >= 1024**2:  # MB
            return f"{bytes_value / (1024**2):.1f} MB"
        else:  # Everything below 1 MB (including 0)
            return "< 1 MB"

    @classmethod
    def format_speed(cls, bytes_per_sec, speed_unit="bits", hide_decimal=False, threshold=0):
        """Format speed with correct units based on configuration"""

        if bytes_per_sec < threshold:
            if speed_unit == "bytes":
                return "0 KB/s"
            else:
                return "0 Kbps"
        decimal_places = 0 if hide_decimal else 1

        if speed_unit == "bytes":
            # Use bytes per second (B/s, KB/s, MB/s, GB/s)
            if bytes_per_sec >= 1_073_741_824:  # GB/s
                return f"{bytes_per_sec / 1_073_741_824:.{decimal_places}f} GB/s"
            elif bytes_per_sec >= 1_048_576:  # MB/s
                return f"{bytes_per_sec / 1_048_576:.{decimal_places}f} MB/s"
            elif bytes_per_sec >= 1_024:  # KB/s
                return f"{bytes_per_sec / 1_024:.{decimal_places}f} KB/s"
            elif bytes_per_sec > 0:
                return f"{bytes_per_sec:.{decimal_places}f} B/s"
            else:
                return "0 B/s"
        else:
            # Default: Use bits per second (bps, Kbps, Mbps, Gbps)
            bits_per_sec = bytes_per_sec * 8
            if bits_per_sec >= 1_000_000_000:  # Gbps
                return f"{bits_per_sec / 1_000_000_000:.{decimal_places}f} Gbps"
            elif bits_per_sec >= 1_000_000:  # Mbps
                return f"{bits_per_sec / 1_000_000:.{decimal_places}f} Mbps"
            elif bits_per_sec >= 1_000:  # Kbps
                return f"{bits_per_sec / 1_000:.{decimal_places}f} Kbps"
            elif bits_per_sec > 0:
                return f"{bits_per_sec:.{decimal_places}f} bps"
            else:
                return "0 bps"
