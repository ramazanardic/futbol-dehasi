"""6+ gol derin araştırma – FotMob veri toplama (nazik, önbellekli). Kullanım: gol6_topla.py code1,code2,..."""
import sys,json,datetime as dt,traceback
sys.path.insert(0,'src')
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.fotmob import FotMob,UA,BASE,parse_matches,find_match,parse_details
D='tahminler/grokbottahmin/2026-11-21/'
codes=[int(c) for c in sys.argv[1].split(',')]
L={x['code']:x for x in json.load(open('tahminler/grokbottahmin/2026-11-21/veri/g6/list.json'))}
f=FotMob(CachedHttp(),delay_s=0.8)
fm=[]
for day in (dt.date(2026,11,21),dt.date(2026,11,22)):
  fm+=parse_matches(f.matches_on(day) or {})
def team_form(tid,before_utc,n=10):
  t=f.http.get(f"{BASE}/teams",{"id":str(tid)},UA,6*3600,f._polite)
  if not isinstance(t,dict): return None
  fx=t['fixtures']['allFixtures']['fixtures']
  fin=[x for x in fx if x['status'].get('finished') and not x['status'].get('cancelled') and x['status']['utcTime']<before_utc]
  nxt=[x for x in fx if not x['status'].get('finished') and x['status']['utcTime']>before_utc]
  out=[]
  for x in fin[-n:]:
    d=f.details(x['id'],ttl_s=None)
    if not d: continue
    ev=((d.get('content') or {}).get('matchFacts') or {}).get('events',{}).get('events') or []
    teams=d['header']['teams']; ft=[teams[0].get('score'),teams[1].get('score')]
    ftev=[e for e in ev if e.get('type')=='Half' and e.get('halfStrShort')=='FT']
    if ftev: ft=[ftev[0]['homeScore'],ftev[0]['awayScore']]
    if ft[0] is None: continue
    home=x['home']['id']==tid
    pd=parse_details(d); xg=pd['stats']['home'].get('xg'),pd['stats']['away'].get('xg')
    out.append(dict(date=x['status']['utcTime'][:10],comp=x['tournament']['name'],venue='H' if home else 'A',opp=x['opponent']['name'],
      gf=ft[0] if home else ft[1],ga=ft[1] if home else ft[0],xgf=(xg[0] if home else xg[1]),xga=(xg[1] if home else xg[0]),red=pd['red']))
  nx=[dict(date=x['status']['utcTime'][:16],comp=x['tournament']['name'],opp=x['opponent']['name']) for x in nxt[:2]]
  prv=[dict(date=x['status']['utcTime'][:16],comp=x['tournament']['name'],opp=x['opponent']['name']) for x in fin[-1:]]
  return dict(name=t['details'].get('name'),last=out,next=nx,prev=prv)
res=[]
for c in codes:
  x=L[c]; r=dict(x)
  try:
    mm=find_match(fm,x['home'],x['away'],0.55)
    r['fotmob']=mm
    if mm:
      d=f.details(mm['id'],ttl_s=1800)
      hdr=d['header']['teams']; hid,aid=hdr[0]['id'],hdr[1]['id']
      pd=parse_details(d); r['today']={k:pd.get(k) for k in ('home_lineup','away_lineup','lineup_type','weather','referee','stadium')}
      h2h=((d.get('content') or {}).get('h2h') or {}).get('matches') or []
      r['h2h']=[dict(date=(m.get('time') or {}).get('utcTime','')[:10],home=m['home']['name'],away=m['away']['name'],score=(m.get('status') or {}).get('scoreStr')) for m in h2h[:8]]
      r['home_form']=team_form(hid,mm['utc']); r['away_form']=team_form(aid,mm['utc'])
  except Exception as e:
    r['error']=repr(e); traceback.print_exc()
  res.append(r)
  print(c,x['home'],x['away'],'fm' if r.get('fotmob') else 'NO-FM',len((r.get('home_form') or {}).get('last') or []),len((r.get('away_form') or {}).get('last') or []),flush=True)
  json.dump(res,open('tahminler/grokbottahmin/2026-11-21/veri/g6/collected.json','w'),ensure_ascii=False,default=str)
print('errors',f.http.errors[:20])
