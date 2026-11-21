"""6+ gol (Toplam Gol Aralığı 6+ / 5,5 Üst) – piyasa (OddsMath keskin 1.5/2.5/3.5) + FotMob veri harmanı."""
import sys,json,math
sys.path.insert(0,'tahminler/grokbottahmin/2026-11-21')
from quantfoot.markets.goal_tail_fit import devig2,com_from_mean,nb_pmf,tail  # repo kopyası (eski /tmp/g6/fit.py)
from scipy.optimize import minimize
D='tahminler/grokbottahmin/2026-11-21/'
res=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/g6/collected.json'))
om=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/g6/om_ou.json'))
NU_CLUB=1.10   # repo: 34.463 maçlık holdout, kulüp ligleri hafif az-dağılımlı (COM-Poisson nu=1.10)
CUP_MISMATCH={3351687}
def targets(ou,sharp=True):
  # keskin (BetInAsia/Pinnacle): power devig; yumuşak büro (1XBET, %10+ marj): çarpımsal devig (power favoriyi şişirir)
  f=devig2 if sharp else (lambda o:(1/o[0])/((1/o[0])+(1/o[1])))
  return {int(float(L)+0.5):f(o) for L,o in ou.items() if o and len(o)==2 and min(o)>1.0}
def fit_mu(tg,pmf):
  r=minimize(lambda x:sum((tail(pmf(math.exp(x[0])),k)-v)**2 for k,v in tg.items()),[math.log(3)],method='Nelder-Mead',options=dict(xatol=1e-5,fatol=1e-12))
  return math.exp(r.x[0]),math.sqrt(r.fun/len(tg))
def agg(L):
  if not L: return None
  n=len(L); xs=[x for x in L if x.get('xgf') is not None]
  tot=[x['gf']+x['ga'] for x in L]
  return dict(n=n,gf=sum(x['gf'] for x in L)/n,ga=sum(x['ga'] for x in L)/n,tot=sum(tot)/n,
    o35=sum(t>=4 for t in tot)/n,o45=sum(t>=5 for t in tot)/n,g6=sum(t>=6 for t in tot),
    xgf=(sum(x['xgf'] for x in xs)/len(xs) if xs else None),xga=(sum(x['xga'] for x in xs)/len(xs) if xs else None),nxg=len(xs),
    seq=' '.join(f"{x['venue']}{x['gf']}-{x['ga']}" for x in L),reds=sum(1 for x in L if sum(x['red'] or [0,0])>0))
def h2h_tot(h):
  out=[]
  for m in h or []:
    s=(m.get('score') or '').replace(' ','')
    if '-' in s:
      try: a,b=s.split('-')[:2]; out.append(int(a)+int(b))
      except: pass
  return out
rows=[]
for r in res:
  c=str(r['code']); o=om.get(c)
  if not o: continue
  tg=targets(o['ou'],sharp=(o.get('book') in ('BetInAsia','Pinnacle')))
  cup=r['code'] in CUP_MISMATCH
  pm_com=(lambda mu:nb_pmf(mu,0.08)) if cup else (lambda mu:com_from_mean(mu,NU_CLUB))
  mu_m,rm=fit_mu(tg,pm_com)
  mu_p,_=fit_mu(tg,lambda mu:nb_pmf(mu,0.0))
  H=agg((r.get('home_form') or {}).get('last')); A=agg((r.get('away_form') or {}).get('last'))
  mu_d=None; wd=0.30
  if H and A and min(H['n'],A['n'])>=5:
    def side(att,dfn):
      g=(att['gf']+dfn['ga'])/2
      if att['xgf'] is not None and dfn['xga'] is not None and att['nxg']>=5 and dfn['nxg']>=5:
        g=0.5*g+0.5*(att['xgf']+dfn['xga'])/2
      return g
    mu_d=side(H,A)+side(A,H)
    wd=0.30*min(H['n'],A['n'])/10
  else: wd=0.0
  mu_b=(1-wd)*mu_m+wd*(mu_d or mu_m)
  p_mkt=tail(pm_com(mu_m),6); p_mod=tail(pm_com(mu_b),6)
  p_nb=tail(nb_pmf(mu_b,0.10),6)   # aşırı-dağılım duyarlılık (NB alpha=0.10)
  p_pois=tail(nb_pmf(mu_b,0.0),6)
  k6=(H['g6'] if H else 0)+(A['g6'] if A else 0); n6=(H['n'] if H else 0)+(A['n'] if A else 0)
  emp=(k6+p_mod*30)/(n6+30)
  p=0.85*p_mod+0.15*emp
  six=r.get('six'); o55=r.get('o55'); odds=max([x for x in (six,o55) if x] or [None])
  ht=h2h_tot(r.get('h2h'))
  today=r.get('today') or {}
  un=lambda s:[(u['name'],u['reason']) for u in ((today.get(s) or {}).get('unavailable') or [])]
  rows.append(dict(code=r['code'],ko=r['ko'],league=r['league'],match=f"{r['home']} - {r['away']}",
    nesine_6plus=six,nesine_55ust=o55,best_odds=odds,sharp_book=o.get('book'),sharp_ou=o['ou'],sharp_targets={f'P(T>={k})':round(v,3) for k,v in tg.items()},
    mu_market=round(mu_m,2),fit_rmse=round(rm,4),mu_poisson_fit=round(mu_p,2),mu_data=mu_d and round(mu_d,2),w_data=round(wd,2),mu_blend=round(mu_b,2),
    p_market=round(p_mkt,4),p_model=round(p_mod,4),p_nb_sens=round(p_nb,4),p_poisson_sens=round(p_pois,4),emp_6plus=f"{k6}/{n6}",emp_shrunk=round(emp,4),
    p_final=round(p,4),fair_odds=round(1/p,2),ev=(odds and round(p*odds-1,4)),ev_band=(odds and [round(min(p_mod,p_pois,p_nb)*odds-1,3),round(max(p_mod,p_pois,p_nb)*odds-1,3)]),
    home=H,away=A,h2h=r.get('h2h'),h2h_totals=ht,h2h_6plus=sum(t>=6 for t in ht),
    home_next=(r.get('home_form') or {}).get('next'),away_next=(r.get('away_form') or {}).get('next'),
    home_out=un('home_lineup'),away_out=un('away_lineup'),weather=today.get('weather'),referee=today.get('referee'),fotmob=(r.get('fotmob') or {}).get('id')))
for x in rows:
  x['started_or_soon']=x['ko']<='18:45'
  x['soft_reference']=x['sharp_book'] not in ('BetInAsia','Pinnacle')
rows.sort(key=lambda x:-x['p_final'])
json.dump(dict(generated='2026-11-21',method='bkz. gol6_detay.md',rows=rows),open(D+'gol6_detay.json','w'),ensure_ascii=False,indent=1,default=str)
for x in rows:
  print(x['code'],x['ko'],x['match'][:34].ljust(34),'odds',x['best_odds'],'mu m/d/b',x['mu_market'],x['mu_data'],x['mu_blend'],'P',x['p_final'],'band',x['p_model'],x['p_poisson_sens'],x['p_nb_sens'],'emp',x['emp_6plus'],'EV',x['ev'],'h2h',x['h2h_totals'])
