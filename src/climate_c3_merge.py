import json
from pathlib import Path
from collections import Counter
plan=json.loads(Path("c3_plan.json").read_text())
old=json.loads(Path("climate_c1.json").read_text())
assert not old["errors"] and len(old["grids"])==10
grids=list(old["grids"])
for i in range(20):
    pair=json.loads(Path(f"pairs/c3_pair_{i:02}.json").read_text())
    assert {tuple(g["grid"]) for g in pair}=={tuple(g) for g in plan["new"][2*i:2*i+2]}
    grids.extend(pair)
assert len(grids)==50 and {tuple(g["grid"]) for g in grids}=={tuple(g) for g in plan["all"]}
for g in grids:
    assert g["complete_years"]==30
    s=g["statistics"]
    assert len(s)==288 and len({(r["month"],r["utc_hour"]) for r in s})==288
    assert sum(r["n"] for r in s)==262992
    assert all(r["temperature_2m"]["p05"]<=r["temperature_2m"]["p95"] and 0<=r["wet_fraction"]<=1 for r in s)
old["grids"]=grids
Path("climate_c3.json").write_text(json.dumps(old,allow_nan=False))
print(json.dumps({"grids":len(grids),"hours":sum(r["n"] for g in grids for r in g["statistics"]),"groups":sum(len(g["statistics"]) for g in grids)}))
