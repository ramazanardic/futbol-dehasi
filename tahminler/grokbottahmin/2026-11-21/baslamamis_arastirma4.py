import json,math,itertools
D='tahminler/grokbottahmin/2026-11-21/'
out=json.load(open(D+'baslamamis_arastirma.json'))
S1=json.load(open('/tmp/ba_stage1.json'))
soft={c['code'] for c in out['top20'] if c['soft_flags']}|{c['code'] for c in out['red_flagged']}
# steam check: big steam against favourite in goal markets -> treat Feyenoord (-7.4 home) as soft
soft.add(3313263)
clean=[c for c in out['top20'] if c['code'] not in soft and not c['used']]
def bestN(pool,n,minO=1.0,excl=set()):
  pool=[c for c in pool if c['code'] not in excl]; best=None
  for comb in itertools.combinations(pool,n):
    if len({c['code'] for c in comb})<n or max(c['mbs'] or 1 for c in comb)>n: continue
    O=math.prod(c['odds'] for c in comb)
    if O<minO: continue
    P=math.prod(c['p'] for c in comb)
    if best is None or P>best[0]: best=(P,O,comb)
  return best
K=('code','ko','league','match','market','sel','odds','p','fair','ev','mbs','ref')
def fmt(b): return dict(total_odds=round(b[1],3),p_win=round(b[0],4),ev=round(b[0]*b[1]-1,4),legs=[{k:c.get(k) for k in K} for c in b[2]])
out['coupons']={n:fmt(bestN(clean,n)) for n in (2,3,4)}
out['coupon_pool_excluded_soft']=sorted(soft)
# 5-leg >=5.00
opts={}
for c in S1['cands']:
  if c['code'] in soft or c['used'] or c['red'] or c['p']<0.58 or not (1.20<=c['odds']<=1.80): continue
  opts.setdefault(c['code'],[]).append(c)
pool=[]
for v in opts.values(): pool+=sorted(v,key=lambda c:-c['p'])[:2]
pool=sorted(pool,key=lambda c:-(math.log(c['p'])/max(math.log(c['odds']),1e-6)))[:28]  # efficiency: least P loss per odds
c5=[];excl=set()
for i in range(3):
  b=bestN(pool,5,5.0,excl)
  if not b: break
  c5.append(fmt(b)); excl|={c['code'] for c in b[2]}
out['coupons_5leg_min5']=c5
out['notes'].append('5 maç ≥5.00: P ≥%64.5 bacaklarla matematiksel olarak imkânsız (en yüksek oranlı 5 banko bacağın çarpımı ≈4.45); bu yüzden 5 maçlık kuponlarda bacak P alt sınırı %58’e indirildi.')
out['notes'].append('Kupon havuzundan çıkarılanlar (rotasyon/çok eksik/FotMob yok/steam): '+', '.join(map(str,sorted(soft))))
json.dump(out,open(D+'baslamamis_arastirma.json','w'),ensure_ascii=False,indent=1,default=str)
for n,v in out['coupons'].items(): print(n,v['total_odds'],v['p_win'],v['ev'],[(l['code'],l['ko'][11:],l['match'],l['market'],l['sel'],l['odds'],l['p']) for l in v['legs']])
for v in c5: print('5L',v['total_odds'],v['p_win'],v['ev']); [print('   ',l['code'],l['ko'][11:],l['league'],l['match'],'|',l['market'],l['sel'],l['odds'],l['p'],l['fair'],l['ev'],l['mbs'],l['ref'][:9]) for l in v['legs']]
