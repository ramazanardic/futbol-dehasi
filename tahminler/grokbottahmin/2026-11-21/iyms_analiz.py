"""İY/MS – yarı bazlı Dixon-Coles + keskin piyasa (motor fair) + takımların gerçek İY/MS desenleri harmanı."""
import sys,json,math,datetime as dt
sys.path.insert(0,'src')
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.fotmob import FotMob,parse_details
D='tahminler/grokbottahmin/2026-11-21/'
NG=sys.argv[1] if len(sys.argv)>1 else D+'nesine_global.json'
ng=json.load(open(NG)); NGM={m['code']:m for m in ng['matches']}
res=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/collected.json'))
uni=json.load(open('tahminler/grokbottahmin/2026-11-21/veri/iyms/universe.json'))
f=FotMob(CachedHttp(),delay_s=0.8)
TSI=dt.timezone(dt.timedelta(hours=3)); NOW=dt.datetime.now(TSI)
OUT=['1/2','1/1','1/X','X/1','X/X','2/1','2/X','2/2']; ALL=OUT+['X/2']
PRIOR_S1=0.445; RHO1,RHO2=-0.10,-0.06
EURO=('Champions League','Europa League','Conference League')
def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def dc(lh,la,rho,G=8):
  M=[[pois(lh,i)*pois(la,j) for j in range(G)] for i in range(G)]
  t={(0,0):1-lh*la*rho,(0,1):1+lh*rho,(1,0):1+la*rho,(1,1):1-rho}
  for (i,j),v in t.items(): M[i][j]*=max(v,0)
  s=sum(map(sum,M)); return [[x/s for x in r] for r in M]
def r3(a,b): return '1' if a>b else ('2' if a<b else 'X')
def htft(lh1,la1,lh2,la2):
  A=dc(lh1,la1,RHO1); B=dc(lh2,la2,RHO2); P={k:0 for k in ALL}
  for i in range(8):
    for j in range(8):
      if A[i][j]<1e-9: continue
      for k in range(8):
        for l in range(8):
          P[r3(i,j)+'/'+r3(i+k,j+l)]+=A[i][j]*B[k][l]
  return P
def agg(L,side):
  """side='H' -> bu takımın ev sahibi gibi yönlendirilmiş İY/MS (takım bakışı: W/D/L)."""
  n=len(L)
  if not n: return None
  g=lambda k: sum(x[k] for x in L)/n
  cnt={}
  for x in L:
    a=r3(x['gf1'],x['ga1'])+'/'+r3(x['gft'],x['gat'])   # takım bakışı: 1=takım önde
    cnt[a]=cnt.get(a,0)+1
  ld=[x for x in L if x['gf1']>x['ga1']]; tr=[x for x in L if x['gf1']<x['ga1']]
  return dict(n=n,gf1=g('gf1'),ga1=g('ga1'),gf2=g('gf2'),ga2=g('ga2'),pat={k:v/n for k,v in cnt.items()},
    ht_draw=sum(1 for x in L if x['gf1']==x['ga1'])/n, ht_lead=len(ld)/n,
    lead_conv=(sum(1 for x in ld if x['gft']>x['gat'])/len(ld) if ld else None), n_lead=len(ld),
    comeback=(sum(1 for x in tr if x['gft']>x['gat'])/len(tr) if tr else None), n_trail=len(tr),
    blown=(sum(1 for x in ld if x['gft']<x['gat'])/len(ld) if ld else None),
    form=''.join('W' if x['gft']>x['gat'] else 'D' if x['gft']==x['gat'] else 'L' for x in L[-5:]),
    seq=' '.join(f"{x['venue']}{x['gf1']}-{x['ga1']}/{x['gft']}-{x['gat']}" for x in L[-10:]))
def flip(o):  # ev-sahibi bakışından takım bakışına (deplasman için)
  m={'1':'2','2':'1','X':'X'}; a,b=o.split('/'); return m[a]+'/'+m[b]
def emp(H,A,o):
  if not H or not A: return None
  ph=H['pat'].get(o,0); pa=A['pat'].get(flip(o),0)   # deplasman takım bakışı: 1/1 ev için = deplasmanın 2/2 si (yenik/yenik)
  # dep. takım bakışında ev sahibinin 1/1'i = deplasman 'L at HT / L at FT' = '2/2' kendi bakışında
  return (ph+pa)/2,(H['n']+A['n'])
have={r['code'] for r in res}
res=res+[dict(code=u['code']) for u in uni['rows'] if u['code'] not in have]
rows=[]
for r in res:
  m=NGM.get(r['code'])
  if not m: continue
  ko=dt.datetime.fromisoformat(m['kickoff_iso'])
  sel={s['selection']:s for s in m.get('selections') or [] if s['market']=='İlk Yarı/Maç Sonucu'}
  if not sel: continue
  over=sum(1/s['odds'] for s in sel.values()) if len(sel)==9 else None
  muh,mua=m.get('mu_home'),m.get('mu_away')
  H=agg((r.get('home_form') or {}).get('last') or [],'H'); A=agg((r.get('away_form') or {}).get('last') or [],'A')
  eng={k:(sel.get(k) or {}).get('fair_prob') for k in ALL}
  ht1x2={s['selection']:s for s in m.get('selections') or [] if s['market']=='1. Yarı Sonucu'}
  rec=dict(code=r['code'],ko=m['kickoff'],league=m.get('league'),match=f"{m['home']} - {m['away']}",tier=m.get('price_tier'),ref=m.get('reference'),
    ref_age_h=m.get('ref_age_hours'),mu=[muh,mua],overround=over and round(over,3),fair_1x2=m.get('fair_1x2'),
    nesine={k:(sel.get(k) or {}).get('odds') for k in ALL},mbs=max((s.get('mbs') or 0) for s in sel.values()),
    engine=eng,home_stats=H,away_stats=A,flags=[],notes=[],fotmob_id=(r.get('fotmob') or {}).get('id'),h2h=r.get('h2h'))
  model=None
  if muh and mua:
    if H and A:
      dh1=(H['gf1']+A['ga1'])/2; da1=(A['gf1']+H['ga1'])/2; dh2=(H['gf2']+A['ga2'])/2; da2=(A['gf2']+H['ga2'])/2; n=min(H['n'],A['n'])
      def share(a,b,ng_):
        s=a/(a+b) if a+b>0 else PRIOR_S1; w=ng_/(ng_+15.0); return (1-w)*PRIOR_S1+w*s
      sh=share(dh1,dh2,(dh1+dh2)*n*2); sa=share(da1,da2,(da1+da2)*n*2)
    else: sh=sa=PRIOR_S1; rec['notes'].append('FotMob formu yok: ilk yarı payı lig ortalaması %44,5')
    model=htft(muh*sh,mua*sa,muh*(1-sh),mua*(1-sa))
    rec['lambdas']=dict(h1=round(muh*sh,3),a1=round(mua*sa,3),h2=round(muh*(1-sh),3),a2=round(mua*(1-sa),3))
  P={};
  for k in ALL:
    parts=[];w=[]
    if eng.get(k): parts.append(eng[k]); w.append(0.45)
    if model: parts.append(model[k]); w.append(0.40)
    e=emp(H,A,k)
    if e is not None:
      shrink=e[1]/(e[1]+20)  # 20 maç ≈ %50 ağırlık
      base=(model or eng)[k] if (model or eng.get(k)) else e[0]
      parts.append(shrink*e[0]+(1-shrink)*base); w.append(0.15)
    P[k]=sum(a*b for a,b in zip(parts,w))/sum(w) if w else None
  s=sum(v for v in P.values() if v)
  P={k:(v/s if v else None) for k,v in P.items()}
  rec['model']=model and {k:round(v,4) for k,v in model.items()}
  rec['empirical']={k:(lambda e:e and round(e[0],3))(emp(H,A,k)) for k in ALL}
  rec['P']={k:round(v,4) for k,v in P.items() if v}
  rec['EV']={k:round(P[k]*rec['nesine'][k]-1,4) for k in ALL if P.get(k) and rec['nesine'].get(k)}
  # bayraklar: eksikler, rotasyon, hakem/kırmızı
  if rec['fotmob_id']:
    d=f.details(rec['fotmob_id'],ttl_s=None)
    if d:
      pd=parse_details(d)
      for side in ('home','away'):
        lu=pd.get(f'{side}_lineup') or {}
        un=[f"{u['name']} ({u['reason']})" for u in lu.get('unavailable') or []]
        if un: rec[f'{side}_unavailable']=un
      rec['lineup_type']=pd.get('lineup_type')
  else: rec['flags'].append('FotMob eşleşmedi: kadro/eksik ve İY/MS geçmişi yok')
  for side,key in (('Ev','home_form'),('Dep','away_form')):
    for nx in ((r.get(key) or {}).get('next') or [])[:1]:
      try:
        gap=(dt.datetime.fromisoformat(nx['date']+':00+00:00')-ko).total_seconds()/86400
        if any(e in nx['comp'] for e in EURO) and gap<5: rec['flags'].append(f"{side} rotasyon riski: {nx['comp']} {nx['opp']} {nx['date'][:10]}")
      except Exception: pass
  if (m.get('ref_age_hours') or 0)>6: rec['notes'].append(f"keskin referans {m.get('ref_age_hours')} sa eski")
  if m.get('price_tier')!='keskin' and 'Pinnacle' not in (m.get('reference') or '') and 'Smarkets' not in (m.get('reference') or ''):
    rec['notes'].append(f"referans: {m.get('reference')} (keskin değil)")
  rec['started']=ko<NOW+dt.timedelta(minutes=20)
  rows.append(rec)
json.dump(rows,open('tahminler/grokbottahmin/2026-11-21/veri/iyms/analysed.json','w'),ensure_ascii=False,default=str)
print(len(rows))
