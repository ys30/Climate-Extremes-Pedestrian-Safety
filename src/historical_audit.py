import csv, hashlib, io, json, re, urllib.request
from pathlib import Path
from collections import defaultdict
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
    for year in sorted(YEARS):
        c,s=coll[year],cas[year]
        result={"year":year,"collision":dict(cm,rows=len(c),columns=list(c[0])),"casualty":dict(sm,rows=len(s),columns=list(s[0])),"audit":audit(c,s),"severity_note":"Recorded severity; not adjusted"}
        (out/f"{year}.json").write_text(json.dumps(result,indent=2))
        print(year,json.dumps(result["audit"]))
if __name__=="__main__": main()
