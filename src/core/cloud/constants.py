"""Values shared across the YASB Cloud app."""

BASE_URL = "https://cloud.yasb.dev"
API_BASE_URL = "https://cloud-api.yasb.dev"
TERMS_URL = f"{BASE_URL}/terms"
PRIVACY_URL = f"{BASE_URL}/privacy"
API_PREFIX = "/v1"

CONTROL_TIMEOUT_MS = 15_000
"""Silence allowed on a request, restarted whenever bytes move."""

# The CLI's event loop ceilings. Both sit above CONTROL_TIMEOUT_MS so the client's own timer
# fires first and reports a real error, rather than the loop giving up with nothing to say.
CALL_TIMEOUT_MS = 30_000
TRANSFER_TIMEOUT_MS = 300_000

MIN_SPINNER_MS = 1000
"""Floor for the startup spinner, or it flickers and reads as a glitch."""

SHUTDOWN_WAIT_MS = 5000
"""Ceiling for a worker thread that will not stop, not the normal cost of closing."""

# Both mirror what the server issues with a device code. Drift and the app waits on a
# code that is already dead.
DEVICE_POLL_INTERVAL_S = 3
DEVICE_CODE_TTL_S = 600

BAD_SIGN_IN = "Sign-in did not complete. Please try again."
EXPIRED_CODE_APP = "This sign-in request expired. Start again when you are ready."
EXPIRED_CODE_CLI = "That code expired. Run `yasbc cloud auth` again when you are ready."
BUSY_MESSAGE = "Something else is still running. Wait for it to finish and try again."
EMPTY_BACKUPS = "No cloud backup snapshots found."
BACKUPS_UNAVAILABLE = "Your backups are not available on this plan."

UNLIMITED = -1
"""What the server sends for a plan limit that does not apply."""

NOTE_MAX_LENGTH = 100
"""The server rejects anything longer, so trim before sending rather than after."""

SAFETY_KEEP = 5
"""Pre-restore copies kept on disk. Older ones are deleted."""

BAR_PROCESS_NAME = "yasb.exe"
BAR_COMMAND_TIMEOUT_S = 30
BAR_STOP_TIMEOUT_S = 15.0

CLOUD_DIR_NAME = "cloud"
SESSION_FILE = "session.bin"
VAULT_FILE = "vault.bin"
LOCK_FILE = "cloud.lock"
SAFETY_DIR = "safety"

# Plain JSON, not DPAPI: nothing in either is secret, and a file you can open in an editor is
# worth a lot when a user reports that their rules are not being applied. Kept apart because
# the state file is rewritten after every backup and the settings a few times a year.
SETTINGS_FILE = "settings.json"
AUTOBACKUP_STATE_FILE = "autobackup.json"

APP_LOG_FILE = "cloud.log"
CLI_LOG_FILE = "cloud-cli.log"
TASK_LOG_FILE = "cloud-task.log"
LOG_MAX_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 5

SETTINGS_VERSION = 1
MAX_EXCLUDE_RULES = 100
MAX_EXCLUDE_RULE_LENGTH = 200
"""Bounds on what the settings page will store. A rule list is a handful of globs; anything
approaching these is a mistake or a paste accident."""

TASK_NAME = "YASB Cloud Automatic Backup"
"""Name of the scheduled task. Shown to the user in Task Scheduler, so it reads as English
rather than an identifier."""

TASK_INTERVAL_MINUTES = 5
"""How often the check runs, not how often a backup happens. A backup needs the folder to
have changed and then gone quiet, so an editing session produces one, roughly this long
after the last save."""
# Apart so a backup can clear its leftovers without touching a running restore.
UPLOAD_DIR = "tmp/upload"
DOWNLOAD_DIR = "tmp/download"

# Labels, not secrets. Changing one makes the file it guards unreadable, hence the suffix.
DPAPI_SESSION_ENTROPY = b"yasb.cloud.session.v1"
DPAPI_VAULT_ENTROPY = b"yasb.cloud.vault.v1"
