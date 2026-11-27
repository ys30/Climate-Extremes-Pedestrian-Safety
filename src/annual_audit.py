import json,csv,hashlib
from pathlib import Path
from collections import Counter
def main():
    rows=[]; monthly=[]
    expected={int(r["month"]):r for r in csv.DictReader(open("results/era5_2022_monthly_verified.csv"))}
    for month in range(1,13):
        p=Path(f"cohorts/cohort_{month:02}.json")
        data=json.loads(p.read_text())
        assert all(r["month"]==month for r in data)
        e=expected[month]
        for code,label in [("1","urban"),("2","rural")]:
            g=[r for r in data if str(r["rural"])==code]
            assert len(g)==int(e[label+"_n"])
            assert sum(r["ksi"] for r in g)==int(e[label+"_ksi"])
        monthly.append(dict(month=month,n=len(data),ksi=sum(r["ksi"] for r in data),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        rows.extend(data)
    assert len(rows)==19322 and sum(r["ksi"] for r in rows)==5905
    assert len({(r["collision"],r["casualty"]) for r in rows})==len(rows)
    assert all(r["ksi"] in (0,1) and 0<=r["distance_km"]<=25 for r in rows)
    out=dict(n=len(rows),ksi=sum(r["ksi"] for r in rows),unique_collisions=len({r["collision"] for r in rows}),monthly=monthly,area=dict(Counter(str(r["rural"]) for r in rows)),note="Reconstructed from public STATS19 and cached ERA5; aggregate audit only.")
    Path("annual_audit.json").write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
