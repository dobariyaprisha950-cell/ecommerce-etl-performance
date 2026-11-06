# E-commerce ETL performance

Reproducible benchmark project comparing an intentionally inefficient Python baseline with streaming Python and optional Polars implementations. Valid events have a parseable `YYYY-MM-DD HH:MM:SS` timestamp, a nonempty SKU, and a numeric nonnegative price. Unknown catalogue SKUs are retained with category `unknown`. Reports group daily revenue and event count by SKU, sorted by date and SKU.

## Setup and run

```sh
# If needed, install uv from a PowerShell terminal outside the project venv.
pip install --user uv
uv sync --extra dev --extra polars
uv run python generate_data.py --rows 1000000 --out data
uv run python pipeline_slow.py data/events.csv data/catalogue.json data/report-baseline.csv
uv run pipeline data/events.csv data/catalogue.json data/report.csv
uv run pipeline data/events.csv data/catalogue.json data/report-polars.csv --engine polars
uv run python bench.py --data data --runs 3 --profile
uv run pytest
uv run mypy etl_pipeline
```

The `polars` extra is optional; omit `--extra polars` for the standard-library fallback. Generated data and run CSVs are ignored by git, while benchmark results and profile artifacts are kept under `profiles/`. Benchmark measures Python allocation peak via `tracemalloc`; for process RSS on Linux, use `/usr/bin/time -v uv run python -m etl_pipeline.cli data/events.csv data/catalogue.json data/report.csv`. `bench.py --profile` saves cProfile artifacts and text summaries. py-spy is included in the dev extra. On Windows, the venv launcher was not detected by py-spy 0.4.3; profiling through the base Python executable with `--idle` succeeded. The 1-million-row SVGs are `profiles/baseline_flamegraph.svg`, `profiles/optimized_flamegraph.svg`, and `profiles/polars_flamegraph.svg`; see REPORT.md for the exact commands and observations.

## Project files

`pipeline_slow.py` provides the list-loading baseline; `etl_pipeline/core.py` streams and aggregates; `etl_pipeline/vectorized.py` is the optional Polars engine; `generate_data.py` creates fixed-seed test/benchmark inputs; `bench.py` records medians and ratios; `tests/` contains behavior and equivalence checks.
