"""Custom exceptions for the ETL framework."""


class ETLError(Exception):
    """Base class for every error raised by the framework."""


class ExtractionError(ETLError):
    """Raised when a source cannot be read (missing file, bad URL, bad JSON...)."""


class ValidationError(ETLError):
    """Raised (or collected) when a record fails validation."""

    def __init__(self, reasons: list[str], record: dict | None = None) -> None:
        self.reasons = reasons
        self.record = record
        super().__init__("; ".join(reasons))


class LoadError(ETLError):
    """Raised when results cannot be written to the destination."""


class UnsupportedFormatError(LoadError):
    """Raised at DataLoader construction when the file extension isn't .csv or .json."""