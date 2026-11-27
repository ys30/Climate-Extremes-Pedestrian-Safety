import json
from pathlib import Path
from collections import Counter
from climate_baseline_c0 import GRIDS
rows=[r for p in sorted(Path("cohorts").glob("cohort_*.json")) for r in json.loads(p.read_text())]
assert len(rows)==19322
def grid(r):return (r["grid_lat"],r["grid_lon"])
counts={code:Counter(grid(r) for r in rows if str(r["rural"])==code) for code in ("1","2")}
selected=list(GRIDS);new=[]
for code in ("1","2","2"):
    g=next(g for g,n in sorted(counts[code].items(),key=lambda x:(-x[1],x[0])) if g not in selected)
    selected.append(g);new.append(g)
Path("climate_grids.json").write_text(json.dumps(selected))
print(json.dumps({"candidate_grids":len(set(map(grid,rows))),"new_grids":new,"selected":selected,"covered":sum(grid(r) in selected for r in rows),"by_grid":[{"grid":g,"urban":counts["1"][g],"rural":counts["2"][g]} for g in selected]},indent=2))
