import json,math,random,sys
D='tahminler/grokbottahmin/2026-11-21/'
pool=json.load(open(D+'kupon5000_havuz.json'))
ANCH={3319709:'MS 1',3314542:'Dep 0.5 Alt'}
extra=json.load(open(D+'kupon5000_ankraj.json'))  # current Pécs/Espanyol legs
pool=[r for r in pool if r['code'] not in ANCH]
MAXO=float(sys.argv[1]) if len(sys.argv)>1 else 3.5
cand=[r for r in pool if 1.40<=r['odds']<=MAXO][:40]
random.seed(7)
def score(c):
  o=math.prod(l['odds'] for l in c); 
  pen=0 if 20<=o<=30 else 50*abs(math.log(o/25))
  n=len(c); pen+= 0 if 3<=n<=6 else 5
  return sum(math.log(l['p']*l['odds']) for l in c)-pen-0.3*abs(math.log(o/25))
best=None
for it in range(4000):
  c=[[extra[0]],[extra[1]],[],[]]
  used=set()
  order=cand[:]; random.shuffle(order)
  order.sort(key=lambda r:-(math.log(r['p']*r['odds'])/math.log(r['odds']))+random.gauss(0,0.03))
  for k in range(4):
    for r in order:
      if r['code'] in used: continue
      o=math.prod(l['odds'] for l in c[k])
      if o*r['odds']<=30 and len(c[k])<6:
        c[k].append(r); used.add(r['code'])
      if math.prod(l['odds'] for l in c[k])>=20: break
  tot=sum(score(x) for x in c)
  if best is None or tot>best[0]: best=(tot,c)
out=[]
for c in best[1]:
  o=math.prod(l['odds'] for l in c); p=math.prod(l['p'] for l in c)
  out.append(dict(legs=c,odds=round(o,2),payout50=round(50*o,2),p=p,ev=p*o-1))
for k,c in enumerate(out,1):
  print(f"K{k} oran {c['odds']} ödeme {c['payout50']} p {c['p']*100:.2f}% EV {c['ev']*100:+.1f}%")
  for l in c['legs']: print('  ',l['code'],l['ko'],l['match'],l['sel'],l['odds'],l['fair'],f"{l['ev']*100:+.1f}%",l['ref'])
pl=1
for c in out: pl*=1-c['p']
print('P(en az 1)',1-pl,'P(hepsi kaybeder)',pl,'beklenen ödeme',sum(50*c['odds']*c['p'] for c in out))
json.dump(out,open(D+'kupon5000_taslak.json','w'),ensure_ascii=False,indent=1)
