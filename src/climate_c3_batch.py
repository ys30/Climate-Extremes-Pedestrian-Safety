import argparse,json,hashlib,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict
import numpy as np
from climate_batch_probe import params,url,VARIABLES,UNITS

def main():
    p=argparse.ArgumentParser();p.add_argument("--pair",type=int,required=True);a=p.parse_args()
    plan=json.loads(Path("c3_plan.json").read_text())
    grids=[tuple(g) for g in plan["new"][2*a.pair:2*a.pair+2]]
    assert len(grids)==2
    root=Path("c3_cache");root.mkdir(exist_ok=True)
    groups={g:defaultdict(lambda:defaultdict(list)) for g in grids};sources=[]
    for year in range(1991,2021,2):
        u=url(dict(params(",".join(str(g[0]) for g in grids),",".join(str(g[1]) for g in grids),f"{year}-01-01",f"{year+1}-12-31"),elevation="nan,nan"))
        path=root/(hashlib.sha256(u.encode()).hexdigest()+".json")
        cached=path.exists()
        if cached:raw=path.read_bytes()
        else:
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(u,timeout=120) as r:raw=r.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code<500 or attempt==2:raise
                    time.sleep(15*(attempt+1))
                except OSError:
                    if attempt==2:raise
                    time.sleep(15*(attempt+1))
        data=json.loads(raw);assert isinstance(data,list) and len(data)==2
        got={(float(d["latitude"]),float(d["longitude"])):d for d in data};assert set(got)==set(grids)
        start=datetime(year,1,1);end=datetime(year+2,1,1)
        expected=[(start+timedelta(hours=i)).isoformat(timespec="minutes") for i in range(int((end-start).total_seconds()/3600))]
        for g,d in got.items():
            h=d["hourly"];assert d["utc_offset_seconds"]==0 and h["time"]==expected
            for v in VARIABLES:
                arr=np.asarray(h[v],dtype=float)
                assert d["hourly_units"][v]==UNITS[v] and arr.shape==(len(expected),) and np.isfinite(arr).all()
                if v!="temperature_2m":assert arr.min()>=0
            for i,t in enumerate(expected):
                k=(int(t[5:7]),int(t[11:13]))
                for v in VARIABLES:groups[g][k][v].append(h[v][i])
        if not cached:
            tmp=path.with_suffix(".tmp");tmp.write_bytes(raw);tmp.replace(path)
        sources.append(dict(years=[year,year+1],url=u,sha256=hashlib.sha256(raw).hexdigest(),hours_per_grid=len(expected)))
        print(json.dumps(dict(pair=a.pair,year=year,cached=cached,hours_per_grid=len(expected))),flush=True)
        if not cached:time.sleep(3)
    out=[]
    for g,group in groups.items():
        stats=[]
        for (month,hour),vals in sorted(group.items()):
            rec=dict(month=month,utc_hour=hour,n=len(vals["temperature_2m"]))
            for v in VARIABLES:
                x=np.asarray(vals[v])
                if v=="precipitation":
                    wet=x[x>=0.1-1e-9];rec.update(wet_fraction=float(len(wet)/len(x)),wet_n=len(wet),wet_p95_mm=float(np.quantile(wet,.95)) if len(wet)>=30 else None)
                else:rec[v]=dict(mean=float(x.mean()),p05=float(np.quantile(x,.05)),p95=float(np.quantile(x,.95)))
            stats.append(rec)
        assert len(stats)==288 and sum(r["n"] for r in stats)==262992
        out.append(dict(grid=g,complete_years=30,sources=sources,statistics=stats))
    Path(f"c3_pair_{a.pair:02}.json").write_text(json.dumps(out,allow_nan=False))
if __name__=="__main__":main()
