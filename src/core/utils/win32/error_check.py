import ctypes as ct

from core.utils.win32.bindings.kernel32 import FormatMessage
from core.utils.win32.constants import FORMAT_MESSAGE_FROM_SYSTEM, FORMAT_MESSAGE_IGNORE_INSERTS


def format_error_message(error_code: int) -> str:
    buffer = ct.create_unicode_buffer(1024)
    length = FormatMessage(
        FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        None,
        error_code,
        0,
        buffer,
        len(buffer),
        None,
    )
    return buffer.value.strip() if length else f"Unknown error code: {error_code}"
