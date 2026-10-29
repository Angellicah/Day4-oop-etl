# Jumla Logistics ETL Framework

A tiny in-house ETL framework that replaces a dozen copy-pasted scripts. Every data source implements one interface, records are validated and cleaned by one transformer, results are written by one loader, and a pipeline runs them without knowing what kind of source it was handed.

Built for the Squad Python Specialization, Day 4 (Object-Oriented ETL).

## Project structure

```
day4-oop-etl/
├── etl/
│   ├── __init__.py
│   ├── errors.py        # custom exception hierarchy
│   ├── extractors.py    # DataExtractor (ABC), CSVExtractor, APIExtractor
│   ├── transformer.py   # DataTransformer (validate / clean / transform)
│   ├── loader.py        # DataLoader (CSV or JSON by extension)
│   └── pipeline.py      # Pipeline and RunSummary
├── data/orders.csv      # online orders export (25 rows)
├── output/              # generated files
├── main.py              # runs the pipelines from configuration
├── requirements.txt
└── README.md
```

## How to run

Requires Python 3.9 or newer and an internet connection (the users pipeline calls a public API).

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```


`python main.py` runs everything and prints the execution summary.

## What `main.py` runs

| Pipeline | Source | Output |
|---|---|---|
| `orders` | `data/orders.csv` (CSVExtractor) | `output/orders_clean.csv`, `output/orders_rejected.csv` |
| `users` | `https://jsonplaceholder.typicode.com/users` (APIExtractor) | `output/users_clean.csv` |
| `missing-file-demo` | a CSV path that does not exist | none (fails on purpose) |
| `invalid-url-demo` | a URL that cannot be reached | none (fails on purpose) |

The last two pipelines demonstrate that a failing source stops only its own pipeline: the others still run and the failure is reported in the summary.

## Class design

```
DataExtractor (abstract base class)
├── CSVExtractor
└── APIExtractor            overrides __repr__

DataTransformer             validate() / clean() / transform()
DataLoader                  load() -> rows written
Pipeline                    runs extractor -> transformer -> loader
RunSummary                  numbers + report() for one pipeline run

ETLError
├── ExtractionError         a source cannot be read
├── ValidationError         a record failed validation
└── LoadError               a destination cannot be written
    └── UnsupportedFormatError   destination extension is not .csv or .json
```

### Why it is built this way

- **`DataExtractor` is an abstract base class.** It defines the contract (`extract()` returns a list of dicts) and cannot be instantiated directly. Each new source is a new subclass, so adding a source never touches the rest of the framework.
- **Single responsibility.** Extractors only read, `DataTransformer` only validates and cleans, `DataLoader` only writes, `Pipeline` only orchestrates. Fixing a bug in one place fixes it for every source, which was the problem with the old copy-pasted scripts.
- **Polymorphism in `Pipeline`.** `Pipeline.run()` calls `self.extractor.extract()` and nothing else about the source. There are no `isinstance` checks and no `if` statements on the source type. The only place that maps a source type to a class is the `EXTRACTORS` dictionary in `main.py`.
- **Configuration, not hard-coded logic.** `DataTransformer` takes its rules (required fields, email field, positive fields, unique field, text rules, computed fields, output columns) as constructor arguments. Orders and users use the same class with different settings, defined in the `PIPELINES` list in `main.py`.
- **Errors are reported, not fatal.** Bad records are rejected inside `transform()` and the run continues. A broken source raises `ExtractionError` (library errors such as `FileNotFoundError` and `requests` exceptions are converted), and `Pipeline.run()` catches it, so only that pipeline is marked `FAILED`.

### Overridden methods

- `APIExtractor.__repr__` in `etl/extractors.py` overrides `DataExtractor.__repr__` to include the URL and timeout. `CSVExtractor` keeps the inherited version, so the two can be compared:

```
APIExtractor(name='users', url='https://jsonplaceholder.typicode.com/users', timeout=10.0)
CSVExtractor(name='orders', source='data/orders.csv')
```

- `extract()` is declared abstract in `DataExtractor` and implemented differently in `CSVExtractor` and `APIExtractor`.
- `APIExtractor.__init__` extends the parent's `__init__` (via `super()`) to add a `timeout`.

## Validation rules

A record is rejected if any of these apply. Every reason is kept, so one record can have several.

| Rule | Reason text (example) |
|---|---|
| A required field is missing or blank | `missing customer_email` |
| The email field does not look like `name@domain.tld` | `invalid customer_email` |
| A numeric field is not a number | `quantity not a number` |
| A numeric field is zero or negative | `unit_price_kes not positive` |
| A whole-number field has a fraction | `quantity not a whole number` |
| The unique field was already seen (first one wins) | `duplicate order_id` |
| Unexpected shape while cleaning (safety net) | `could not clean record (KeyError)` |

**Orders:** all columns are required; `customer_email` must be a valid email; `quantity` and `unit_price_kes` must be positive whole numbers; `order_id` must be unique.

**Users:** `id`, `name` and `email` are required; `email` must be valid; `id` must be a positive whole number and unique.

### Cleaning (valid records only)

- Leading, trailing and repeated spaces are trimmed.
- City is Title Case, email is lowercase, SKU and status are uppercase.
- `quantity` and `unit_price_kes` become integers (a value like `1,150` becomes `1150`).
- `line_total_kes = quantity * unit_price_kes` is added.
- Users: the nested `address.city` and `company.name` are flattened into `city` and `company`.

### Output files

- `output/orders_clean.csv`: `order_id, order_date, customer_email, city, product_sku, quantity, unit_price_kes, line_total_kes, status`
- `output/orders_rejected.csv`: `order_id, reasons, <the original columns>`; reasons for one record are joined with `; `
- `output/users_clean.csv`: `id, name, username, email, phone, website, city, company`

## Execution summary

Each pipeline prints one block, followed by a total:

```
=== ETL execution summary ===
Pipeline: orders  (CSVExtractor -> output\orders_clean.csv)
  Extracted : 25
  Valid     : 19
  Rejected  : 6
    - duplicate order_id: 1
    - invalid customer_email: 1
    - missing customer_email: 1
    - missing product_sku: 1
    - quantity not a number: 1
    - unit_price_kes not positive: 1
  Loaded    : 19
  Duration  : 0.01s
  Status    : PARTIAL
...
Total pipelines: 4 | Succeeded: 2 | Failed: 2
```

Counts always reconcile: `valid + rejected = extracted`.

## Assumptions

- **Status meaning.** `SUCCESS`: everything passed. `PARTIAL`: the pipeline finished but some records were rejected. `FAILED`: a stage broke (source unreadable, destination unwritable).
- **"Succeeded" in the total line** means not `FAILED`, so a `PARTIAL` pipeline counts as succeeded because it loaded its valid rows.
- **Thousands separators are accepted.** A price written as `"1,150"` is read as 1150 rather than rejected.
- **Duplicates:** the first occurrence of an `order_id` is kept and later ones are rejected. Only valid records register an ID, so an invalid row cannot block a later valid one with the same ID.
- **Not validated:** `order_date` format and the set of allowed `status` values are only checked for presence. Dates are passed through as written.
- **Email check is deliberately simple** (something, `@`, something, a dot, something). It catches obviously broken addresses, not every invalid one.
- **Quantities and prices are whole numbers** (KES, no decimals).
- Files are read and written as UTF-8. CSV output is overwritten on each run.
- The rejected file is only written for pipelines that configure a `rejected_output` (orders). If a pipeline has nothing rejected, the file contains only its header.
- `ValidationError` is part of the exception hierarchy for callers that want to raise on invalid input. The transformer itself collects reasons as strings so that a bad record never stops a run.