import json,math
from collections import Counter
from datetime import datetime
from pathlib import Path
import pandas as pd
import statsmodels.formula.api as smf
from match_era5_pilot import cell,fetch,match

def main():
    events=json.loads(Path("work/events.json").read_text())
    assert len(events)==1802
    audit={k:dict(Counter(str(e["controls"].get(k)) for e in events)) for k in events[0]["controls"]}
    Path("control_codes.json").write_text(json.dumps(audit,indent=2))
    weather={}; rows=[]
    for e in events:
        g=cell(e)
        if g not in weather: weather[g]=fetch(g)[:2]
        r=match(e,*weather[g])
        if r is None: raise ValueError("Missing matched exposure")
        dt=datetime.fromisoformat(e["utc"])
        r.update(e["controls"])
        r.update(collision=e["collision"],casualty=e["casualty"],hour_sin=math.sin(2*math.pi*dt.hour/24),hour_cos=math.cos(2*math.pi*dt.hour/24),weekend=int(dt.weekday()>=5))
        rows.append(r)
    d=pd.DataFrame(rows)
    assert not d.duplicated(["collision","casualty"]).any()
    d["age"]=pd.to_numeric(d.age_of_casualty,errors="coerce")
    d["speed"]=pd.to_numeric(d.speed_limit,errors="coerce")
    masks={"weather":d.weather.astype(str).isin(["1","2","4","5"]),"area":d.rural.astype(str).isin(["1","2"]),"age":d.age.between(0,110),"sex":d.sex_of_casualty.astype(str).isin(["1","2"]),"speed":d.speed.isin([20,30,40,50,60,70]),"road":d.road_type.astype(str).isin(["1","2","3","6","7"]),"light":d.light_conditions.astype(str).isin(["1","4","5","6","7"])}
    keep=pd.Series(True,index=d.index); flow={}
    for k,v in masks.items():
        flow[k]=int((keep & ~v).sum());keep &=v
    d=d[keep].copy()
    d["rural_binary"]=(d.rural.astype(str)=="2").astype(int)
    d["police_rain"]=d.weather.astype(str).isin(["2","5"]).astype(int)
    d["era_rain"]=(d.precipitation_1h>=0.1-1e-9).astype(int)
    d["age10"]=d.age/10
    d["speed_high"]=(d.speed>=40).astype(int)
    d["single_road"]=(d.road_type.astype(str)=="6").astype(int)
    d["dark"]=(d.light_conditions.astype(str)!="1").astype(int)
    d["temp5"]=d.temperature/5;d["wind5"]=d.wind/5
    b="ksi ~ rural_binary + hour_sin + hour_cos + weekend"
    a=b+" + age10 + I(age10 ** 2) + C(sex_of_casualty) + speed_high + single_road + dark"
    forms={"base":b,"adjusted":a,"police":a+" + police_rain","era5":a+" + era_rain + temp5 + wind5","combined":a+" + police_rain + era_rain + temp5 + wind5","interaction":a+" + rural_binary * era_rain + temp5 + wind5"}
    result={"n":len(d),"ksi":int(d.ksi.sum()),"collisions":int(d.collision.nunique()),"exclusions_sequential":flow,"models":{},"limitations":"Exploratory January common cohort; coarse road categories; provisional code filters; no causal or out-of-sample claims."}
    for name,formula in forms.items():
        try:
            m=smf.logit(formula,d).fit(disp=False,cov_type="cluster",cov_kwds={"groups":d.collision})
            assert m.mle_retvals["converged"] and m.nobs==len(d)
            ci=m.conf_int()
            out={"aic":float(m.aic),"brier":float(((m.predict(d)-d.ksi)**2).mean()),"terms":{k:{"OR":math.exp(v),"lo":math.exp(ci.loc[k,0]),"hi":math.exp(ci.loc[k,1])} for k,v in m.params.items()}}
            if "era_rain" in m.params:
                risks={}
                for rural in (0,1):
                    dry=d.copy();wet=d.copy()
                    dry["rural_binary"]=wet["rural_binary"]=rural
                    dry["era_rain"]=0;wet["era_rain"]=1
                    risks[str(rural)]={"dry":float(m.predict(dry).mean()),"wet":float(m.predict(wet).mean()),"rd":float((m.predict(wet)-m.predict(dry)).mean())}
                out["standardized_model_contrasts"]=risks
            json.dumps(out,allow_nan=False)
            result["models"][name]=out
        except Exception as e:result["models"][name]={"error":repr(e)}
    Path("adjusted_models.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False))
    assert all("error" not in m for m in result["models"].values())
if __name__=="__main__":main()
