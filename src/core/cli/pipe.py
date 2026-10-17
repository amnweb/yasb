"""The named pipes yasbc and the bar talk over, and how their messages are encoded."""

import json

from core.utils.win32.bindings.kernel32 import ReadFile, WriteFile

CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"
BUFSIZE = 65536


def write_message(handle: int, msg_dict: dict[str, str]):
    try:
        data = json.dumps(msg_dict).encode("utf-8")
    except Exception as e:
        print(f"JSON encode error: {e}")
        print(f"Data: {msg_dict}")
        return False
    success = WriteFile(handle, data)
    return success


def read_message(handle: int) -> dict[str, str] | None:
    success, data = ReadFile(handle, BUFSIZE)
    if not success or len(data) == 0:
        return None
    try:
        messages: list[str] = []
        # This is needed in case there are multiple json objects in one data block
        for line in data.split(b"\0"):
            if not line.strip():
                continue
            json_object = json.loads(line.decode().strip())
            if json_object.get("type") == "DATA":
                messages.append(json_object.get("data"))
            else:
                # If it's ping/pong, just return the object as is
                return json_object
        return {"type": "DATA", "data": "\n".join(messages)}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Data: {data}")
        return None
