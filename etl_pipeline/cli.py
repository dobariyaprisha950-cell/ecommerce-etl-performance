"""Command line entry point."""
from __future__ import annotations
import argparse
from pathlib import Path
from etl_pipeline.core import run_python

def main() -> None:
    parser=argparse.ArgumentParser(description="Run e-commerce ETL")
    parser.add_argument("input",type=Path); parser.add_argument("catalogue",type=Path); parser.add_argument("output",type=Path)
    parser.add_argument("--engine",choices=("python","polars"),default="python")
    args=parser.parse_args()
    if args.engine=="polars":
        from etl_pipeline.vectorized import run_polars
        run_polars(args.input,args.catalogue,args.output)
    else: run_python(args.input,args.catalogue,args.output)

if __name__ == "__main__": main()
