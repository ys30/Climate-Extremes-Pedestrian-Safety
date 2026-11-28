import json, hashlib, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from climate_baseline_c0 import BASE,VARIABLES,UNITS
GRIDS=[(51.5,-0.25),(56.0,-3.25)]
def params(lat,lon,start,end):
    return dict(latitude=lat,longitude=lon,start_date=start,end_date=end,hourly=",".join(VARIABLES),models="era5",timezone="GMT",wind_speed_unit="ms",temperature_unit="celsius",precipitation_unit="mm",cell_selection="nearest",elevation="nan")
def url(p):return BASE+"?"+urllib.parse.urlencode(p)
def reference(g,year):
    u=url(params(*g,f"{year}-01-01",f"{year}-12-31"))
    return json.loads((Path("climate_cache")/(hashlib.sha256(u.encode()).hexdigest()+".json")).read_bytes())
def main():
    out=[]
    for years in [(1999,1999),(1999,2000)]:
        start,end=f"{years[0]}-01-01",f"{years[1]}-12-31"
        u=url(params(",".join(str(g[0]) for g in GRIDS),",".join(str(g[1]) for g in GRIDS),start,end))
        rec={"years":years,"locations":GRIDS,"url":u}
        try:
            refs={g:[reference(g,y) for y in range(years[0],years[1]+1)] for g in GRIDS}
            tic=time.monotonic()
            with urllib.request.urlopen(u,timeout=180) as r:raw=r.read()
            rec.update(seconds=time.monotonic()-tic,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            data=json.loads(raw);assert isinstance(data,list) and len(data)==2
            got={(float(d["latitude"]),float(d["longitude"])):d for d in data}
            assert set(got)==set(GRIDS)
            for g,d in got.items():
                assert d["utc_offset_seconds"]==0
                ref=refs[g];h=d["hourly"]
                assert h["time"]==[t for q in ref for t in q["hourly"]["time"]]
                for v in VARIABLES:
                    assert d["hourly_units"][v]==UNITS[v]
                    a=np.asarray(h[v],dtype=float);b=np.asarray([x for q in ref for x in q["hourly"][v]],dtype=float)
                    assert a.shape==b.shape and np.isfinite(a).all()
                    rec.setdefault("max_abs_difference",{})[str(g)+":"+v]=float(np.max(np.abs(a-b)))
                    assert np.array_equal(a,b), "Batch values differ from annual cache"
            rec["status"]="pass"
        except Exception as e:
            rec.update(status="fail",error=repr(e))
        out.append(rec)
        print(json.dumps(rec),flush=True)
        if rec["status"]!="pass":break
        time.sleep(5)
    Path("batch_probe.json").write_text(json.dumps(out,indent=2))
    assert len(out)==2 and all(r["status"]=="pass" for r in out)
if __name__=="__main__":main()
