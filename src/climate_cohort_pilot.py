import json
from pathlib import Path
from collections import Counter,defaultdict
from statistics import mean
baseline=json.loads(Path("climate_c1.json").read_text())
assert not baseline["errors"]
lookup={(tuple(g["grid"]),s["month"],s["utc_hour"]):s for g in baseline["grids"] for s in g["statistics"]}
rows=[r for p in sorted(Path("cohorts").glob("cohort_*.json")) for r in json.loads(p.read_text())]
assert len(rows)==19322
groups=defaultdict(list)
for r in rows:
    g=(r["grid_lat"],r["grid_lon"])
    s=lookup.get((g,r["utc_month"],r["utc_hour"]))
    if s is None:continue
    t=s["temperature_2m"];w=s["wind_speed_10m"];p=s["wet_p95_mm"]
    wet=r["precipitation_1h"]>=0.1-1e-9
    z=dict(ksi=r["ksi"],anomaly=r["temperature"]-t["mean"],hot=r["temperature"]>t["p95"],cold=r["temperature"]<t["p05"],wind=r["wind"]>w["p95"],precip=(wet and r["precipitation_1h"]>p) if p is not None else None)
    groups[str(r["rural"])].append(z)
    groups["all"].append(z)
out={"reference":"1991-2020","cohort_n":len(rows),"covered":len(groups["all"]),"groups":{},"note":"Purposively selected grid pilot; not representative. Strict greater-than thresholds; no spatial extrapolation; total precipitation includes snow."}
for code,g in groups.items():
    if not g:continue
    out["groups"][code]={"n":len(g),"ksi":sum(r["ksi"] for r in g),"mean_temperature_anomaly":mean(r["anomaly"] for r in g),"hot":sum(r["hot"] for r in g),"cold":sum(r["cold"] for r in g),"wind":sum(r["wind"] for r in g),"extreme_precip":sum(r["precip"] is True for r in g),"precip_threshold_available":sum(r["precip"] is not None for r in g),"compound_hot_wind":sum(r["hot"] and r["wind"] for r in g)}
Path("climate_cohort_pilot.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
