"""Validates and normalises records."""
from __future__ import annotations

import math
import re
from typing import Any, Callable

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TEXT_RULES: dict[str, Callable[[str], str]] = {
    "title": str.title,
    "upper": str.upper,
    "lower": str.lower,
}


def _is_missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _to_number(value: Any) -> float | None:
    """Parse '1,150' / ' 4 ' / 12 into a float, or None if it isn't a real number."""
    try:
        number = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


class DataTransformer:
    """Validates and normalises records. Keeps the rejected ones and why."""

    def __init__(
        self,
        required_fields: list[str],
        email_field: str | None = None,
        positive_fields: list[str] | None = None,
        unique_field: str | None = None,
        int_fields: list[str] | None = None,
        text_rules: dict[str, str] | None = None,
        computed_fields: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        output_fields: list[str] | None = None,
    ) -> None:
        self.required_fields = required_fields
        self.email_field = email_field
        self.positive_fields = positive_fields or []
        self.unique_field = unique_field
        self.int_fields = int_fields or []
        self.text_rules = text_rules or {}
        self.computed_fields = computed_fields or {}
        self.output_fields = output_fields
        self.rejected: list[dict[str, Any]] = []  # filled in by transform()

    def validate(self, record: dict[str, Any]) -> list[str]:
        """Return the reasons this record is invalid (empty list means valid)."""
        reasons: list[str] = []

        for field in self.required_fields:
            if _is_missing(record.get(field)):
                reasons.append(f"missing {field}")

        if self.email_field and not _is_missing(record.get(self.email_field)):
            if not EMAIL_PATTERN.match(str(record[self.email_field]).strip()):
                reasons.append(f"invalid {self.email_field}")

        for field in self.positive_fields:
            value = record.get(field)
            if _is_missing(value):
                continue  # already reported as missing (if it's required)
            number = _to_number(value)
            if number is None:
                reasons.append(f"{field} not a number")
            elif number <= 0:
                reasons.append(f"{field} not positive")
            elif field in self.int_fields and number != int(number):
                reasons.append(f"{field} not a whole number")

        return reasons

    def clean(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return a normalised copy of a valid record."""
        # 1. trim and collapse extra spaces in every text value
        cleaned = {
            key: " ".join(value.split()) if isinstance(value, str) else value
            for key, value in record.items()
        }

        # 2. apply text rules (title / upper / lower)
        for field, rule in self.text_rules.items():
            if isinstance(cleaned.get(field), str):
                cleaned[field] = TEXT_RULES[rule](cleaned[field])

        # 3. convert whole-number fields to int
        for field in self.int_fields:
            if field in cleaned:
                cleaned[field] = int(_to_number(cleaned[field]))

        # 4. add derived fields
        for name, func in self.computed_fields.items():
            cleaned[name] = func(cleaned)

        # 5. keep only the output columns, in order
        if self.output_fields:
            cleaned = {field: cleaned.get(field) for field in self.output_fields}
        return cleaned

    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate and clean every record. Rejected ones go to self.rejected with reasons."""
        self.rejected = []
        seen: set[str] = set()
        valid: list[dict[str, Any]] = []

        for record in records:
            reasons = self.validate(record)

            key = None
            if not reasons and self.unique_field:
                key = str(record.get(self.unique_field, "")).strip()
                if key in seen:
                    reasons.append(f"duplicate {self.unique_field}")

            if not reasons:
                try:
                    valid.append(self.clean(record))
                    if key is not None:
                        seen.add(key)
                except (KeyError, TypeError, ValueError) as exc:
                    reasons.append(f"could not clean record ({exc.__class__.__name__})")

            if reasons:
                self.rejected.append({"record": record, "reasons": reasons})

        return valid

    def rejected_rows(self) -> list[dict[str, Any]]:
        """Rejected records as flat rows: id column first, then reasons, then the originals."""
        rows = []
        for item in self.rejected:
            record, key = item["record"], self.unique_field
            row: dict[str, Any] = {}
            if key:
                row[key] = record.get(key, "")
            row["reasons"] = "; ".join(item["reasons"])
            row.update({k: v for k, v in record.items() if k != key})
            rows.append(row)
        return rows