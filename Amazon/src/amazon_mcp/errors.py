from sp_api.base.exceptions import (
    SellingApiBadRequestException,
    SellingApiException,
    SellingApiForbiddenException,
    SellingApiRequestThrottledException,
)


def _message(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc) or exc.__class__.__name__


def to_tool_error(exc: Exception) -> dict:
    """Map an exception to a structured, MCP-tool-friendly error dict."""
    if isinstance(exc, RuntimeError):
        return {"error": True, "type": "config_error", "message": str(exc), "retriable": False}
    if isinstance(exc, SellingApiRequestThrottledException):
        return {
            "error": True,
            "type": "rate_limited",
            "message": "Amazon rate-limited this request; wait a moment and retry.",
            "retriable": True,
        }
    if isinstance(exc, SellingApiForbiddenException):
        return {
            "error": True,
            "type": "auth_failed",
            "message": f"Amazon rejected the request (forbidden): {_message(exc)}",
            "retriable": False,
        }
    if isinstance(exc, SellingApiBadRequestException):
        return {
            "error": True,
            "type": "bad_request",
            "message": _message(exc),
            "retriable": False,
        }
    if isinstance(exc, SellingApiException):
        return {
            "error": True,
            "type": "sp_api_error",
            "message": _message(exc),
            "retriable": False,
        }
    return {
        "error": True,
        "type": "unexpected_error",
        "message": str(exc),
        "retriable": False,
    }
