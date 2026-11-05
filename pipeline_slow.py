"""Intentionally inefficient baseline for comparison."""
from __future__ import annotations
import csv, json
from datetime import datetime
from pathlib import Path
from typing import Any
from etl_pipeline.core import OUTPUT_FIELDS

def run_baseline(input_path: Path, catalogue_path: Path, output_path: Path) -> list[dict[str, str | int | float]]:
    with catalogue_path.open(encoding="utf-8") as f: catalog: list[dict[str,str]]=json.load(f)["products"]
    with input_path.open(newline="",encoding="utf-8") as f: events=list(csv.DictReader(f))
    valid: list[dict[str,Any]]=[]
    for event in events:
        sku=event.get("sku","").strip()
        try: date=datetime.strptime(event.get("timestamp",""),"%Y-%m-%d %H:%M:%S").date().isoformat(); price=float(event.get("price",""))
        except ValueError: continue
        if not sku or price<0: continue
        category="unknown"
        for product in catalog:
            if product["sku"]==sku: category=product.get("category","unknown"); break
        valid.append({"date":date,"sku":sku,"category":category,"price":price})
    # Deliberately do separate full passes for group initialization, revenue,
    # and count. This repeats key searches and aggregation work without making
    # the million-row benchmark intractable through a quadratic nested scan.
    groups: dict[tuple[str,str],list[float|int]]={}
    for item in valid: groups.setdefault((str(item["date"]),str(item["sku"])),[0.0,0])
    for item in valid:
        value=groups[(str(item["date"]),str(item["sku"]))]; value[0]=float(value[0])+float(item["price"])
    for item in valid:
        value=groups[(str(item["date"]),str(item["sku"]))]; value[1]=int(value[1])+1
    output: list[dict[str,str|int|float]]=[]
    for (date,sku),(revenue,count) in groups.items():
        category="unknown"
        for product in catalog:
            if product["sku"]==sku: category=product.get("category","unknown"); break
        output.append({"date":date,"sku":sku,"category":category,"revenue":round(float(revenue),2),"event_count":int(count)})
    output.sort(key=lambda x:(str(x["date"]),str(x["sku"])))
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open("w",newline="",encoding="utf-8") as f: writer=csv.DictWriter(f,fieldnames=OUTPUT_FIELDS); writer.writeheader(); writer.writerows(output)
    return output

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("input",type=Path); p.add_argument("catalogue",type=Path); p.add_argument("output",type=Path); a=p.parse_args(); run_baseline(a.input,a.catalogue,a.output)
