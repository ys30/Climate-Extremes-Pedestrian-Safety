import json,csv
from pathlib import Path
from collections import Counter
rows=[r for p in sorted(Path("cohorts").glob("cohort_*.json")) for r in json.loads(p.read_text())]
assert len(rows)==19322
def grid(r):return (r["grid_lat"],r["grid_lon"])
counts={code:Counter(grid(r) for r in rows if str(r["rural"])==code) for code in ("1","2")}
selected=[(51.5,-0.25),(56.0,-3.25),(52.5,-3.5),(51.5,0.0),(51.25,0.5),(53.25,-1.25)]
all_grids=set(map(grid,rows))
assert len(all_grids)==432 and set(selected)<=all_grids
new=[g for g,n in sorted(counts["2"].items(),key=lambda x:(-x[1],x[0])) if g not in selected][:4]
assert len(new)==4
selected+=new
Path("climate_grids.json").write_text(json.dumps(selected))
with open("grid_inventory.csv","w") as f:
    w=csv.writer(f);w.writerow(["lat","lon","urban","rural","selected"])
    for g in sorted(all_grids):w.writerow([*g,counts["1"][g],counts["2"][g],int(g in selected)])
print(json.dumps({"candidate_grids":len(all_grids),"new_grids":new,"selected":selected,"covered":sum(grid(r) in selected for r in rows),"by_grid":[{"grid":g,"urban":counts["1"][g],"rural":counts["2"][g]} for g in selected]},indent=2))
