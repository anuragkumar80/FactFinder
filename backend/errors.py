"""Exceptions shared by the service layer and the API."""

class InputError(ValueError):
    """The user's input is empty or too long."""

class RateLimited(RuntimeError):
    """Too many live checks from one IP."""

class QuotaExceeded(RuntimeError):
    """Daily TinyFish fetch budget is used up and no cached result exists."""

class CheckFailed(RuntimeError):
    """The live pipeline failed and no cached result exists."""
