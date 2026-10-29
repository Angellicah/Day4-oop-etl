"""Pipeline orchestration and run summaries."""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from etl.errors import ETLError
from etl.extractors import DataExtractor
from etl.loader import DataLoader
from etl.transformer import DataTransformer


@dataclass
class RunSummary:
    """Collects the numbers printed at the end of a pipeline run."""

    source: str                 # the pipeline's name
    extractor: str = ""         # extractor class name, e.g. CSVExtractor
    destination: str = ""       # where the clean output was written
    extracted: int = 0
    valid: int = 0
    rejected: int = 0
    loaded: int = 0
    reject_reasons: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def status(self) -> str:
        if self.errors:
            return "FAILED"      # a stage (source or loading) broke
        if self.rejected:
            return "PARTIAL"     # finished, but some records were rejected
        return "SUCCESS"

    def report(self) -> str:
        lines = [
            f"Pipeline: {self.source}  ({self.extractor} -> {self.destination})",
            f"  Extracted : {self.extracted}",
            f"  Valid     : {self.valid}",
            f"  Rejected  : {self.rejected}",
        ]
        for reason, count in sorted(self.reject_reasons.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"    - {reason}: {count}")
        lines += [
            f"  Loaded    : {self.loaded}",
            f"  Duration  : {self.duration:.2f}s",
            f"  Status    : {self.status}",
        ]
        for error in self.errors:
            lines.append(f"  Error     : {error}")
        return "\n".join(lines)


class Pipeline:
    """Runs extractor -> transformer -> loader. Must not care which extractor it was given."""

    def __init__(
        self,
        extractor: DataExtractor,
        transformer: DataTransformer,
        loader: DataLoader,
        rejected_loader: DataLoader | None = None,
        name: str | None = None,
    ) -> None:
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader
        self.rejected_loader = rejected_loader
        self.name = name or extractor.name

    def run(self) -> RunSummary:
        summary = RunSummary(
            source=self.name,
            extractor=type(self.extractor).__name__,
            destination=str(self.loader.destination),
        )
        start = time.perf_counter()
        try:
            raw = self.extractor.extract()          # polymorphic call: CSV, API, anything
            summary.extracted = len(raw)

            valid = self.transformer.transform(raw)
            summary.valid = len(valid)
            summary.rejected = len(self.transformer.rejected)
            reasons = Counter(r for item in self.transformer.rejected for r in item["reasons"])
            summary.reject_reasons = dict(reasons)

            summary.loaded = self.loader.load(valid)
            if self.rejected_loader:
                self.rejected_loader.load(self.transformer.rejected_rows())
        except ETLError as exc:                      # a known problem with this pipeline
            summary.errors.append(str(exc))
        except Exception as exc:                     # anything unexpected still stays contained
            summary.errors.append(f"Unexpected {type(exc).__name__}: {exc}")
        finally:
            summary.duration = time.perf_counter() - start
        return summary