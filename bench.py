"""Benchmark all engines and save cProfile evidence and comparison results."""
from __future__ import annotations

import argparse
import cProfile
import csv
import json
import pstats
import statistics
import time
import tracemalloc
from decimal import Decimal
from pathlib import Path
from typing import Callable

from etl_pipeline.core import run_python
from etl_pipeline.vectorized import run_polars
from pipeline_slow import run_baseline

Engine = Callable[[Path, Path, Path], list[dict[str, str | int | float]]]


def measure(engine: Engine, input_path: Path, catalogue: Path, output: Path) -> tuple[float, int, list[dict[str, str | int | float]]]:
    tracemalloc.start()
    start = time.perf_counter()
    rows = engine(input_path, catalogue, output)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed, peak, rows


def save_profile(engine: Engine, name: str, input_path: Path, catalogue: Path, output: Path) -> None:
    profile_path = Path("profiles") / f"{name}.prof"
    profiler = cProfile.Profile()
    profiler.enable()
    engine(input_path, catalogue, output)
    profiler.disable()
    profiler.dump_stats(str(profile_path))
    with profile_path.with_suffix(".txt").open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumulative").print_stats(40)


def normalized_csv(path: Path) -> list[tuple[str, str, str, Decimal, int]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [(row["date"], row["sku"], row["category"], Decimal(row["revenue"]), int(row["event_count"]))
                for row in csv.DictReader(handle)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--engines", nargs="+", choices=("baseline", "optimized_python", "polars"), default=("baseline", "optimized_python", "polars"))
    parser.add_argument("--baseline-results", type=Path, help="Reuse saved baseline measurements when benchmarking only optimized engines")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    args.data.mkdir(parents=True, exist_ok=True)
    Path("profiles").mkdir(parents=True, exist_ok=True)
    input_path, catalogue = args.data / "events.csv", args.data / "catalogue.json"
    all_engines: dict[str, Engine] = {"baseline": run_baseline, "optimized_python": run_python, "polars": run_polars}
    engines = {name: all_engines[name] for name in args.engines}
    records: dict[str, object] = {}
    medians: dict[str, tuple[float, int]] = {}

    if args.baseline_results:
        prior = json.loads(args.baseline_results.read_text(encoding="utf-8"))
        baseline_times = prior["wall_seconds_each_run"]
        baseline_peaks = prior["tracemalloc_peak_bytes_each_run"]
        medians["baseline"] = (statistics.median(baseline_times), int(statistics.median(baseline_peaks)))
        records["baseline"] = prior
        if "baseline" not in engines:
            engines = {name: engine for name, engine in engines.items() if name != "baseline"}

    baseline_output = args.data / "report-baseline.csv"
    expected_csv = normalized_csv(baseline_output) if baseline_output.exists() else None

    for name, engine in engines.items():
        times: list[float] = []
        peaks: list[int] = []
        output = args.data / f"report-{name}.csv"
        for run_number in range(args.runs):
            seconds, peak, rows = measure(engine, input_path, catalogue, output)
            if name == "baseline":
                expected_csv = normalized_csv(output)
            elif expected_csv is not None and normalized_csv(output) != expected_csv:
                raise RuntimeError(f"{name} output differs from baseline")
            times.append(seconds)
            peaks.append(peak)
            print(f"{name} run {run_number + 1}/{args.runs}: {seconds:.3f}s, tracemalloc peak {peak} bytes", flush=True)
        median_time, median_peak = statistics.median(times), int(statistics.median(peaks))
        medians[name] = (median_time, median_peak)
        records[name] = {"wall_seconds_each_run": times, "median_wall_seconds": median_time,
                         "tracemalloc_peak_bytes_each_run": peaks, "median_tracemalloc_peak_bytes": median_peak,
                         "runs": args.runs, "output_rows": len(rows)}

    if "baseline" not in medians:
        raise RuntimeError("Baseline comparison requires the baseline engine or --baseline-results")
    base_time, base_memory = medians["baseline"]
    records["comparisons"] = {
        name: {"speedup_vs_baseline": base_time / seconds,
               "memory_reduction_vs_baseline": base_memory / memory}
        for name, (seconds, memory) in medians.items() if name != "baseline"
    }
    records["output_equivalence"] = "passed: normalized CSV rows match baseline" if expected_csv is not None else "not checked"
    if args.profile:
        for name, engine in engines.items():
            save_profile(engine, name, input_path, catalogue, args.data / f"profile-{name}.csv")
        records["profiles"] = "cProfile .prof and human-readable .txt saved for selected engines"
    json_path = Path("profiles") / "benchmark.json"
    json_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    with (Path("profiles") / "benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["engine", "median_wall_seconds", "median_tracemalloc_peak_bytes", "speedup_vs_baseline", "memory_reduction_vs_baseline"])
        for name, (seconds, memory) in medians.items():
            comparison = records["comparisons"].get(name, {}) if isinstance(records["comparisons"], dict) else {}
            writer.writerow([name, seconds, memory, comparison.get("speedup_vs_baseline", 1.0), comparison.get("memory_reduction_vs_baseline", 1.0)])
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
