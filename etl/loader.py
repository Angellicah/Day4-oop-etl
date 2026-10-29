"""Loader: writes records to a CSV or JSON file."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from etl.errors import LoadError, UnsupportedFormatError

SUPPORTED_EXTENSIONS = (".csv", ".json")


class DataLoader:
    """Writes transformed records to a destination file (CSV or JSON by extension)."""

    def __init__(self, destination: Path | str, fieldnames: list[str] | None = None) -> None:
        self.destination = Path(destination)
        self.fieldnames = fieldnames  # optional: fixes CSV columns (and header when empty)
        self._writers = {
            ".csv": self._write_csv,
            ".json": self._write_json,
        }
        self.extension = self.destination.suffix.lower()
        if self.extension not in self._writers:
            raise UnsupportedFormatError(
                f"Unsupported output format '{self.extension}' for {self.destination}. "
                f"Use one of: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

    def load(self, records: list[dict[str, Any]]) -> int:
        """Write the records and return how many were written."""
        try:
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            self._writers[self.extension](records)
        except (OSError, ValueError, TypeError) as exc:
            raise LoadError(f"Could not write {self.destination}: {exc}") from exc
        return len(records)

    def _write_csv(self, records: list[dict[str, Any]]) -> None:
        # use the given columns, else every key seen, in first-seen order
        columns = self.fieldnames or list(dict.fromkeys(key for r in records for key in r))
        with open(self.destination, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)

    def _write_json(self, records: list[dict[str, Any]]) -> None:
        with open(self.destination, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)