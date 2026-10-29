"""Extractors: one class per kind of data source."""
from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from typing import Any

import requests

from etl.errors import ExtractionError


class DataExtractor(ABC):
    """Common interface for every data source."""

    def __init__(self, source: str, name: str | None = None) -> None:
        self.source = source
        self.name = name or source  # fall back to the source if no name given

    @abstractmethod
    def extract(self) -> list[dict[str, Any]]:
        """Return the raw records from the source."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, source={self.source!r})"


class CSVExtractor(DataExtractor):
    """Reads records from a CSV file."""

    def extract(self) -> list[dict[str, Any]]:
        try:
            with open(self.source, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ExtractionError(f"CSV file is empty: {self.source}")
                return list(reader)
        except FileNotFoundError as exc:
            raise ExtractionError(f"File not found: {self.source}") from exc
        except PermissionError as exc:
            raise ExtractionError(f"No permission to read: {self.source}") from exc
        except (csv.Error, UnicodeDecodeError) as exc:
            raise ExtractionError(f"Could not parse CSV {self.source}: {exc}") from exc
        
class APIExtractor(DataExtractor):
    """Reads records from a JSON HTTP endpoint."""

    def __init__(self, source: str, name: str | None = None, timeout: float = 10.0) -> None:
        super().__init__(source, name)
        self.timeout = timeout

    def __repr__(self) -> str:
        # overrides DataExtractor.__repr__ to show API-specific settings
        return f"{self.__class__.__name__}(name={self.name!r}, url={self.source!r}, timeout={self.timeout})"

    def extract(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(self.source, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout as exc:
            raise ExtractionError(f"Request timed out after {self.timeout}s: {self.source}") from exc
        except requests.exceptions.HTTPError as exc:
            raise ExtractionError(f"HTTP error from {self.source}: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ExtractionError(f"Could not reach {self.source}: {exc}") from exc
        except ValueError as exc:  # response wasn't valid JSON
            raise ExtractionError(f"Response from {self.source} was not valid JSON") from exc

        if not isinstance(data, list):
            raise ExtractionError(f"Expected a JSON list from {self.source}, got {type(data).__name__}")
        return data
        