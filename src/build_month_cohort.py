import argparse,json,hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter
import match_era5_pilot as m

def main():
    p=argparse.ArgumentParser();p.add_argument("--month",type=int,required=True);a=p.parse_args()
    def offline(*args,**kwargs):raise RuntimeError("Cache miss: network disabled during cohort reconstruction")
    m.urllib.request.urlopen=offline
    events=json.loads(Path("work/events.json").read_text())
    cache={};rows=[]
    for e in events:
        g=m.cell(e)
        if g not in cache:cache[g]=m.fetch(g,a.month)[:2]
        d,idx=cache[g];r=m.match(e,d,idx)
        assert r is not None
        dt=datetime.fromisoformat(e["utc"])
        r.update(e["controls"])
        r.update(collision=e["collision"],casualty=e["casualty"],month=a.month,utc_month=dt.month,utc_hour=dt.hour,local_hour=dt.astimezone(__import__("zoneinfo").ZoneInfo("Europe/London")).hour,weekend=int(dt.astimezone(__import__("zoneinfo").ZoneInfo("Europe/London")).weekday()>=5),grid_lat=d["latitude"],grid_lon=d["longitude"])
        rows.append(r)
    assert len({(r["collision"],r["casualty"]) for r in rows})==len(rows)
    import csv
    expected=list(csv.DictReader(open("results/era5_2022_monthly_verified.csv")))
    expected=next(r for r in expected if int(r["month"])==a.month)
    for code,label in [("1","urban"),("2","rural")]:
        group=[r for r in rows if str(r["rural"])==code]
        assert len(group)==int(expected[label+"_n"])
        assert sum(r["ksi"] for r in group)==int(expected[label+"_ksi"])
        assert sum(r["precipitation_1h"]>=0.1 for r in group)==int(expected[label+"_wet_1h"])
    path=Path(f"cohort_{a.month:02}.json")
    path.write_text(json.dumps(rows,allow_nan=False,separators=(",",":")))
    print(json.dumps(dict(month=a.month,n=len(rows),ksi=sum(r["ksi"] for r in rows),grids=len(cache),sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
if __name__=="__main__":main()
