"""İY/MS derin araştırma – aday seçimi + FotMob HT/FT form toplama (önbellekli, nazik)."""
import sys,json,datetime as dt,glob,re,traceback
sys.path.insert(0,'src')
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.fotmob import FotMob,UA,BASE,parse_matches,find_match,parse_details
D='tahminler/grokbottahmin/2026-11-21/'
TSI=dt.timezone(dt.timedelta(hours=3))
SRC=sys.argv[1] if len(sys.argv)>1 else D+'nesine_global.json'
ng=json.load(open(SRC))
NOW=dt.datetime.now(TSI)+dt.timedelta(minutes=20)
used=set()
for f in glob.glob(D+'kupon_*.json')+[D+'banko_kupon.json']:
  if 'kupon_10_banko' in f: continue
  used|=set(int(c) for c in re.findall(r'"code": (\d{7})',open(f).read()))
NAMES=('Sassuolo','Amstetten','Lazio','Catanzaro','Napoli')
OUT=['1/2','1/1','1/X','X/1','X/X','2/1','2/X','2/2']
rows=[]
for m in ng['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<NOW: continue
  if m['code'] in used or any(n in m['home']+m['away'] for n in NAMES): continue
  sel={s['selection']:s for s in (m.get('selections') or []) if s['market']=='İlk Yarı/Maç Sonucu'}
  if not sel: continue
  rows.append(dict(code=m['code'],ko=m['kickoff'],ko_iso=m['kickoff_iso'],league=m.get('league'),home=m['home'],away=m['away'],
    p11=(sel.get('1/1') or {}).get('fair_prob') or 0,p22=(sel.get('2/2') or {}).get('fair_prob') or 0,
    best_ev=max((s.get('ev') or -9) for s in sel.values())))
json.dump(dict(used=sorted(used),rows=rows),open('tahminler/grokbottahmin/2026-11-21/veri/iyms/universe.json','w'),ensure_ascii=False)
cand={}
for key,n in (('p11',25),('p22',15),('best_ev',12)):
  for r in sorted(rows,key=lambda r:-r[key])[:n]: cand[r['code']]=r
print('universe',len(rows),'cand',len(cand),flush=True)
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
    ht=[e for e in ev if e.get('type')=='Half' and e.get('halfStrShort')=='HT']
    teams=d['header']['teams']; ft=[teams[0].get('score'),teams[1].get('score')]
    if not ht or ft[0] is None: continue
    hth=[ht[0]['homeScore'],ht[0]['awayScore']]
    ftev=[e for e in ev if e.get('type')=='Half' and e.get('halfStrShort')=='FT']
    if ftev: ft=[ftev[0]['homeScore'],ftev[0]['awayScore']]
    home=x['home']['id']==tid
    pd=parse_details(d)
    gf1,ga1=(hth[0],hth[1]) if home else (hth[1],hth[0])
    gft,gat=(ft[0],ft[1]) if home else (ft[1],ft[0])
    out.append(dict(date=x['status']['utcTime'][:10],comp=x['tournament']['name'],venue='H' if home else 'A',
      opp=x['opponent']['name'],gf1=gf1,ga1=ga1,gf2=gft-gf1,ga2=gat-ga1,gft=gft,gat=gat,red=pd['red']))
  nx=[dict(date=x['status']['utcTime'][:16],comp=x['tournament']['name'],opp=x['opponent']['name']) for x in nxt[:2]]
  return dict(name=t['details'].get('name'),last=out,next=nx)
res=[]
for c in cand.values():
  r=dict(c)
  try:
    mm=find_match(fm,c['home'],c['away'],0.6)
    r['fotmob']=mm
    if mm:
      d=f.details(mm['id'],ttl_s=1800)
      hdr=d['header']['teams']; hid,aid=hdr[0]['id'],hdr[1]['id']
      pd=parse_details(d); r['today']={k:pd.get(k) for k in ('lineup_type','referee')}
      h2h=((d.get('content') or {}).get('h2h') or {}).get('matches') or []
      r['h2h']=[dict(date=(x.get('time') or {}).get('utcTime','')[:10],home=x['home']['name'],away=x['away']['name'],score=(x.get('status') or {}).get('scoreStr')) for x in h2h[:6]]
      r['home_form']=team_form(hid,mm['utc']); r['away_form']=team_form(aid,mm['utc'])
  except Exception as e:
    r['error']=repr(e); traceback.print_exc()
  res.append(r)
  print(c['code'],c['ko'],c['home'],c['away'],'fm' if r.get('fotmob') else 'NO-FM',len((r.get('home_form') or {}).get('last') or []),len((r.get('away_form') or {}).get('last') or []),flush=True)
  json.dump(res,open('tahminler/grokbottahmin/2026-11-21/veri/iyms/collected.json','w'),ensure_ascii=False,default=str)
print('errors',f.http.errors[:20])
