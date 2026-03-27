"""Package exceptions."""


class SmartLocatorError(Exception):
    """Base package error."""


class MissingAPIKeyError(SmartLocatorError):
    """Raised when no API key is available for OpenAI requests."""
