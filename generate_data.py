"""Generate deterministic synthetic events and a realistic SKU catalogue."""
from __future__ import annotations
import argparse,csv,json,random
from datetime import datetime,timedelta
from pathlib import Path

def generate(rows: int,out: Path,seed: int=20261104)->tuple[Path,Path]:
    rng=random.Random(seed); out.mkdir(parents=True,exist_ok=True)
    products=[{"sku":f"SKU{i:05d}","category":["apparel","home","electronics","books"][i%4],"base_price":round(rng.uniform(4,500),2)} for i in range(1,501)]
    cat=out/"catalogue.json"; cat.write_text(json.dumps({"products":products},indent=2)+"\n",encoding="utf-8")
    start=datetime(2025,1,1)
    with (out/"events.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["timestamp","user_id","event","sku","price"])
        for i in range(rows):
            sku=str(rng.choice(products)["sku"]); price: float|str=round(rng.uniform(1,500),2)
            ts=(start+timedelta(seconds=rng.randrange(90*86400))).strftime("%Y-%m-%d %H:%M:%S")
            if i%9973==0: ts="malformed-time"
            if i%4999==0: price=-float(price)
            if i%1999==0: sku=""
            if i%1237==0 and i>0: price="bad-price"
            w.writerow([ts,f"U{rng.randrange(1,100001):06d}",rng.choice(["view","add_to_cart","purchase"]),sku,price])
    return out/"events.csv",cat

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--rows",type=int,default=1_000_000); p.add_argument("--out",type=Path,default=Path("data")); p.add_argument("--seed",type=int,default=20261104); a=p.parse_args(); generate(a.rows,a.out,a.seed)
if __name__=="__main__": main()
