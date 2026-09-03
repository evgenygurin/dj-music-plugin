from __future__ import annotations


class StemError(RuntimeError):
    """Base error for stem separation."""


class StemBackendUnavailableError(StemError):
    """A requested backend is not installed or cannot run on this platform."""


class StemModelLoadError(StemError):
    """The selected separation model could not be loaded."""


class StemInferenceError(StemError):
    """Model inference failed."""


class AudioInputError(StemError):
    """Input audio cannot be decoded or normalized."""


class StemOutputValidationError(StemError):
    """A produced stem failed integrity validation."""


class StemEncodingError(StemError):
    """A stem could not be encoded."""


class StemCacheError(StemError):
    """Stem cache contains invalid or incomplete artifacts."""
