import json, math, time, hashlib, calendar, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict
import numpy as np
from weather_probe_openmeteo import BASE,UNITS
GRIDS=[(51.5,-0.25),(56.0,-3.25),(52.5,-3.5)]
VARIABLES=["temperature_2m","precipitation","wind_speed_10m"]
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--grids");p.add_argument("--output",default="climate_c0.json");args=p.parse_args()
    grids=[tuple(g) for g in json.loads(Path(args.grids).read_text())] if args.grids else GRIDS
    assert 1<=len(grids)<=10 and len(set(grids))==len(grids)
    assert all(49<=a<=61 and -9<=b<=3 and a*4==round(a*4) and b*4==round(b*4) for a,b in grids)
    root=Path("climate_cache");root.mkdir(exist_ok=True)
    out=[]; errors=[]
    for lat,lon in grids:
        groups=defaultdict(lambda:defaultdict(list)); sources=[]
        for year in range(1991,2021):
            params=dict(latitude=lat,longitude=lon,start_date=f"{year}-01-01",end_date=f"{year}-12-31",hourly=",".join(VARIABLES),models="era5",timezone="GMT",wind_speed_unit="ms",temperature_unit="celsius",precipitation_unit="mm",cell_selection="nearest",elevation="nan")
            url=BASE+"?"+urllib.parse.urlencode(params)
            path=root/(hashlib.sha256(url.encode()).hexdigest()+".json")
            try:
                if path.exists(): raw=path.read_bytes()
                else:
                    for attempt in range(3):
                        try:
                            with urllib.request.urlopen(url,timeout=120) as r:raw=r.read()
                            break
                        except OSError:
                            if attempt==2:raise
                            time.sleep(15*(attempt+1))
                d=json.loads(raw);h=d["hourly"]
                assert abs(d["latitude"]-lat)<1e-4 and abs(d["longitude"]-lon)<1e-4
                assert d["utc_offset_seconds"]==0
                expected=[(datetime(year,1,1)+timedelta(hours=i)).isoformat(timespec="minutes") for i in range((365+calendar.isleap(year))*24)]
                assert h["time"]==expected
                for v in VARIABLES:
                    assert d["hourly_units"][v]==UNITS[v]
                    arr=np.asarray(h[v],dtype=float)
                    assert arr.shape==(len(expected),) and np.isfinite(arr).all()
                    if v!="temperature_2m":assert arr.min()>=0
                if not path.exists():
                    tmp=path.with_suffix(".tmp");tmp.write_bytes(raw);tmp.replace(path)
                sources.append(dict(year=year,url=url,sha256=hashlib.sha256(raw).hexdigest(),hours=len(expected)))
                for i,t in enumerate(expected):
                    k=(int(t[5:7]),int(t[11:13]))
                    for v in VARIABLES:groups[k][v].append(h[v][i])
                print("validated",lat,lon,year,len(expected),flush=True)
                time.sleep(2)
            except Exception as exc:
                errors.append(dict(grid=[lat,lon],year=year,error=repr(exc)))
                print(errors[-1],flush=True)
                if isinstance(exc,urllib.error.HTTPError) and exc.code==429:break
        stats=[]
        if len(sources)==30:
            for (month,hour),vals in sorted(groups.items()):
                rec=dict(month=month,utc_hour=hour,n=len(vals["temperature_2m"]))
                for v in VARIABLES:
                    a=np.asarray(vals[v])
                    if v=="precipitation":
                        wet=a[a>=0.1-1e-9];rec["wet_fraction"]=float(len(wet)/len(a));rec["wet_n"]=int(len(wet));rec["wet_p95_mm"]=float(np.quantile(wet,.95)) if len(wet)>=30 else None
                    else:
                        rec[v]=dict(mean=float(a.mean()),p05=float(np.quantile(a,.05)),p95=float(np.quantile(a,.95)))
                stats.append(rec)
            assert len(stats)==288 and sum(x["n"] for x in stats)==262992
        out.append(dict(grid=[lat,lon],complete_years=len(sources),sources=sources,statistics=stats))
        Path(args.output).write_text(json.dumps(dict(reference="1991-2020",model="ERA5 via Open-Meteo",conditioning="calendar month and UTC hour",grids=out,errors=errors,precipitation="total precipitation including snow; wet hour >=0.1 mm; minimum 30 wet hours for p95"),indent=2))
    assert not errors and all(len(x["statistics"])==288 for x in out),"Incomplete climatology; no partial normals accepted"
if __name__=="__main__":main()
