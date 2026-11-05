from __future__ import annotations
import csv, json
from pathlib import Path
import pytest
from hypothesis import given, strategies as st
from etl_pipeline.core import clean_row, run_python
from pipeline_slow import run_baseline
from generate_data import generate

@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path, Path]:
    data=tmp_path/"events.csv"; cat=tmp_path/"catalogue.json"; out=tmp_path/"out.csv"
    data.write_text("timestamp,user_id,event,sku,price\n2025-01-01 00:00:00,u,purchase,A,2\n",encoding="utf-8")
    cat.write_text(json.dumps({"products":[{"sku":"A","category":"x"}]}),encoding="utf-8")
    return data,cat,out

def test_equivalence_10000(tmp_path: Path) -> None:
    data=tmp_path/"data"; generate(10000,data); a=tmp_path/"a.csv"; b=tmp_path/"b.csv"
    assert run_baseline(data/"events.csv",data/"catalogue.json",a)==run_python(data/"events.csv",data/"catalogue.json",b)

@given(st.text(),st.text(),st.text())
def test_clean_rows_valid(timestamp: str, sku: str, price: str) -> None:
    result=clean_row({"timestamp":timestamp,"sku":sku,"price":price})
    if result is not None: assert result[1] and result[2]>=0

def test_empty_csv(files: tuple[Path,Path,Path]) -> None:
    data,cat,out=files; data.write_text("timestamp,user_id,event,sku,price\n",encoding="utf-8"); assert run_python(data,cat,out)==[]

@pytest.mark.parametrize("row",["bad,u,purchase,A,2","2025-01-01 00:00:00,u,purchase,A,x","2025-01-01 00:00:00,u,purchase,A,-1","2025-01-01 00:00:00,u,purchase,,2"])
def test_invalid_records_dropped(files: tuple[Path,Path,Path], row: str) -> None:
    data,cat,out=files; data.write_text("timestamp,user_id,event,sku,price\n"+row+"\n",encoding="utf-8"); assert run_python(data,cat,out)==[]

def test_unknown_sku(files: tuple[Path,Path,Path]) -> None:
    data,cat,out=files; data.write_text("timestamp,user_id,event,sku,price\n2025-01-01 00:00:00,u,purchase,Z,1\n",encoding="utf-8"); assert run_python(data,cat,out)[0]["category"]=="unknown"

def test_duplicate_aggregation(files: tuple[Path,Path,Path]) -> None:
    data,cat,out=files; data.write_text("timestamp,user_id,event,sku,price\n"+"2025-01-01 00:00:00,u,purchase,A,2\n"*3,encoding="utf-8"); row=run_python(data,cat,out)[0]; assert row["revenue"]==6 and row["event_count"]==3
