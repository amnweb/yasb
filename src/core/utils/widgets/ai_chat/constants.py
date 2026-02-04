# UI Constants
THINKING_PLACEHOLDER = "thinking ..."

# Timeouts and Intervals
DEFAULT_TIMEOUT_SECONDS = 120
MESSAGE_QUEUE_TIMEOUT_SECONDS = 0.1
FLUSH_INTERVAL_MS = 250
THINKING_ANIMATION_INTERVAL_MS = 300
SCROLL_DELAY_MS = 50
SCROLL_ANIMATION_MS = 200
BATCH_RENDER_SIZE = 2
BATCH_RENDER_DELAY_MS = 10
OPENAI_CHUNK_BATCH = 50

# Syntax Highlighting
MAX_HIGHLIGHTED_CODE_LENGTH = 15000

# Chat code block
CODE_MONO_FONT = "'JetBrains Mono','Cascadia Code','Fira Code','Consolas','Monaco',monospace"

# Permissions and Tools for Copilot
DEFAULT_ALLOWED_TOOLS = ("view", "web_fetch")
DEFAULT_ALLOWED_PERMISSION_KINDS = frozenset({"read", "url"})

# Image Handling Constants
FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

FORMAT_TO_EXT = {
    "PNG": "png",
    "JPEG": "jpg",
    "JPG": "jpg",
    "GIF": "gif",
    "WEBP": "webp",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Size limits
BYTES_PER_KB = 1024
IMAGE_READER_ALLOCATION_LIMIT = 1024
REMOVE_BUTTON_SIZE_PX = 20

# For the OpenAI Vision API, the recommended maximum dimension for optimal processing and token efficiency
# is to resize the image so that the longest side is no more than 2048 pixels
MAX_IMAGE_DIMENSION = 2048
