import json,math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor
b=json.loads(Path("climate_c1.json").read_text())
assert b["reference"]=="1991-2020" and not b["errors"] and len(b["grids"])==10
assert all(g["complete_years"]==30 and len(g["statistics"])==288 for g in b["grids"])
lookup={(tuple(g["grid"]),s["month"],s["utc_hour"]):s for g in b["grids"] for s in g["statistics"]}
rows=[]
for p in sorted(Path("cohorts").glob("cohort_*.json")):
    for r in json.loads(p.read_text()):
        g=(r["grid_lat"],r["grid_lon"])
        s=lookup.get((g,r["utc_month"],r["utc_hour"]))
        if s is None:continue
        t=s["temperature_2m"]
        rows.append(dict(r,grid=str(g),anomaly5=(r["temperature"]-t["mean"])/5,temp5=r["temperature"]/5,hot=int(r["temperature"]>t["p95"]),cold=int(r["temperature"]<t["p05"])))
assert len(rows)==4917 and sum(r["ksi"] for r in rows)==1333
d=pd.DataFrame(rows)
d["age"]=pd.to_numeric(d.age_of_casualty,errors="coerce")
d["speed"]=pd.to_numeric(d.speed_limit,errors="coerce")
masks={"area":d.rural.astype(str).isin(["1","2"]),"age":d.age.between(0,110),"sex":d.sex_of_casualty.astype(str).isin(["1","2"]),"speed":d.speed.isin([20,30,40,50,60,70]),"road":d.road_type.astype(str).isin(["1","2","3","6","7"]),"light":d.light_conditions.astype(str).isin(["1","4","5","6","7"])}
keep=pd.Series(True,index=d.index);flow={}
for k,v in masks.items():
    flow[k]=int((keep & ~v).sum());keep &=v
d=d[keep].copy()
d["rural_binary"]=(d.rural.astype(str)=="2").astype(int)
d["age10"]=d.age/10;d["speed_high"]=(d.speed>=40).astype(int)
d["single_road"]=(d.road_type.astype(str)=="6").astype(int)
d["dark"]=(d.light_conditions.astype(str)!="1").astype(int)
d["era_rain"]=(d.precipitation_1h>=0.1-1e-9).astype(int);d["wind5"]=d.wind/5
d["hour_sin"]=np.sin(2*np.pi*d.local_hour/24);d["hour_cos"]=np.cos(2*np.pi*d.local_hour/24)
# Pool very sparse grid levels only for this engineering pilot; report the mapping.
counts=d.groupby("grid").ksi.agg(["size","sum"])
sparse=counts.index[(counts["sum"]<5)|((counts["size"]-counts["sum"])<5)].tolist()
# Omit grid FE in main pilot rather than invent a shared geography. Fit FE sensitivity on supported grids separately later.
base="ksi ~ rural_binary + age10 + I(age10 ** 2) + C(sex_of_casualty) + speed_high + single_road + dark + C(month) + hour_sin + hour_cos + weekend + era_rain + wind5"
forms={"CM0":base,"CM1":base+" + temp5","CM2":base+" + anomaly5","CM3":base+" + temp5 + anomaly5","CM4":base+" + temp5 + hot + cold"}
# Same supported cohort for pooled and grid-FE comparisons.
d=d[~d.grid.isin(sparse)].copy()
assert len(d)==4502
out={"n":len(d),"ksi":int(d.ksi.sum()),"excluded_grids":sparse,"models":{},"note":"Exploratory same-cohort comparisons; collision-clustered intervals; not spatially robust."}
for label,extra in [("pooled",""),("grid_fe"," + C(grid)")]:
    for name,term in [("base",""),("absolute"," + temp5"),("anomaly"," + anomaly5"),("extremes"," + temp5 + hot + cold"),("nonlinear_anomaly"," + bs(anomaly5, df=4)")]:
        m=smf.logit(base+extra+term,d).fit(disp=False,cov_type="cluster",cov_kwds={"groups":d.collision})
        assert m.mle_retvals["converged"] and m.nobs==len(d)
        ci=m.conf_int()
        out["models"][label+"_"+name]={"aic":float(m.aic),"brier":float(((m.predict(d)-d.ksi)**2).mean()),"terms":{k:{"OR":math.exp(m.params[k]),"lo":math.exp(ci.loc[k,0]),"hi":math.exp(ci.loc[k,1])} for k in ("temp5","anomaly5","hot","cold") if k in m.params}}
# Geographic holdout for models without grid dummy variables. Fixed spline bounds are not used in CV.
out["holdout"]={}
for name,term in [("base",""),("absolute"," + temp5"),("anomaly"," + anomaly5"),("extremes"," + temp5 + hot + cold")]:
    folds=[]
    for grid,test in d.groupby("grid"):
        train=d[d.grid!=grid]
        m=smf.logit(base+term,train).fit(disp=False)
        assert m.mle_retvals["converged"]
        pr=np.clip(m.predict(test),1e-12,1-1e-12)
        folds.append({"grid":grid,"n":len(test),"brier":float(((pr-test.ksi)**2).mean()),"logloss":float(-(test.ksi*np.log(pr)+(1-test.ksi)*np.log(1-pr)).mean())})
    out["holdout"][name]={"folds":folds,"weighted_brier":sum(f["n"]*f["brier"] for f in folds)/len(d),"weighted_logloss":sum(f["n"]*f["logloss"] for f in folds)/len(d),"macro_brier":float(np.mean([f["brier"] for f in folds]))}
Path("climate_spatial.json").write_text(json.dumps(out,indent=2,allow_nan=False))
print(json.dumps(out,indent=2,allow_nan=False))
