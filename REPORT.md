# ETL performance report

## Project overview

The pipeline reads e-commerce CSV events, discards malformed timestamps, invalid or negative prices, and empty SKUs, enriches surviving records from a product catalogue, and writes daily revenue and event counts per SKU in deterministic date/SKU order. Unknown catalogue SKUs are retained with category `unknown`.

The reproducible full dataset contained 1,000,000 source rows, a 500-product catalogue, and 45,000 final daily SKU groups. The generator used seed `20261104`.

## Baseline and optimizations

The baseline materializes all input events, parses each timestamp with `datetime.strptime`, scans the catalogue list for every event, and uses separate full passes for group initialization, revenue, and event counts. It deliberately repeats lookup and aggregation work.

The optimized Python engine streams `csv.reader` rows, uses dictionary catalogue lookups, caches parsed date components, validates timestamps with ISO parsers, and updates a dictionary aggregation incrementally. The Polars engine lazily scans CSV, parses and filters in vectorized expressions, groups, joins the catalogue, and sorts the result.

Profiling showed timestamp parsing and per-row overhead dominated Python processing. Replacing `DictReader` with `csv.reader` and caching the repeating calendar date reduced Python runtime from the first optimized attempt's median of 76.521 seconds to 39.256 seconds in the final three-run set. Only the final implementation values below are used for target evaluation.

## Benchmark method and actual measurements

The benchmark ran each engine three times on the generated million-row file. Each run was timed with `time.perf_counter`; peak Python allocation was measured with `tracemalloc`. Reported values are medians. The baseline run outputs were recorded as each run completed before the benchmark process was interrupted during its first optimized repetition; the optimized and Polars runs were then completed with the same benchmark harness and the recorded baseline results. Result CSVs were compared row by row after parsing revenue as decimal, and both optimized outputs matched the baseline.

| Engine | Median wall time | Median peak allocation | Speed-up vs baseline | Memory reduction vs baseline |
|---|---:|---:|---:|---:|
| Baseline | 466.040 s | 735,129,242 bytes (700.9 MiB) | 1.00× | 1.00× |
| Optimized Python | 39.256 s | 25,820,340 bytes (24.6 MiB) | 11.87× | 28.47× |
| Polars | 2.251 s | 20,703,572 bytes (19.7 MiB) | 207.00× | 35.51× |

Speed-up is baseline median seconds divided by engine median seconds. Memory reduction is baseline median `tracemalloc` peak divided by engine median peak. Both assignment targets (at least 10× faster and 3× lower peak memory) were achieved by the optimized Python engine; Polars also exceeded both targets.

Individual run values and calculations are in [`profiles/benchmark.json`](profiles/benchmark.json) and [`profiles/benchmark.csv`](profiles/benchmark.csv). `tracemalloc` tracks Python allocations and does not capture all native Polars memory or total process RSS. For Linux RSS, use `/usr/bin/time -v uv run python -m etl_pipeline.cli data/events.csv data/catalogue.json data/rss-report.csv`; this host was Windows, so that Linux command was documented but not executed.

## Profiling evidence

cProfile binary profiles and human-readable summaries are saved under `profiles/`. The baseline and optimized Python sample profiles use the same reproducible 10,000-row subset; separate full-data profiles are also saved for optimized Python and Polars. py-spy 0.4.3 was installed, but its flame-graph command failed with `Failed to find python version from target process` on this Python 3.14.7 installation. No py-spy flame graphs were generated. Try again with a py-spy-supported interpreter if SVG flame graphs are required.

## Validation

- `pytest`: **9 passed**, including the 10,000-row baseline/optimized equivalence test and Hypothesis property test.
- `mypy --strict etl_pipeline`: **passed**, no issues in 4 source files.
- Million-row baseline, optimized Python, and Polars output equivalence: **passed** (45,000 output rows each).
- Generated CSV/JSON data and run outputs are ignored by Git; benchmark and profile evidence remain trackable.

## Conclusion

On this Windows host with Python 3.14.7, the optimized Python implementation achieved an 11.87× speed-up and 28.47× reduction in measured Python allocation peak compared with the intentionally inefficient baseline. Polars achieved 207.00× speed-up and 35.51× allocation reduction. The 10× speed and 3× memory objectives are met. RSS measurements and py-spy flame graphs remain unavailable from this Windows/Python 3.14.7 profiling setup.
