"""Shared benchmark exceptions."""

class IoABenchError(Exception):
    """Base class for expected benchmark failures."""


class ConfigurationError(IoABenchError):
    """Raised when local benchmark configuration is invalid."""


class ContractError(IoABenchError):
    """Raised when a document violates a shipped contract."""


class ProviderTransientError(IoABenchError):
    """A provider failure that may succeed after bounded retry."""


class ProviderPermanentError(IoABenchError):
    """A provider failure that should not be retried as-is."""


class ProviderRequestUnresolved(ProviderPermanentError):
    """A possibly executed request with unknown outcome; retries can duplicate billing."""

    category = "REQUEST_UNRESOLVED"


class ModelUnsupportedError(ProviderPermanentError):
    """The requested exact model is not available from the provider."""
