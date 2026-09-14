"""Error types for YASB Cloud."""


class CloudError(Exception):
    """Base for every YASB Cloud failure."""


class Cancelled(CloudError):
    """The user stopped the operation. Not a failure, so nothing reports it."""


class CryptoError(CloudError):
    """A cryptographic operation failed."""


class IntegrityError(CryptoError):
    """Authentication tag mismatch: modified, truncated, or the wrong key."""


class FormatError(CryptoError):
    """A snapshot blob is malformed or an unsupported format version."""


class SnapshotError(CloudError):
    """A snapshot could not be collected from the configuration directory."""


class QuotaExceededError(SnapshotError):
    """The snapshot would exceed a plan limit. Raised before any expensive work."""


class RestoreError(CloudError):
    """A restore could not be completed."""


class UnsafePathError(RestoreError):
    """An archive entry tried to write outside the target directory. Aborts the restore."""
