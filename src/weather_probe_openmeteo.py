import json, urllib.request, urllib.parse, math
from datetime import datetime,timedelta
from pathlib import Path
BASE="https://archive-api.open-meteo.com/v1/archive"
VARS=["temperature_2m","precipitation","wind_speed_10m","dew_point_2m"]
LOCATIONS={"London":(51.5,-0.13),"Edinburgh":(55.95,-3.19),"Rural_Wales":(52.45,-3.55)}
def main():
    results=[]
    expected=[(datetime(2021,12,31)+timedelta(hours=i)).isoformat(timespec="minutes") for i in range(96)]
    for name,(lat,lon) in LOCATIONS.items():
        params=dict(latitude=lat,longitude=lon,start_date="2021-12-31",end_date="2022-01-03",hourly=",".join(VARS),models="era5_land",timezone="GMT",wind_speed_unit="ms",temperature_unit="celsius",precipitation_unit="mm",cell_selection="nearest",elevation="nan")
        url=BASE+"?"+urllib.parse.urlencode(params)
        with urllib.request.urlopen(url,timeout=60) as r: d=json.load(r)
        h=d["hourly"]; units=d["hourly_units"]
        assert h["time"]==expected and d["utc_offset_seconds"]==0
        assert units["precipitation"]=="mm" and units["wind_speed_10m"]=="m/s" and units["temperature_2m"]=="°C" and units["dew_point_2m"]=="°C",units
        for v in VARS: assert len(h[v])==96 and all(x is not None and math.isfinite(x) for x in h[v]),v
        assert min(h["precipitation"])>=0
        assert min(h["wind_speed_10m"])>=0
        results.append(dict(name=name,requested=[lat,lon],returned=[d["latitude"],d["longitude"]],url=url,units=units,hourly=h,precipitation_note="Preceding hour ending at timestamp per provider; verify against ECMWF before production."))
        print(name, "96 hours", "precipitation mm",sum(h["precipitation"]),flush=True)
    Path("probe_openmeteo.json").write_text(json.dumps(results,indent=2))
if __name__=="__main__": main()
