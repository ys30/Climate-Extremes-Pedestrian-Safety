import csv, hashlib, io, json, re, urllib.request
from pathlib import Path
from collections import defaultdict, Counter
from audit import key
from audit import Links, get, CATALOG, audit
YEARS=set(range(2016,2021))
def extract(kind):
    parser=Links(); parser.feed(get(CATALOG).decode("utf-8"))
    pattern=r"[-_]"+kind+r"s?[-_]1979[-_]latest[-_]published[-_]year\.csv(?:\?|$)"
    urls=sorted(set(u for u in parser.urls if re.search(pattern,u,re.I)))
    if len(urls)!=1: raise ValueError(f"Missing/ambiguous cumulative {kind}: {urls}")
    url=urls[0]; sha=hashlib.sha256(); rows=defaultdict(list)
    class HashReader(io.RawIOBase):
        def readable(self): return True
        def readinto(self,b):
            chunk=response.read(len(b)); sha.update(chunk); b[:len(chunk)]=chunk; return len(chunk)
    with urllib.request.urlopen(url,timeout=180) as response:
        reader=csv.DictReader(io.TextIOWrapper(io.BufferedReader(HashReader()),encoding="utf-8-sig",newline=""))
        for raw in reader:
            row={k.strip().lower():v for k,v in raw.items()}
            year=int(row.get("collision_year") or row.get("accident_year") or (row.get("collision_index") or row.get("accident_index"))[:4])
            if year in YEARS: rows[year].append(row)
    return rows,{"url":url,"sha256":sha.hexdigest(),"scope":"complete cumulative CSV"}
def main():
    coll,cm=extract("collision")
    cas,sm=extract("casualt(?:y|ies)")
    out=Path("results");out.mkdir(exist_ok=True)
    blocked=[]
    for year in sorted(YEARS):
        c,s=coll[year],cas[year]
        groups=defaultdict(list)
        for row in s: groups[(key(row),row.get("casualty_reference",""))].append(row)
        missing=[r for (a,b),rs in groups.items() if not a.strip() or not b.strip() for r in rs]
        dup=[rs for k,rs in groups.items() if all(v.strip() for v in k) and len(rs)>1]
        exact=[rs for rs in dup if all(r==rs[0] for r in rs)]
        conflict=[rs for rs in dup if not all(r==rs[0] for r in rs)]
        diag={"year":year,"raw_casualties":len(s),"raw_pedestrians":sum(r.get("casualty_type")=="0" for r in s),"missing_key_rows":len(missing),"duplicate_groups":len(dup),"exact_duplicate_groups":len(exact),"conflicting_groups":len(conflict),"duplicate_excess_rows":sum(len(rs)-1 for rs in dup),"missing_key_types":dict(Counter(r.get("casualty_type") for r in missing)),"conflict_types":dict(Counter(r.get("casualty_type") for rs in conflict for r in rs)),"conflicting_fields":dict(Counter(k for rs in conflict for k in rs[0] if len({r.get(k) for r in rs})>1))}
        (out/f"diagnostic-{year}.json").write_text(json.dumps(diag,indent=2))
        print(json.dumps(diag),flush=True)
        # Quarantine only groups demonstrably outside the pedestrian cohort.
        if any(r.get("casualty_type","").strip() not in {"1","2","9"} for r in missing+[r for rs in conflict for r in rs]):
            blocked.append(year); continue
        raw_count=len(s)
        s=[r for r in s if r.get("casualty_type","").strip()=="0"]
        # Strict audit below checks all pedestrian keys, including exact duplicates.
        result={"year":year,"collision":dict(cm,rows=len(c),columns=list(c[0])),"casualty":dict(sm,rows=raw_count,pedestrian_rows=len(s),columns=list(s[0])),"audit":audit(c,s),"severity_note":"Recorded severity; not adjusted"}
        (out/f"{year}.json").write_text(json.dumps(result,indent=2))
        print(year,json.dumps(result["audit"]))
    if blocked: raise ValueError(f"Unresolved historical casualty keys: {blocked}")
if __name__=="__main__": main()
