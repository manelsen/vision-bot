class VisionBotError(Exception):
    """Base exception for the vision bot"""
    pass

class transientAPIError(VisionBotError):
    """Errors that can be retried (timeouts, 500s)"""
    pass

class PermanentAPIError(VisionBotError):
    """Errors that should NOT be retried (Invalid Key, 404)"""
    pass

class FileTooLargeError(VisionBotError):
    """File exceeds size limits"""
    pass

class UnsupportedFormatError(VisionBotError):
    """Format not supported by the model"""
    pass

class NoContextError(VisionBotError):
    """User asked a question without sending a file first"""
    pass
