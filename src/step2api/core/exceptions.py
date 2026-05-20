"""Custom exceptions for Step2API."""


class Step2APIError(Exception):
    """Base exception."""
    status_code: int = 500


class AuthenticationError(Step2APIError):
    """Authentication failed."""
    status_code = 401


class TooManyRequestsError(Step2APIError):
    """Rate limit exceeded."""
    status_code = 429


class UpstreamError(Step2APIError):
    """Error from upstream StepFun API."""
    status_code = 502


class InvalidRequestError(Step2APIError):
    """Invalid client request."""
    status_code = 400


class SessionError(Step2APIError):
    """Chat session error."""
    status_code = 500
