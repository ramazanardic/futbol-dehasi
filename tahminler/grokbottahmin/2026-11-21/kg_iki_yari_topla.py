"""KG iki yarı (Evet/Evet) derin araştırma – veri toplama (FotMob, nazik, önbellekli)."""
import sys,json,datetime as dt,math,traceback
sys.path.insert(0,'src')
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.fotmob import FotMob,UA,BASE,parse_matches,find_match,parse_details
D='tahminler/grokbottahmin/2026-11-21/'
TSI=dt.timezone(dt.timedelta(hours=3))
ng=json.load(open(D+'nesine_global.json'))
NOW=dt.datetime.now(TSI)+dt.timedelta(minutes=10)
N=int(sys.argv[1]) if len(sys.argv)>1 else 28
rows=[]
for m in ng['matches']:
  k=dt.datetime.fromisoformat(m['kickoff_iso'])
  if k<NOW: continue
  sel={(s['market'],s['selection']):s for s in (m.get('selections') or [])}
  ee=sel.get(('1. Yarı / 2. Yarı Karşılıklı Gol','Evet/Evet'))
  if not ee: continue
  rows.append(dict(code=m['code'],ko=m['kickoff'],ko_iso=m['kickoff_iso'],league=m.get('league'),home=m['home'],away=m['away'],
    mu=[m.get('mu_home'),m.get('mu_away')],tier=m.get('price_tier'),ref=m.get('reference'),
    nesine={ (a+'|'+b):dict(odds=s['odds'],fair=s.get('fair_prob'),mbs=s.get('mbs')) for (a,b),s in sel.items() if a in (
      '1. Yarı / 2. Yarı Karşılıklı Gol','1. Yarı Karşılıklı Gol','2. Yarı Karşılıklı Gol','Karşılıklı Gol','2,5 Gol Alt/Üst','3,5 Gol Alt/Üst','1. Yarı 1,5 Gol Alt/Üst','Maç Sonucu')},
    research=m.get('research')))
rows.sort(key=lambda r:-(r['nesine']['1. Yarı / 2. Yarı Karşılıklı Gol|Evet/Evet']['fair'] or 0))
json.dump(dict(generated_at=ng['generated_at'],all=rows),open('tahminler/grokbottahmin/2026-11-21/veri/kg2/all_market.json','w'),ensure_ascii=False,default=str)
cand=rows[:N]
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
    # if extra time/pens, FT should be 90' score
    ftev=[e for e in ev if e.get('type')=='Half' and e.get('halfStrShort')=='FT']
    if ftev: ft=[ftev[0]['homeScore'],ftev[0]['awayScore']]
    home=x['home']['id']==tid
    pd=parse_details(d)
    xg=pd['stats']['home'].get('xg'),pd['stats']['away'].get('xg')
    gf1,ga1=(hth[0],hth[1]) if home else (hth[1],hth[0])
    gf2,ga2=(ft[0]-hth[0],ft[1]-hth[1]) if home else (ft[1]-hth[1],ft[0]-hth[0])
    out.append(dict(date=x['status']['utcTime'][:10],comp=x['tournament']['name'],venue='H' if home else 'A',
      opp=x['opponent']['name'],ht=hth,ft=ft,gf1=gf1,ga1=ga1,gf2=gf2,ga2=ga2,
      xgf=(xg[0] if home else xg[1]),xga=(xg[1] if home else xg[0]),red=pd['red']))
  nx=[dict(date=x['status']['utcTime'][:16],comp=x['tournament']['name'],opp=x['opponent']['name']) for x in nxt[:2]]
  top=[]
  try:
    for grp in (t.get('overview') or {}).get('topPlayers',{}).values():
      for p in (grp.get('players') or [])[:3]: top.append((p.get('name'),p.get('value')))
  except Exception: pass
  return dict(name=t['details'].get('name'),last=out,next=nx,top_players=top)
res=[]
for c in cand:
  r=dict(c)
  try:
    OVR={3314269:5875028,3313708:5772225,3313264:5881225,3313060:1000015509}
    mm=next((x for x in fm if x['id']==OVR.get(c['code'])),None) or find_match(fm,c['home'],c['away'],0.6)
    r['fotmob']=mm
    if mm:
      d=f.details(mm['id'],ttl_s=1800)
      hdr=d['header']['teams']; hid,aid=hdr[0]['id'],hdr[1]['id']
      pd=parse_details(d); r['today']={k:pd.get(k) for k in ('home_lineup','away_lineup','lineup_type','weather','referee','stadium')}
      # preview / h2h
      h2h=((d.get('content') or {}).get('h2h') or {}).get('matches') or []
      r['h2h']=[dict(date=(x.get('time') or {}).get('utcTime','')[:10],home=x['home']['name'],away=x['away']['name'],score=(x.get('status') or {}).get('scoreStr')) for x in h2h[:6]]
      r['home_form']=team_form(hid,mm['utc'])
      r['away_form']=team_form(aid,mm['utc'])
  except Exception as e:
    r['error']=repr(e); traceback.print_exc()
  res.append(r)
  print(c['code'],c['home'],c['away'],'fm' if r.get('fotmob') else 'NO-FM',len((r.get('home_form') or {}).get('last') or []),len((r.get('away_form') or {}).get('last') or []),flush=True)
json.dump(res,open('tahminler/grokbottahmin/2026-11-21/veri/kg2/collected.json','w'),ensure_ascii=False,default=str)
print('errors',f.http.errors[:20])
