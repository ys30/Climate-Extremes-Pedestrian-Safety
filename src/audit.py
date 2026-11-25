import argparse,csv,hashlib,json,urllib.request,re,io
from html.parser import HTMLParser
from urllib.parse import urljoin
from collections import Counter
from pathlib import Path
CATALOG="https://www.gov.uk/government/statistical-data-sets/road-safety-open-data"
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            href=dict(attrs).get("href","")
            if href: self.urls.append(urljoin(CATALOG,href))
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"STATS19 research audit"}),timeout=120) as r: return r.read()
def source(links,year,kind):
    kinds="(?:collision|accident)s?" if kind=="collision" else "casualt(?:y|ies)"
    matches=sorted(set(u for u in links if re.search(r"[-_]"+kinds+r"[-_]"+str(year)+r"\.csv(?:\?|$)",u,re.I)))
    if len(matches)!=1: raise ValueError(f"Ambiguous/missing official {kind} {year}: {matches}")
    return matches[0]
def read(url):
    b=get(url); reader=csv.DictReader(io.StringIO(b.decode("utf-8-sig")))
    rows=[{k.strip().lower():v for k,v in row.items()} for row in reader]
    if not rows: raise ValueError("Empty input")
    return rows,{"url":url,"sha256":hashlib.sha256(b).hexdigest(),"rows":len(rows),"columns":list(rows[0])}
def key(row):
    for k in ("collision_index","accident_index"):
        if k in row: return row[k]
    raise ValueError("No collision index")
def audit(coll,cas):
    ids=[key(r) for r in coll]; idset=set(ids)
    if "" in idset or len(ids)!=len(idset): raise ValueError("Invalid collision IDs")
    if "casualty_reference" not in cas[0]: raise ValueError("Missing casualty_reference")
    ck=[(key(r),r["casualty_reference"]) for r in cas]
    if any(not a or not b for a,b in ck) or len(set(ck))!=len(ck): raise ValueError("Invalid casualty keys")
    if any(key(r) not in idset for r in cas): raise ValueError("Unmatched casualty collision")
    ped=[r for r in cas if r["casualty_type"].strip()=="0"]
    if not ped: raise ValueError("No pedestrian casualties; check coding")
    severity=Counter(r["casualty_severity"] for r in ped)
    lookup={key(r):r for r in coll}
    missing=Counter(k for r in ped for k in ("date","time","latitude","longitude","weather_conditions","urban_or_rural_area") if lookup[key(r)].get(k,"").strip() in ("","-1"))
    return {"pedestrian_casualties":len(ped),"pedestrian_collisions":len({key(r) for r in ped}),"severity_codes":dict(severity),"ksi_recorded":severity["1"]+severity["2"],"missing_event_fields":dict(missing)}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--year",type=int,required=True);p.add_argument("--out",required=True);a=p.parse_args()
    parser=Links();parser.feed(get(CATALOG).decode("utf-8"))
    coll,cmeta=read(source(parser.urls,a.year,"collision"));cas,smeta=read(source(parser.urls,a.year,"casualty"))
    result={"year":a.year,"collision":cmeta,"casualty":smeta,"audit":audit(coll,cas),"severity_note":"Recorded severity, not DfT adjusted estimates"}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result["audit"],indent=2))
if __name__=="__main__": main()
