import pandas as pd, numpy as np, json
import statsmodels.api as sm
from scipy import stats
from pathlib import Path

ROOT=Path('.')
D=pd.read_csv(ROOT/'5_Experiments_Simulations/strengthening/canonical_v2/discovery_canonical_v2.csv')
R0=pd.read_csv(ROOT/'5_Experiments_Simulations/strengthening/canonical_v2/replication_canonical_v2_complete.csv')
SEED=20260918
DRAWS=200000

assert 'tradplusad.com' in set(R0.domain)

def finalize_claim(df):
    return (df[['has_iso_27001','has_soc_2','has_csa_star']].sum(axis=1)>0).astype(int)

def gap(df):
    c=df['claim'].to_numpy(bool); y=df.d_vpf_technical_score.to_numpy(float)
    a=y[c]; b=y[~c]
    diff=float(a.mean()-b.mean())
    v1=np.var(a,ddof=1); v0=np.var(b,ddof=1)
    se=np.sqrt(v1/len(a)+v0/len(b))
    dof=(v1/len(a)+v0/len(b))**2/((v1/len(a))**2/(len(a)-1)+(v0/len(b))**2/(len(b)-1))
    crit=stats.t.ppf(.975,dof)
    return diff,[float(diff-crit*se),float(diff+crit*se)],float(stats.ttest_ind(a,b,equal_var=False).pvalue)

def interaction(D,R):
    dd=D.copy(); rr=R.copy()
    dd['claim']=finalize_claim(dd)
    # rr claim already scenario set
    allx=pd.concat([dd.assign(stratum=0),rr.assign(stratum=1)],ignore_index=True)
    y=allx.d_vpf_technical_score.to_numpy(float)
    c=allx.claim.to_numpy(int)
    s=allx.stratum.to_numpy(int)
    inter=c*s
    lr=np.log10(allx['rank'].to_numpy(float))
    clr=lr.copy()
    for g in (0,1): clr[s==g]-=lr[s==g].mean()
    X=sm.add_constant(np.column_stack([c,s,inter,clr]))
    m=sm.OLS(y,X).fit(cov_type='HC3'); ci=m.conf_int()
    return float(m.params[3]),[float(ci[3,0]),float(ci[3,1])],float(m.pvalues[3])

def perm(D,R,draws=DRAWS):
    dd=D.copy(); dd['claim']=finalize_claim(dd)
    rows=pd.concat([dd.assign(stratum=0),R.assign(stratum=1)],ignore_index=True)
    y=rows.d_vpf_technical_score.to_numpy(float)
    c=rows.claim.to_numpy(bool)
    s=rows.stratum.to_numpy(int)
    def g(ss,t):
        m=ss==t
        return float(y[m&c].mean()-y[m&~c].mean())
    obs=g(s,1)-g(s,0)
    ic=np.where(c)[0]; ino=np.where(~c)[0]
    nrc=int(((s==1)&c).sum()); nrn=int(((s==1)&~c).sum())
    rng=np.random.default_rng(SEED)
    exceed=0
    for _ in range(draws):
        ps=np.zeros(len(rows),int)
        ps[rng.choice(ic,size=nrc,replace=False)]=1
        ps[rng.choice(ino,size=nrn,replace=False)]=1
        delta=g(ps,1)-g(ps,0)
        if abs(delta)>=abs(obs)-1e-12: exceed+=1
    return float(obs),(exceed+1)/(draws+1)

scenarios={}
for name in ['original_negative','final_positive','removed']:
    R=R0.copy()
    if name=='original_negative':
        R['claim']=finalize_claim(R)
        R.loc[R.domain=='tradplusad.com','claim']=0
    elif name=='final_positive':
        R['claim']=finalize_claim(R)
    else:
        R=R[R.domain!='tradplusad.com'].copy()
        R['claim']=finalize_claim(R)
    gg,ci,p=gap(R)
    beta,bci,bp=interaction(D,R)
    delta,pp=perm(D,R)
    scenarios[name]={
        'n_second':len(R),'claimers':int(R.claim.sum()),'nonclaimers':int((1-R.claim).sum()),
        'second_gap':gg,'second_gap_ci95':ci,'second_welch_p':p,
        'claim_x_stratum_beta':beta,'claim_x_stratum_ci95':bci,'interaction_p':bp,
        'second_minus_discovery_gap':delta,'claim_stratified_permutation_p':pp,'permutation_draws':DRAWS
    }
out={'seed':SEED,'tradplus_domain':'tradplusad.com','scenarios':scenarios,
     'interpretation':'Sensitivity only. It tests the post-outcome TradPlus label correction; it does not adjudicate the correct label.'}
Path('6_Analysis_Results/strengthening/canonical_v2_tradplus_timing_sensitivity.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
