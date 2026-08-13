"""Domain-level exceptions shown as friendly GUI messages."""

from __future__ import annotations


class TextLabError(Exception):
    """Base exception for expected application errors."""


class EmptyInputError(TextLabError):
    """Raised when the user submits empty text."""


class ResourceNotFoundError(TextLabError):
    """Raised when a bundled model/resource cannot be found."""


class DependencyUnavailableError(TextLabError):
    """Raised when a required Python dependency is missing."""

