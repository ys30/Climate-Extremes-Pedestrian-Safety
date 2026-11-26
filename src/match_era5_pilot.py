import json, math, time, urllib.request, urllib.parse, argparse, statistics
from collections import Counter, defaultdict
from datetime import datetime,timedelta
from pathlib import Path
from weather_probe_openmeteo import BASE,VARS,UNITS

def cell(e): return (round(e["lat"]*4)/4,round(e["lon"]*4)/4)
def distance(a,b,c,d):
    x=math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(x)))
def fetch(g):
    params=dict(latitude=g[0],longitude=g[1],start_date="2021-12-30",end_date="2022-01-31",hourly=",".join(VARS),models="era5",timezone="GMT",wind_speed_unit="ms",temperature_unit="celsius",precipitation_unit="mm",cell_selection="nearest",elevation="nan")
    url=BASE+"?"+urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=45) as r:d=json.load(r)
            break
        except (OSError,ValueError):
            if attempt==2:raise
            time.sleep(3*(attempt+1))
    h=d["hourly"]; ts=h["time"]
    expected=[(datetime(2021,12,30)+timedelta(hours=i)).isoformat(timespec="minutes") for i in range(33*24)]
    assert ts==expected and d["utc_offset_seconds"]==0
    for v in VARS:
        assert d["hourly_units"][v]==UNITS[v] and len(h[v])==len(ts)
    return d,{t:i for i,t in enumerate(ts)},url

def match(e,d,idx):
    h=d["hourly"]; stamp=datetime.fromisoformat(e["utc"]).replace(minute=0,second=0,microsecond=0)
    i=idx[stamp.replace(tzinfo=None).isoformat(timespec="minutes")]
    assert i>=23
    vals={v:h[v][i] for v in VARS}
    rain=h["precipitation"][i-23:i+1]
    if any(x is None or not math.isfinite(x) for x in list(vals.values())+rain):return None
    if min(rain)<0 or vals["wind_speed_10m"]<0:return None
    dist=distance(e["lat"],e["lon"],d["latitude"],d["longitude"])
    if dist>25:return None
    return dict(rural=e["rural"],weather=e["weather"],ksi=e["ksi"],temperature=vals["temperature_2m"],wind=vals["wind_speed_10m"],dew=vals["dew_point_2m"],distance_km=dist,**{f"precipitation_{n}h":math.fsum(rain[-n:]) for n in (1,3,6,24)})
def main():
    p=argparse.ArgumentParser(); p.add_argument('--per-group',type=int,default=5); p.add_argument('--all',action='store_true'); args=p.parse_args()
    assert 1<=args.per_group<=25
    events=json.loads(Path("work/events.json").read_text())
    by=defaultdict(list)
    for e in events:by[cell(e)].append(e)
    selected=[]
    for code in ("1","2"):
        ranked=sorted(by,key=lambda g:(-sum(e["rural"]==code for e in by[g]),g))
        selected.extend([g for g in ranked if g not in selected and any(e["rural"]==code for e in by[g])][:args.per_group])
    if args.all: selected=sorted(by)
    output=[]; errors=[]; matched=[]
    for g in selected:
        try:
            d,idx,url=fetch(g)
            rows=[match(e,d,idx) for e in by[g]]
            valid=[r for r in rows if r is not None]; matched.extend(valid)
            output.append(dict(requested=g,returned=[d["latitude"],d["longitude"]],url=url,eligible=len(rows),matched=len(valid)))
        except Exception as exc:errors.append(dict(cell=g,error=repr(exc)))
        time.sleep(1)
    result=dict(model="era5",candidate_cells=len(by),selected_cells=len(selected),eligible=sum(len(by[g]) for g in selected),matched=len(matched),cells=output,errors=errors,groups=dict(Counter(str(r["rural"]) for r in matched)),note="Engineering pilot; selected subset is not representative. Police weather is instantaneous categorical reporting; preceding-hour precipitation is not a gold standard. Hourly precipitation ends at floor(event UTC hour).")
    result["descriptive_by_group"]={}
    for code in sorted({str(r["rural"]) for r in matched}):
        rows=[r for r in matched if str(r["rural"])==code]
        result["descriptive_by_group"][code]={"n":len(rows),"ksi":sum(r["ksi"] for r in rows),"mean_temperature":statistics.mean(r["temperature"] for r in rows),"mean_wind":statistics.mean(r["wind"] for r in rows),"rain_ge_0_1mm_1h":sum(r["precipitation_1h"]>=0.1 for r in rows),"rain_ge_0_1mm_3h":sum(r["precipitation_3h"]>=0.1 for r in rows),"police_weather_by_rain_1h": [{"weather":w,"rain_ge_0_1mm":wet,"n":n} for (w,wet),n in sorted(Counter((str(r["weather"]),r["precipitation_1h"]>=0.1) for r in rows).items())]}
    result["agreement_sensitivity"]=[]
    for group in ("all","1","2"):
        for window in (1,3,6,24):
            for threshold in (0.1,0.2,0.5,1.0):
                rows=[r for r in matched if (group=="all" or str(r["rural"])==group) and str(r["weather"]) in {"1","2","4","5"}]
                a,b,c,d=[sum((str(r["weather"]) in {"2","5"})==p and (r[f"precipitation_{window}h"]>=threshold-1e-9)==w for r in rows) for p,w in [(False,False),(False,True),(True,False),(True,True)]]
                n=a+b+c+d
                po=(a+d)/n if n else None
                pe=((a+b)*(a+c)+(c+d)*(b+d))/n**2 if n else None
                result["agreement_sensitivity"].append(dict(group=group,window=window,threshold=threshold,n=n,tn=a,fp=b,fn=c,tp=d,agreement=po,kappa=(po-pe)/(1-pe) if n and pe<1 else None,positive_agreement=2*d/(2*d+b+c) if 2*d+b+c else None))
    if matched:
        result["ranges"]={k:[min(r[k] for r in matched),max(r[k] for r in matched)] for k in ("temperature","wind","distance_km","precipitation_1h","precipitation_3h","precipitation_6h","precipitation_24h")}
    Path("match_summary.json").write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in {"cells","agreement_sensitivity"}},indent=2))
    assert len(selected)==(len(by) if args.all else 2*args.per_group) and not errors and len(matched)==result["eligible"],"Pilot completeness gate failed"
if __name__=="__main__":main()
