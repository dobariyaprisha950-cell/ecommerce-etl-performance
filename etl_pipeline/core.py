"""Streaming, standard-library ETL implementation."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import TextIO, Mapping

OUTPUT_FIELDS = ["date", "sku", "category", "revenue", "event_count"]


@lru_cache(maxsize=32768)
def parse_day(value: str) -> str | None:
    """Parse/cache the repeating ISO calendar date component."""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def parse_date(value: str) -> str | None:
    """Validate a timestamp and return its cached daily key."""
    if len(value) != 19 or value[10] != " " or value[13] != ":" or value[16] != ":":
        return None
    try:
        time.fromisoformat(value[11:])
    except ValueError:
        return None
    return parse_day(value[:10])


def read_catalogue(path: Path) -> dict[str, str]:
    """Read SKU to category mappings from the generated catalogue."""
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    products = raw["products"] if isinstance(raw, dict) else raw
    return {str(item["sku"]): str(item.get("category", "unknown")) for item in products}


def clean_row(row: Mapping[str, str | None]) -> tuple[str, str, float] | None:
    """Return normalized daily key and price, or discard an invalid event."""
    sku = (row.get("sku") or "").strip()
    if not sku:
        return None
    date = parse_date(row.get("timestamp") or "")
    if date is None:
        return None
    try:
        price = float(row.get("price") or "")
    except ValueError:
        return None
    if price < 0:
        return None
    return date, sku, price


def aggregate_stream(handle: TextIO, catalogue: dict[str, str]) -> list[dict[str, str | int | float]]:
    """Stream CSV records and aggregate incrementally."""
    totals: dict[tuple[str, str], list[float | int]] = defaultdict(lambda: [0.0, 0])
    reader = csv.reader(handle)
    next(reader, None)
    for row in reader:
        if len(row) < 5:
            continue
        sku = row[3].strip()
        if not sku:
            continue
        date = parse_date(row[0])
        if date is None:
            continue
        try:
            price = float(row[4])
        except ValueError:
            continue
        if price < 0:
            continue
        value = totals[(date, sku)]
        value[0] = float(value[0]) + price
        value[1] = int(value[1]) + 1
    result: list[dict[str, str | int | float]] = []
    for (date, sku), (revenue, count) in totals.items():
        result.append({"date": date, "sku": sku, "category": catalogue.get(sku, "unknown"),
                       "revenue": round(float(revenue), 2), "event_count": int(count)})
    return sorted(result, key=lambda item: (str(item["date"]), str(item["sku"])))


def run_python(input_path: Path, catalogue_path: Path, output_path: Path) -> list[dict[str, str | int | float]]:
    """Execute streaming Python ETL and write deterministic CSV output."""
    catalogue = read_catalogue(catalogue_path)
    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = aggregate_stream(handle, catalogue)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows
