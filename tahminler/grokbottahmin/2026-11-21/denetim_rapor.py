"""denetim_topla.py çıktısından (/tmp/denetim/graded.json) kupon durumu, K/Z, kalibrasyon, geriye dönük banko koruması."""
import sys, json, math, collections, datetime as dt
sys.path.insert(0, 'src')
from quantfoot.strategy import banko_guard as bg
D = 'tahminler/grokbottahmin/2026-11-21/'
g = json.load(open('/tmp/denetim/graded.json'))
P, picks = g['placed'], g['picks']
LIVE_MKT = {3307474: 0.205, 3314339: 0.627, 3405042: 0.505}
rows = []; staked = lost = 0; won_ret = 0
for cid, c in P.items():
    legs = [picks[i] for i in c['legs']]
    st = [l['status'] for l in legs]
    if 'kaybetti' in st: cs = 'KAYBETTİ'
    elif all(s == 'kazandı' for s in st): cs = 'KAZANDI'
    else: cs = 'devam'
    pw = math.prod(l['p'] for l in legs)
    alive_p = math.prod(l['p'] for l in legs if l['status'] != 'kazandı') if cs == 'devam' else (0 if cs == 'KAYBETTİ' else 1)
    staked += c['stake']; lost += c['stake'] if cs == 'KAYBETTİ' else 0; won_ret += c['stake'] * c['odds'] if cs == 'KAZANDI' else 0
    guard = bg.check_coupon([bg.BankoLeg(l['code'], f"{l['match']} {l['name'] or l['sel']}", l['odds'], l['p'],
                                         offered=True, live=(cid == 'CANLI'), p_market=LIVE_MKT.get(l['code'])) for l in legs],
                            at_selection=False)
    rows.append(dict(id=cid, odds=c['odds'], stake=c['stake'], max_win=round(c['stake'] * c['odds'], 2), status=cs,
                     p_win_model=round(pw, 4), p_win_now=round(alive_p, 4), ev_tl=round(c['stake'] * (pw * c['odds'] - 1), 1),
                     legs_won=st.count('kazandı'), legs_lost=st.count('kaybetti'), legs_pending=len(st) - st.count('kazandı') - st.count('kaybetti'),
                     last_ko=max(l['ko'] for l in legs), note=c.get('note', ''),
                     guard_ok=guard.ok, guard_errors=guard.errors,
                     legs=[dict(code=l['code'], match=l['match'], pick=l['name'] or l['sel'], odds=l['odds'], p=l['p'], ko=l['ko'],
                                status=l['status'], state=l['result']['state'], ht=l['result'].get('ht'), ft=l['result'].get('ft'),
                                score_now=l['result'].get('score'), minute=l['result'].get('minute'),
                                red=l['result'].get('red_status'), reason=l['result'].get('reason'),
                                fm_match=l['result'].get('fm_match')) for l in legs]))
# kalibrasyon (sonuçlanan bütün benzersiz seçimler)
uniq = {}
for p in picks:
    k = (p['code'], p['name'] or p['sel'])
    if k not in uniq or p['src'] == 'oynanan': uniq[k] = p
settled = [p for p in uniq.values() if p['won'] in (True, False) and p['p']]
def bucket(x): return '<0.40' if x < .4 else '0.40–0.55' if x < .55 else '0.55–0.65' if x < .65 else '0.65–0.75' if x < .75 else '≥0.75'
cal = collections.defaultdict(lambda: [0, 0, 0.0])
for p in settled:
    b = cal[bucket(p['p'])]; b[0] += 1; b[1] += p['won']; b[2] += p['p']
calib = {k: dict(n=v[0], hit=v[1], expected=round(v[2], 2)) for k, v in sorted(cal.items())}
exposure = collections.Counter()
for c in P.values():
    for i in c['legs']: exposure[picks[i]['match']] += 1
out = dict(generated_at=dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).isoformat(timespec='minutes'),
           coupons=rows, staked_tl=staked, lost_tl=lost, returned_tl=won_ret,
           pnl_settled_tl=won_ret - lost, open_stake_tl=staked - lost - (sum(r['stake'] for r in rows if r['status'] == 'KAZANDI')),
           expected_return_tl=round(sum(r['stake'] * r['p_win_model'] * r['odds'] for r in rows), 1),
           open_max_return_tl=round(sum(r['max_win'] for r in rows if r['status']=='devam'), 2),
           n_coupons=len(rows),
           settled_unique_picks=len(settled), calibration=calib,
           settled=[dict(match=p['match'], pick=p['name'] or p['sel'], odds=p['odds'], p=p['p'], won=p['won'], src=p['src'],
                         ht=p['result'].get('ht'), ft=p['result'].get('ft')) for p in settled],
           pending_unique=sum(1 for p in uniq.values() if p['won'] is None),
           match_exposure={k: v for k, v in exposure.items() if v > 1})
json.dump(out, open('/tmp/denetim/rapor.json', 'w'), ensure_ascii=False, indent=1)
for r in rows: print(r['id'], r['odds'], r['stake'], r['status'], f"W{r['legs_won']} L{r['legs_lost']} P{r['legs_pending']}", 'Pmodel', r['p_win_model'], 'Pnow', r['p_win_now'], 'EV', r['ev_tl'], r['last_ko'], 'guard', r['guard_ok'], r['guard_errors'][:2])
print({k: out[k] for k in ('staked_tl', 'lost_tl', 'returned_tl', 'pnl_settled_tl', 'open_stake_tl', 'open_max_return_tl', 'expected_return_tl', 'settled_unique_picks', 'pending_unique', 'n_coupons')})
print(calib); print(out['match_exposure'])
for s in out['settled']: print(s)
