import json, urllib.request, urllib.parse, math, time
from datetime import datetime,timedelta
from pathlib import Path
BASE="https://archive-api.open-meteo.com/v1/archive"
VARS=["temperature_2m","precipitation","wind_speed_10m","dew_point_2m"]
LOCATIONS={"London":(51.5,-0.13),"Edinburgh":(55.95,-3.19),"Rural_Wales":(52.45,-3.55)}
MODELS=["era5_land","era5"]
UNITS={"temperature_2m":"°C","dew_point_2m":"°C","wind_speed_10m":"m/s","precipitation":"mm"}
def main():
    results=[]
    expected=[(datetime(2021,12,30)+timedelta(hours=i)).isoformat(timespec="minutes") for i in range(120)]
    for model in MODELS:
        for name,(lat,lon) in LOCATIONS.items():
            params=dict(latitude=lat,longitude=lon,start_date="2021-12-30",end_date="2022-01-03",hourly=",".join(VARS),models=model,timezone="GMT",wind_speed_unit="ms",temperature_unit="celsius",precipitation_unit="mm",cell_selection="nearest",elevation="nan")
            url=BASE+"?"+urllib.parse.urlencode(params)
            rec=dict(model=model,name=name,url=url,requested=[lat,lon],passed=False)
            try:
                with urllib.request.urlopen(url,timeout=60) as r: d=json.load(r)
                h=d["hourly"]; units=d["hourly_units"]; ts=h["time"]
                rec.update(returned=[d["latitude"],d["longitude"]],units=units,hourly=h,time_complete=ts==expected,utc_offset=d["utc_offset_seconds"])
                diagnostics={}
                for v in VARS:
                    vals=h.get(v,[])
                    missing=[i for i,x in enumerate(vals) if x is None or not isinstance(x,(int,float)) or not math.isfinite(x)]
                    valid=[x for x in vals if isinstance(x,(int,float)) and math.isfinite(x)]
                    diagnostics[v]=dict(n=len(vals),missing=len(missing),missing_times=[ts[i] for i in missing if i<len(ts)],minimum=min(valid) if valid else None,maximum=max(valid) if valid else None,missing_in_target=sum(i>=24 for i in missing),unit_ok=units.get(v)==UNITS[v])
                rec["diagnostics"]=diagnostics
                rec["passed"]=ts==expected and d["utc_offset_seconds"]==0 and all(z["n"]==120 and z["missing_in_target"]==0 and z["unit_ok"] for z in diagnostics.values()) and all(diagnostics[v]["minimum"] is not None and diagnostics[v]["minimum"]>=0 for v in ["precipitation","wind_speed_10m"])
                print(json.dumps({k:v for k,v in rec.items() if k!="hourly"},ensure_ascii=False),flush=True)
            except Exception as e:
                rec["error"]=repr(e); print(json.dumps(rec),flush=True)
            results.append(rec)
            Path("probe_openmeteo.json").write_text(json.dumps(results,indent=2))
            time.sleep(1)
    passed=[m for m in MODELS if all(r["passed"] for r in results if r["model"]==m)]
    print("Complete products:",passed,flush=True)
    Path("probe_summary.json").write_text(json.dumps({"complete_products":passed,"policy":"Never mix products or fill missing precipitation with zero. First 24h are diagnostic padding; target includes Dec 31 for lag windows."},indent=2))
    if not passed: raise RuntimeError("No complete weather product; inspect saved diagnostics")
if __name__=="__main__": main()
