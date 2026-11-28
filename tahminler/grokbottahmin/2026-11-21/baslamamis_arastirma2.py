import json,sys,math,datetime as dt,itertools
from pathlib import Path
sys.path.insert(0,'src')
from quantfoot.data import fotmob as fmb
from quantfoot.data.match_dossier import CachedHttp, team_match_score
D='tahminler/grokbottahmin/2026-11-21/'
S=json.load(open('/tmp/ba_stage1.json'))
cands=S['cands']
banko=[c for c in cands if c['p']>=0.645 and 1.20<=c['odds']<=1.80]
best={}
for c in banko:
  if c['code'] not in best or (c['p'],c['ev'])>(best[c['code']]['p'],best[c['code']]['ev']): best[c['code']]=c
# keep all banko options per match for coupon search, but rank list by match-best
ranked=sorted(best.values(),key=lambda c:(-c['p'],-c['ev']))
fm=fmb.FotMob(CachedHttp(Path('tahminler/grokbottahmin/canli/onbellek')),delay_s=0.8)
ml=fmb.parse_matches(fm.matches_on(dt.date(2026,11,21)) or {})+fmb.parse_matches(fm.matches_on(dt.date(2026,11,22)) or {})
# European fixtures next week for rotation risk
EURO=('Champions League','Europa League','Conference League')
euro_teams={}
for d in range(23,28):
  for m in fmb.parse_matches(fm.matches_on(dt.date(2026,11,d)) or {}):
    if any(e in (m['league'] or '') for e in EURO) or 'Cup' in (m['league'] or '') or 'Kupa' in (m['league'] or '') or 'Pokal' in (m['league'] or '') or 'Copa' in (m['league'] or ''):
      for t in (m['home'],m['away']): euro_teams[t]=f"{m['league']} {str(m['utc'])[:10]}"
def rot(team):
  for t,v in euro_teams.items():
    if t and team_match_score(team,t)>=0.85: return v
  return None
def enrich(c):
  out={}
  m=fmb.find_match(ml,c['home'],c['away'])
  if not m: return {'fotmob':None}
  out['fotmob_id']=m['id']
  if m.get('ongoing') or m.get('finished'): out['started']=True
  try:
    d=fm.details(m['id'],ttl_s=3600) or {}
  except Exception as e:
    return out
  p=fmb.parse_details(d)
  for side in ('home','away'):
    lu=p.get(f'{side}_lineup') or {}
    out[f'{side}_unavailable']=[f"{u['name']} ({u['reason']})" for u in lu.get('unavailable') or []]
  tf=((d.get('content') or {}).get('matchFacts') or {}).get('teamForm') or []
  if len(tf)==2: out['form']=[''.join(x.get('resultString','') for x in tf[0]),''.join(x.get('resultString','') for x in tf[1])]
  ins=((d.get('content') or {}).get('matchFacts') or {}).get('insights') or []
  out['insights']=[i.get('text') for i in ins if isinstance(i,dict) and i.get('text')][:3]
  return out
top=ranked[:45]
for c in top:
  e=enrich(c); c.update(e)
  rh,ra=rot(c['home']),rot(c['away'])
  c['rotation']=[x for x in (f"{c['home']}: {rh}" if rh else None, f"{c['away']}: {ra}" if ra else None) if x]
  if e.get('started'): c['red'].append('maç başlamış/FotMob')
json.dump(dict(ranked=top,banko_all=banko,euro_teams=euro_teams),open('/tmp/ba_stage2.json','w'),ensure_ascii=False,default=str)
for c in top: print(c['code'],c['ko'][11:],c['match'],c['name'],c['odds'],c['p'],c['ev'],c['used'],c['red'],c.get('form'),'rot',c['rotation'],'abs',len(c.get('home_unavailable') or []),len(c.get('away_unavailable') or []))
