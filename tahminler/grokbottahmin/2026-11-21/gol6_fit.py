import json,math,numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
def devig2(o):
  a,b=o
  # power method
  lo,hi=0.5,3.0
  for _ in range(60):
    k=(lo+hi)/2; s=(1/a)**k+(1/b)**k
    if s>1: lo=k
    else: hi=k
  return (1/a)**k
def com_pmf(lam,nu,N=20):
  k=np.arange(N+1); lp=k*math.log(lam)-nu*gammaln(k+1); lp-=lp.max(); p=np.exp(lp); return p/p.sum()
def com_from_mean(mu,nu,N=20):
  lo,hi=1e-3,60
  for _ in range(80):
    lam=math.sqrt(lo*hi); p=com_pmf(lam,nu,N); m=(np.arange(N+1)*p).sum()
    if m<mu: lo=lam
    else: hi=lam
  return com_pmf(lam,nu,N)
def nb_pmf(mu,alpha,N=20):
  k=np.arange(N+1)
  if alpha<1e-6:
    lp=k*math.log(mu)-mu-gammaln(k+1)
  else:
    r=1/alpha; p=r/(r+mu)
    lp=gammaln(k+r)-gammaln(r)-gammaln(k+1)+r*math.log(p)+k*math.log(1-p)
  q=np.exp(lp); return q/q.sum()
def tail(p,k): return p[k:].sum()
def fit_market(ou):
  """ou: {'1.5':[o,u],...} -> targets P(T>=2..4); fit COM (mu,nu) free."""
  tg={}
  for L,o in ou.items():
    if o and len(o)==2 and min(o)>1.0: tg[int(float(L)+0.5)]=devig2(o)
  if not tg: return None
  def loss(x):
    mu,nu=math.exp(x[0]),math.exp(x[1])
    p=com_from_mean(mu,nu); return sum((tail(p,k)-v)**2 for k,v in tg.items())
  best=None
  for nu0 in (0.8,1.0,1.2):
    r=minimize(loss,[math.log(3),math.log(nu0)],method='Nelder-Mead',options=dict(xatol=1e-4,fatol=1e-9,maxiter=600))
    if best is None or r.fun<best.fun: best=r
  mu,nu=math.exp(best.x[0]),math.exp(best.x[1])
  nu=min(max(nu,0.7),1.4)
  # Poisson fit (nu=1) too
  r1=minimize(lambda x:sum((tail(com_from_mean(math.exp(x[0]),1.0),k)-v)**2 for k,v in tg.items()),[math.log(3)],method='Nelder-Mead')
  mu1=math.exp(r1.x[0])
  return dict(targets=tg,mu=mu,nu=nu,rmse=math.sqrt(best.fun/len(tg)),mu_pois=mu1,
     p6_com=tail(com_from_mean(mu,nu),6),p6_pois=tail(com_from_mean(mu1,1.0),6),p5_com=tail(com_from_mean(mu,nu),5))
