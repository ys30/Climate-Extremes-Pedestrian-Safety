import csv,json,math
from collections import Counter
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from audit import Links,get,CATALOG,source,read,audit,key

def main():
    p=Links();p.feed(get(CATALOG).decode("utf-8"))
    c,cm=read(source(p.urls,2022,"collision"));s,sm=read(source(p.urls,2022,"casualty"))
    annual=audit(c,s)
    assert annual["pedestrian_casualties"]==19327,"Annual source differs from verified baseline"
    lookup={key(r):r for r in c}
    events=[];excluded=Counter();jan=0
    for r in s:
        if r["casualty_type"].strip()!="0":continue
        a=lookup[key(r)]
        try: day=datetime.strptime(a["date"],"%d/%m/%Y")
        except ValueError: day=datetime.strptime(a["date"],"%Y-%m-%d")
        if day.month!=1:continue
        jan+=1
        try:
            t=datetime.strptime(a["time"],"%H:%M").time()
            ts=datetime.combine(day,t,ZoneInfo("Europe/London")).astimezone(timezone.utc)
            lat,lon=float(a["latitude"]),float(a["longitude"])
            if not (49<=lat<=61 and -9<=lon<=3):raise ValueError("Outside GB")
            if r["casualty_severity"] not in {"1","2","3"}:raise ValueError("Unknown severity")
        except (ValueError,TypeError):excluded["invalid_coordinates_time_or_severity"]+=1;continue
        grid=(round(lat*10)/10,round(lon*10)/10)
        events.append(dict(collision=key(r),casualty=r["casualty_reference"],utc=ts.isoformat(),lat=lat,lon=lon,grid=grid,ksi=int(r["casualty_severity"] in {"1","2"}),weather=a.get("weather_conditions"),rural=a.get("urban_or_rural_area")))
    assert len(events)+sum(excluded.values())==jan
    cells=Counter(tuple(r["grid"]) for r in events)
    out=Path("work");out.mkdir(exist_ok=True)
    (out/"events.json").write_text(json.dumps(events))
    result=dict(source_collision=cm,source_casualty=sm,january_raw=jan,january_eligible=len(events),excluded=dict(excluded),unique_collisions=len({r["collision"] for r in events}),candidate_cells=len(cells),urban_rural=dict(Counter(r["rural"] for r in events)),ksi=sum(r["ksi"] for r in events),note="Rounded 0.1 degree cells are planning approximations, not verified ERA5-Land grid matches.")
    Path("pilot_manifest.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
