import json, math
from pathlib import Path
from datetime import datetime
import pandas as pd
import statsmodels.formula.api as smf
from match_era5_pilot import cell,fetch,match

def main():
    events=json.loads(Path("work/events.json").read_text())
    weather={}
    rows=[]
    for e in events:
        g=cell(e)
        if g not in weather: weather[g]=fetch(g)[:2]
        r=match(e,*weather[g])
        if r is None: raise ValueError("Missing matched exposure")
        dt=datetime.fromisoformat(e["utc"])
        r.update(collision=e["collision"],casualty=e["casualty"],hour_sin=math.sin(2*math.pi*dt.hour/24),hour_cos=math.cos(2*math.pi*dt.hour/24),weekend=int(dt.weekday()>=5))
        rows.append(r)
    d=pd.DataFrame(rows)
    assert len(d)==1802 and not d.duplicated(["collision","casualty"]).any()
    d=d[d.weather.astype(str).isin(["1","2","4","5"]) & d.rural.astype(str).isin(["1","2"])].copy()
    d["rural_binary"]=(d.rural.astype(str)=="2").astype(int)
    d["police_rain"]=d.weather.astype(str).isin(["2","5"]).astype(int)
    d["era_rain"]=(d.precipitation_1h>=0.1-1e-9).astype(int)
    d["temp5"]=d.temperature/5
    d["wind5"]=d.wind/5
    base="ksi ~ rural_binary + hour_sin + hour_cos + weekend"
    forms={"M0":base,"M1":base+" + police_rain","M2":base+" + era_rain + temp5 + wind5","M3":base+" + police_rain + era_rain + temp5 + wind5","M4_exploratory":base+" + rural_binary * era_rain + temp5 + wind5"}
    result={"n":len(d),"excluded_weather_or_area":1802-len(d),"ksi":int(d.ksi.sum()),"collisions":int(d.collision.nunique()),"cell_counts":d.groupby(["rural_binary","era_rain"]).ksi.agg(["size","sum"]).reset_index().to_dict("records"),"models":{},"limitations":"January only; limited controls; conditional injury severity, not collision incidence; exploratory in-sample fit; collision-clustered covariance; no causal interpretation."}
    for name,formula in forms.items():
        try:
            m=smf.logit(formula,d).fit(disp=False,cov_type="cluster",cov_kwds={"groups":d.collision})
            assert m.nobs==len(d) and m.mle_retvals["converged"]
            ci=m.conf_int()
            pred=m.predict(d)
            result["models"][name]={"formula":formula,"aic":float(m.aic),"brier":float(((pred-d.ksi)**2).mean()),"terms":{k:{"OR":math.exp(v),"lo":math.exp(ci.loc[k,0]),"hi":math.exp(ci.loc[k,1])} for k,v in m.params.items()}}
        except Exception as exc:result["models"][name]={"error":repr(exc)}
    Path("january_models.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False))
    assert all("error" not in r for r in result["models"].values()),"At least one exploratory model failed"
if __name__=="__main__":main()
