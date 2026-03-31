"""BusMinder exception hierarchy."""

from __future__ import annotations


class BusMinderError(Exception):
    """Base exception for all BusMinder errors."""


class BusMinderConnectionError(BusMinderError):
    """Raised when the BusMinder service cannot be reached."""


class BusMinderParseError(BusMinderError):
    """Raised when BusMinder response data cannot be parsed."""
