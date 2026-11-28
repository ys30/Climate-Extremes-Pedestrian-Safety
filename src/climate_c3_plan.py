import csv,json
from pathlib import Path
rows=list(csv.DictReader(open("grid_inventory.csv")))
assert len(rows)==432
for r in rows:
    r["grid"]=(float(r["lat"]),float(r["lon"]))
    for k in ("urban","rural","selected"):r[k]=int(r[k])
assert sum(r["urban"] for r in rows)==16903 and sum(r["rural"] for r in rows)==2419
selected=[r["grid"] for r in rows if r["selected"]]
assert len(selected)==10
new=[]
for i in range(40):
    key="rural" if i%2==0 else "urban"
    r=min((r for r in rows if r["grid"] not in selected and r["grid"] not in new),key=lambda r:(-r[key],r["grid"]))
    new.append(r["grid"])
allg=selected+new
Path("c3_plan.json").write_text(json.dumps({"existing":selected,"new":new,"all":allg},indent=2))
for label,grids in [("existing",selected),("target",allg)]:
    print(json.dumps({"stage":label,"grids":len(grids),"urban":sum(r["urban"] for r in rows if r["grid"] in grids),"rural":sum(r["rural"] for r in rows if r["grid"] in grids)}))
