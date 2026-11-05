"""Optional Polars vectorized implementation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from etl_pipeline.core import OUTPUT_FIELDS

def run_polars(input_path: Path,catalogue_path: Path,output_path: Path)->list[dict[str,str|int|float]]:
    try: import polars as pl
    except ImportError as exc: raise RuntimeError("Install the optional polars extra to use this engine") from exc
    with catalogue_path.open(encoding="utf-8") as f: raw: Any=json.load(f)
    products=raw["products"] if isinstance(raw,dict) else raw
    cat=pl.DataFrame(products).select(pl.col("sku").cast(pl.String),pl.col("category").cast(pl.String)).lazy()
    lazy=pl.scan_csv(input_path,schema_overrides={"timestamp":pl.String,"user_id":pl.String,"event":pl.String,"sku":pl.String,"price":pl.String})
    result=(lazy.with_columns(pl.col("timestamp").str.strptime(pl.Datetime,"%Y-%m-%d %H:%M:%S",strict=False).alias("ts"),pl.col("price").cast(pl.Float64,strict=False).alias("p"),pl.col("sku").str.strip_chars())
        .filter(pl.col("ts").is_not_null()&pl.col("p").is_not_null()&(pl.col("p")>=0)&(pl.col("sku").str.len_chars()>0))
        .with_columns(pl.col("ts").dt.date().cast(pl.String).alias("date"))
        .group_by(["date","sku"]).agg(pl.col("p").sum().round(2).alias("revenue"),pl.len().alias("event_count"))
        .join(cat,on="sku",how="left").with_columns(pl.col("category").fill_null("unknown")).sort(["date","sku"]).select(OUTPUT_FIELDS).collect())
    rows: list[dict[str,str|int|float]]=result.to_dicts(); output_path.parent.mkdir(parents=True,exist_ok=True); result.write_csv(output_path); return rows
