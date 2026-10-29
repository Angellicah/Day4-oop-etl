"""Runs the ETL pipelines described in PIPELINES and prints an execution summary."""
from __future__ import annotations

from typing import Any

from etl.errors import ETLError
from etl.extractors import APIExtractor, CSVExtractor
from etl.loader import DataLoader
from etl.pipeline import Pipeline, RunSummary
from etl.transformer import DataTransformer

# ---- configuration -------------------------------------------------------

EXTRACTORS = {"csv": CSVExtractor, "api": APIExtractor}

ORDER_COLUMNS = [
    "order_id", "order_date", "customer_email", "city",
    "product_sku", "quantity", "unit_price_kes", "line_total_kes", "status",
]

ORDERS_TRANSFORMER = {
    "required_fields": [
        "order_id", "order_date", "customer_email", "city",
        "product_sku", "quantity", "unit_price_kes", "status",
    ],
    "email_field": "customer_email",
    "positive_fields": ["quantity", "unit_price_kes"],
    "unique_field": "order_id",
    "int_fields": ["quantity", "unit_price_kes"],
    "text_rules": {
        "customer_email": "lower",
        "city": "title",
        "product_sku": "upper",
        "status": "upper",
    },
    "computed_fields": {"line_total_kes": lambda r: r["quantity"] * r["unit_price_kes"]},
    "output_fields": ORDER_COLUMNS,
}

USER_COLUMNS = ["id", "name", "username", "email", "phone", "website", "city", "company"]

USERS_TRANSFORMER = {
    "required_fields": ["id", "name", "email"],
    "email_field": "email",
    "positive_fields": ["id"],
    "unique_field": "id",
    "int_fields": ["id"],
    "text_rules": {"email": "lower"},
    "computed_fields": {
        "city": lambda r: r["address"]["city"],      # flatten nested API fields
        "company": lambda r: r["company"]["name"],
    },
    "output_fields": USER_COLUMNS,
}

PIPELINES: list[dict[str, Any]] = [
    {
        "name": "orders",
        "extractor": {"type": "csv", "source": "data/orders.csv"},
        "transformer": ORDERS_TRANSFORMER,
        "output": "output/orders_clean.csv",
        "columns": ORDER_COLUMNS,
        "rejected_output": "output/orders_rejected.csv",
    },
    {
        "name": "users",
        "extractor": {"type": "api", "source": "https://jsonplaceholder.typicode.com/users"},
        "transformer": USERS_TRANSFORMER,
        "output": "output/users_clean.csv",
        "columns": USER_COLUMNS,
    },
    {   # demo: a source that does not exist
        "name": "missing-file-demo",
        "extractor": {"type": "csv", "source": "data/does_not_exist.csv"},
        "transformer": ORDERS_TRANSFORMER,
        "output": "output/missing_file_demo.csv",
    },
    {   # demo: a URL that cannot be reached
        "name": "invalid-url-demo",
        "extractor": {"type": "api", "source": "https://not-a-real-site.invalid/users", "timeout": 5},
        "transformer": USERS_TRANSFORMER,
        "output": "output/invalid_url_demo.csv",
    },
]

# ---- wiring --------------------------------------------------------------


def build_pipeline(config: dict[str, Any]) -> Pipeline:
    """Turn one config entry into a ready-to-run Pipeline."""
    extractor_settings = dict(config["extractor"])
    extractor_class = EXTRACTORS[extractor_settings.pop("type")]
    extractor = extractor_class(name=config["name"], **extractor_settings)

    transformer = DataTransformer(**config["transformer"])
    loader = DataLoader(config["output"], fieldnames=config.get("columns"))

    rejected_loader = None
    if "rejected_output" in config:
        rejected_loader = DataLoader(config["rejected_output"])

    return Pipeline(extractor, transformer, loader, rejected_loader, name=config["name"])


def main() -> None:
    summaries: list[RunSummary] = []
    for config in PIPELINES:
        try:
            summaries.append(build_pipeline(config).run())
        except ETLError as exc:  # e.g. a bad output extension in the config
            summaries.append(
                RunSummary(
                    source=config["name"],
                    extractor=config["extractor"]["type"],
                    destination=config["output"],
                    errors=[str(exc)],
                )
            )

    print("=== ETL execution summary ===")
    for summary in summaries:
        print(summary.report())
        print()

    failed = sum(1 for s in summaries if s.status == "FAILED")
    print(f"Total pipelines: {len(summaries)} | Succeeded: {len(summaries) - failed} | Failed: {failed}")


if __name__ == "__main__":
    main()