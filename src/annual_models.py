import json,math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy.special import expit
from annual_audit import main as audit

def main():
    audit()
    d=pd.DataFrame([r for p in sorted(Path("cohorts").glob("cohort_*.json")) for r in json.loads(p.read_text())])
    assert len(d)==19322
    d["age"]=pd.to_numeric(d.age_of_casualty,errors="coerce")
    d["speed"]=pd.to_numeric(d.speed_limit,errors="coerce")
    masks={"weather":d.weather.astype(str).isin(["1","2","4","5"]),"area":d.rural.astype(str).isin(["1","2"]),"age":d.age.between(0,110),"sex":d.sex_of_casualty.astype(str).isin(["1","2"]),"speed":d.speed.isin([20,30,40,50,60,70]),"road":d.road_type.astype(str).isin(["1","2","3","6","7"]),"light":d.light_conditions.astype(str).isin(["1","4","5","6","7"])}
    keep=pd.Series(True,index=d.index);flow={}
    for k,v in masks.items():
        flow[k]=int((keep & ~v).sum());keep &= v
    d=d[keep].copy()
    d["rural_binary"]=(d.rural.astype(str)=="2").astype(int)
    d["police_rain"]=d.weather.astype(str).isin(["2","5"]).astype(int)
    d["era_rain"]=(d.precipitation_1h>=0.1-1e-9).astype(int)
    d["age10"]=d.age/10
    d["speed_high"]=(d.speed>=40).astype(int)
    d["single_road"]=(d.road_type.astype(str)=="6").astype(int)
    d["dark"]=(d.light_conditions.astype(str)!="1").astype(int)
    d["temp5"]=d.temperature/5;d["wind5"]=d.wind/5
    d["hour_sin"]=np.sin(2*np.pi*d.local_hour/24);d["hour_cos"]=np.cos(2*np.pi*d.local_hour/24)
    b="ksi ~ rural_binary + hour_sin + hour_cos + weekend + C(month)"
    p=b+" + age10 + I(age10 ** 2) + C(sex_of_casualty)"
    a=p+" + speed_high + single_road + dark"
    w=" + era_rain + temp5 + wind5"
    forms={"Y0":b,"Y1":p,"Y2":a,"Y3":a+" + police_rain","Y4":a+w,"Y5":a+w+" + police_rain","Y6":a+w+" + rural_binary:era_rain","Y6_unadjusted":b+w+" + rural_binary:era_rain","Y7":a+" + era_rain + bs(temperature, df=4) + wind5"}
    result=dict(n=len(d),ksi=int(d.ksi.sum()),collisions=int(d.collision.nunique()),exclusions=flow,cell_counts=d.groupby(["rural_binary","era_rain"]).ksi.agg(["size","sum"]).reset_index().to_dict("records"),models={},limitations="Conditional KSI among recorded pedestrian casualties; provisional covariate filters; collision-clustered covariance; common sample restricted to police fine/rain; standardized associations not causal; no out-of-sample evaluation.")
    for name,formula in forms.items():
        try:
            m=smf.logit(formula,d).fit(disp=False,cov_type="cluster",cov_kwds={"groups":d.collision})
            assert m.mle_retvals["converged"] and m.nobs==len(d)
            ci=m.conf_int()
            out=dict(formula=formula,aic=float(m.aic),brier=float(((m.predict(d)-d.ksi)**2).mean()),terms={k:dict(OR=math.exp(v),lo=math.exp(ci.loc[k,0]),hi=math.exp(ci.loc[k,1])) for k,v in m.params.items() if not k.startswith("bs(")})
            if name in ("Y4","Y5","Y6","Y6_unadjusted"):
                cov=np.asarray(m.cov_params());beta=np.asarray(m.params)
                def pred(area,wet):
                    z=d.copy();z["rural_binary"]=area;z["era_rain"]=wet
                    x=np.asarray(build_design_matrices([m.model.data.design_info],z)[0]);pr=expit(x@beta)
                    return pr.mean(),(x*(pr*(1-pr))[:,None]).mean(axis=0)
                def interval(v,g):
                    se=math.sqrt(max(0,float(g@cov@g)));return dict(estimate=float(v),lo=float(v-1.96*se),hi=float(v+1.96*se))
                rds={};rd=[]
                for area in (0,1):
                    dry,gd=pred(area,0);wet,gw=pred(area,1);v=wet-dry;g=gw-gd
                    rds[str(area)]=dict(dry=float(dry),wet=float(wet),rd=interval(v,g));rd.append((v,g))
                rds["difference_in_rd"]=interval(rd[1][0]-rd[0][0],rd[1][1]-rd[0][1])
                out["standardized"]=rds
            json.dumps(out,allow_nan=False)
            result["models"][name]=out
        except Exception as e:result["models"][name]={"error":repr(e)}
    Path("annual_models.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False))
    assert all("error" not in r for r in result["models"].values())
if __name__=="__main__":main()
