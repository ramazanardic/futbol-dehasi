"""21.11.2026 denetim — bugün verilen tüm seçimleri topla, FotMob'dan sonuç çek, notla.
API-Football KULLANILMAZ. Sonuç uydurulmaz: bulunamayan maç 'eşleşmedi', bitmeyen 'bekliyor'."""
import sys, json, math, re, datetime as dt
from pathlib import Path
sys.path.insert(0, 'src')
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.fotmob import FotMob, parse_matches, find_match, parse_details

D = Path('tahminler/grokbottahmin/2026-11-21')
TSI = dt.timezone(dt.timedelta(hours=3))
J = lambda f: json.load(open(D / f))
ng = J('nesine_global.json')
NG = {m['code']: m for m in ng['matches']}

picks = []
def _ko(k):
    if not k or len(k) > 5: return k
    return ('2026-11-22 ' if int(k[:2]) < 10 else '2026-11-21 ') + k
def add(src, code, match, market, sel, name, odds, p, ko=None, placed=None, extra=None):
    m = NG.get(code) or {}
    home, away = (m.get('home'), m.get('away')) if m else tuple((match or ' - ').split(' - ', 1))
    picks.append(dict(src=src, code=code, match=match or f"{home} - {away}", home=home, away=away,
                      ko=_ko(m.get('kickoff') or ko), league=m.get('league'), market=market, sel=sel, name=name,
                      odds=odds, p=p, placed=placed or [], **(extra or {})))

# ---- OYNANAN KUPONLAR -------------------------------------------------------------
PLACED = {}
def coupon(cid, stake, odds, legs, note=''):
    PLACED[cid] = dict(id=cid, stake=stake, odds=odds, note=note, legs=[])
    for l in legs:
        add('oynanan', *l, placed=[cid]); PLACED[cid]['legs'].append(len(picks) - 1)

k5000 = J('kupon_5000.json')['set_A_onerilen_az_bacak']['kuponlar']
def legs_from(lst):
    return [(l['code'], l['match'], l.get('market'), l['sel'], l['sel'], l['odds'], l['p'], l.get('ko')) for l in lst]
coupon('K1', 50, 24.97, legs_from(k5000[0]['legs']))
coupon('K3', 50, 26.11, legs_from(k5000[2]['legs']), 'bacaklar Set A Kupon 3 dosyasından (oynanırken oran 25.85→26.11)')
coupon('K4', 50, 24.72, legs_from(k5000[3]['legs']), 'bacaklar Set A Kupon 4 dosyasından (oynanırken oran 25.15→24.72)')
coupon('K5', 50, 20.49, [(l['code'], l['match'], l['nesine_market'], l['nesine_selection'], l['nesine_label'], l['odds'], l['model_p'], '2026-11-21 ' + l['kickoff_tsi']) for l in J('kupon_5.json')['legs']])
coupon('K6', 50, 20.82, [(l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko']) for l in J('kupon_6.json')['legs']])
b7 = J('kupon_7_banko.json')
b5 = {l['code']: l for l in b7['coupons']['5']['legs']}
ant = next(x for x in b7['backups'] if x['code'] == 3318505)
bl = [b5[3313572], dict(b5[3312753], odds=1.67), ant, b5[3313774], b5[3314607]]
coupon('B5', 400, 7.27, [(l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko']) for l in bl],
       'Espanyol ÇŞ1X yerine Antequera 3,5 Alt (yedek); Coleraine 1.67')
coupon('MS10', 100, 7.67, [(l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko']) for l in J('kupon_10ms1.json')['legs']])
coupon('CANLI', 70, 7.64, [
    (3307474, 'Kokand 1912 - Sogdiana', 'Canlı Maç Sonucu', '1', 'MS 1', 3.79, 0.317, '2026-11-21 15:00'),
    (3314339, 'Khor Fakkan - AL Jazira (Bae)', 'Canlı Maç Sonucu', '2', 'MS 2', 1.26, 0.808, '2026-11-21 15:45'),
    (3405042, 'Reading - Bromley', 'Canlı Ev 1,5 Alt/Üst', '1,5 Üst', 'Ev 1.5 Üst', 1.60, 0.644, '2026-11-21 15:30')],
    'canlı model P (oynanırken); piyasa P: Kokand 0.205, Khor 0.627, Reading 0.505')
LIVE_MKT_P = {3307474: 0.205, 3314339: 0.627, 3405042: 0.505}
A = J('baslamamis_arastirma.json')['coupons_5leg_min5'][0]['legs']
coupon('A5', 100, 5.00, [(l['code'], l['match'], l['market'], l['sel'], l['sel'], (1.45 if l['code'] == 3318770 else l['odds']), l['p'], l['ko']) for l in A])
kb = J('kupon_10_banko.json')['legs']
# West Ham bültenden düşmüş olabilir (18:00 başladı). Yerleştirme anı: μ_dep=0.771, Genk fair P=0.70826.
wh = NG.get(3314223) or {}
mu_a = wh.get('mu_away') or 0.771
genk = NG.get(3313833) or {}
genk_p = next((s['fair_prob'] for s in genk.get('selections', [])
               if s.get('market') == 'Maç Sonucu' and s.get('selection') == '1'), 0.70826)
coupon('B10', 150, 6.84, [(l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko']) for l in kb if l['code'] not in (3313082, 3339060)] + [
    (3313833, 'KRC Genk - RAAL La Louviere', 'Maç Sonucu', '1', 'MS 1', 1.25, genk_p, '2026-11-21 20:15'),
    (3314223, 'West Ham - Preston', 'Deplasman 1. Yarı 0,5 Gol Alt/Üst', '0,5 Alt', 'Dep İY 0.5 Alt', 1.21, round(math.exp(-0.45 * mu_a), 4), '2026-11-21 18:00')],
    'Tottenham Dep1,5Alt ve Mineiro Dep0,5Ü düşürüldü (oran <1.20); Genk + West Ham eklendi; West Ham P ≈ exp(-0.45·μ_dep)')
k2 = J('kupon_2000.json')
# Oynanırken yükselen oranlar: Pontevedra 1.60→1.69, Águila 1.46→1.48; toplam 6.74→7.21
_placed_odds_2000 = {3319685: 1.69, 3312935: 1.48}
coupon('K2000', 300, 7.21, [
    (l['code'], l['match'], l['market'], l['sel'], l['name'],
     _placed_odds_2000.get(l['code'], l['odds']), l['p'], l['ko'])
    for l in k2['legs']
], 'oynanırken Pontevedra 1.60→1.69, Águila 1.46→1.48; toplam 6.74→7.21, maks 2.163,41 TL')

# ---- ÖNERİLEN AMA OYNANMAYAN ------------------------------------------------------
for i, c in enumerate(J('kupon_5000.json')['set_B_1.40_2.30_4_6_bacak']['kuponlar']):
    for l in c['legs']: add(f'öneri:5000-B{i+1}', l['code'], l['match'], l.get('market'), l['sel'], l['sel'], l['odds'], l['p'], l.get('ko'))
add('öneri:5000-A2', *legs_from(k5000[1]['legs'])[0])  # Pécs (Nesine'de yoktu)
for l in k5000[1]['legs'][1:]: add('öneri:5000-A2', *legs_from([l])[0])
for l in J('kupon_7.json')['legs']: add('öneri:kupon7', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
for k, c in b7['coupons'].items():
    for l in c['legs']: add(f'öneri:banko7-{k}', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
bk = J('banko_kupon.json')
for l in bk['top10']: add('öneri:banko_top10', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
for l in J('kupon_10ms1.json')['backups']: add('öneri:ms10-yedek', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
for l in kb: add('öneri:banko10-ilk', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
ba = J('baslamamis_arastirma.json')
for l in ba['top20']: add('öneri:baslamamis_top20', l['code'], l['match'], l['market'], l['sel'], l['name'], l['odds'], l['p'], l['ko'])
for j, c in enumerate(ba['coupons_5leg_min5']):
    for l in c['legs']: add(f'öneri:5li_{"ABC"[j] if j < 3 else j}', l['code'], l['match'], l['market'], l['sel'], l['sel'], l['odds'], l['p'], l['ko'])
for l in J('kg_iki_yari_detay.json')['ranking']:
    pp = l.get('final_p') or l.get('p_final') or l.get('blend_p') or l.get('engine_p')
    add('öneri:kg_iki_yari', l['code'], l['match'], '1. Yarı / 2. Yarı Karşılıklı Gol', 'Evet/Evet', 'KGKG', l.get('nesine_odds'), pp, l['ko'])
for l in J('iyms_detay.json')['coupon_legs']:
    add('öneri:iyms', l['code'], l['match'], l['market'], l['selection'], 'İYMS ' + l['selection'], l['odds'], l['P'], l['ko'])

# ---- SONUÇLAR (FotMob) -------------------------------------------------------------
f = FotMob(CachedHttp(Path('/tmp/denetim/cache')), delay_s=0.7)
fm = []
for day in (dt.date(2026, 11, 21), dt.date(2026, 11, 22)):
    fm += parse_matches(f.matches_on(day, ttl_s=600) or {})
OVR = {3314269: 5875028, 3313708: 5772225, 3313264: 5881225, 3313060: 1000015509,
       3319709: 5884617, 3319368: 5884922, 3314719: 5853554, 3318770: 5977807, 3314647: 5836938}
res_cache = {}
def result(p):
    code = p['code']
    if code in res_cache: return res_cache[code]
    ko = dt.datetime.strptime(p['ko'], '%Y-%m-%d %H:%M').replace(tzinfo=TSI) if p.get('ko') else None
    cand = fm
    if ko:
        cand = [m for m in fm if m.get('utc') and abs((dt.datetime.fromisoformat(m['utc'].replace('Z', '+00:00')) - ko).total_seconds()) <= 3 * 3600]
    mm = next((m for m in fm if m['id'] == OVR.get(code)), None) or find_match(cand, p['home'] or '', p['away'] or '', 0.6)
    r = dict(fotmob_id=None, state='eşleşmedi')
    if mm:
        r.update(fotmob_id=mm['id'], fm_match=f"{mm['home']} - {mm['away']}", state='bitti' if mm['finished'] else ('canlı' if mm['ongoing'] else 'başlamadı'),
                 minute=mm.get('minute'), score=[mm['hg'], mm['ag']])
        if mm['finished'] or mm['ongoing']:
            d = f.details(mm['id'], ttl_s=None if mm['finished'] else 300) or {}
            st = (d.get('header') or {}).get('status') or {}
            # Liste "bitti" dese de önbellekteki detay hâlâ canlı kalmış olabilir — yenile.
            if mm['finished'] and st.get('ongoing') and not st.get('finished'):
                d = f.details(mm['id'], ttl_s=0) or d
                st = (d.get('header') or {}).get('status') or {}
            ev = ((d.get('content') or {}).get('matchFacts') or {}).get('events', {}).get('events') or []
            ht = [e for e in ev if e.get('type') == 'Half' and e.get('halfStrShort') == 'HT']
            ft = [e for e in ev if e.get('type') == 'Half' and e.get('halfStrShort') == 'FT']
            pd = parse_details(d)
            r['ht'] = [ht[0]['homeScore'], ht[0]['awayScore']] if ht else None
            if ft:
                r['ft'] = [ft[0]['homeScore'], ft[0]['awayScore']]
            elif st.get('finished') and pd.get('score'):
                r['ft'] = pd.get('score')
            elif mm['finished']:
                r['ft'] = [mm['hg'], mm['ag']]  # liste skoru; bayat detaya güvenme
            else:
                r['ft'] = None
            r['red_status'] = pd['red']; r['red_stats'] = [pd['stats']['home'].get('red'), pd['stats']['away'].get('red')]
            r['reason'] = (st.get('reason') or {}).get('short') or ((mm.get('reason') if isinstance(mm.get('reason'), str) else None))
            if st.get('finished') or mm['finished']:
                r['state'] = 'bitti'
                r['score'] = r.get('ft') or r['score']
                r['minute'] = None
            elif st.get('ongoing') or mm['ongoing']:
                r['state'] = 'canlı'
                r['score'] = pd.get('score') or r['score']
    res_cache[code] = r
    return r

def _line(s):
    m = re.search(r'(\d+)[.,](5)', s); return float(f"{m.group(1)}.5") if m else None

def grade(p, r):
    """True/False/None (None = belirlenemez/bekliyor). Kapanmış yarı marketleri canlıda karara bağlanabilir."""
    name = f"{p.get('market') or ''} | {p.get('sel') or ''} | {p.get('name') or ''}"
    ht, ft = r.get('ht'), r.get('ft')
    if r['state'] != 'bitti' or ft is None:
        return None
    if ht is None and re.search(r'İY|1\. Yarı|2Y|İlk Yarı|Evet/Evet|Dep İY', name):
        return None
    h, a = ft; h1, a1 = ht if ht else (None, None)
    h2, a2 = (h - h1, a - a1) if ht else (None, None)
    nm, mk, sel = p.get('name') or '', p.get('market') or '', str(p.get('sel') or '')
    def ou(goals, s):
        ln = _line(s); return (goals > ln) if 'Üst' in s else (goals < ln)
    def ms(x, hh, aa):
        return {'1': hh > aa, '2': aa > hh, '0': hh == aa, 'X': hh == aa}[x]
    if nm == 'KGKG': return h1 > 0 and a1 > 0 and h2 > 0 and a2 > 0
    if nm.startswith('İYMS'):
        a_, b_ = sel.split('/'); return ms(a_, h1, a1) and ms(b_, h, a)
    if '&' in sel or ' ve ' in sel or ('&' in mk):
        parts = re.split(r'\s*&\s*|\s+ve\s+', sel.replace('MS ', 'MS '))
        out = True
        for part in parts:
            part = part.strip()
            if part.startswith('MS'): out &= ms(part.split()[1], h, a)
            elif part.startswith('İY KG'): out &= ((h1 > 0 and a1 > 0) == ('Var' in part))
            elif part.startswith('İY'): out &= ms(part.split()[1], h1, a1)
            elif part.startswith('KG'): out &= ((h > 0 and a > 0) == ('Var' in part))
            elif 'Alt' in part or 'Üst' in part: out &= ou(h + a, part)
            else: return None
        return out
    if mk == 'Maç Sonucu' or mk == 'Canlı Maç Sonucu' or re.fullmatch(r'MS [102X]', nm):
        return ms((sel if sel in '102X' else nm.split()[-1]), h, a)
    if 'Çifte' in mk or nm.startswith('ÇŞ'):
        s = nm.replace('ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        return any(ms(c, h, a) for c in s)
    if 'Handikap' in mk:
        hc = int(re.search(r'\((-?\d+)\)', nm).group(1)); hh = h + hc
        return ms(nm.split()[-1], hh, a)
    if mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102]', nm): return ms(nm.split()[-1], h1, a1)
    if nm.startswith('2Y'): return ms(nm.split()[-1], h2, a2)
    if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'): return ou(a1, sel)
    if mk.startswith('1. Yarı') and ('Alt' in sel or 'Üst' in sel): return ou(h1 + a1, sel)
    if mk.startswith('Deplasman') or 'Ev Sahibi' in mk or mk.startswith('Canlı Ev') or nm.startswith(('Dep ', 'Ev ')):
        g = a if (mk.startswith('Deplasman') or nm.startswith('Dep')) else h
        return ou(g, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Karşılıklı' in mk: return (h > 0 and a > 0) == (sel in ('Var', 'Evet'))
    if 'Tek' in sel or 'Tek' in nm: return (h + a) % 2 == 1
    if 'Alt' in sel or 'Üst' in sel or 'Alt' in nm or 'Üst' in nm: return ou(h + a, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    return None

def early_decide(p, r):
    """Canlı maçta zaten kesinleşmiş bacaklar (ör. Üst geçti, ya da İY bitmiş).
    Yalnız matematiksel olarak kesin sonuç döner; aksi halde None."""
    if r['state'] != 'canlı': return None
    sc = r.get('score')
    if not sc or sc[0] is None: return None
    h, a = sc; nm, sel = p.get('name') or '', str(p.get('sel') or '')
    mk = p.get('market') or ''
    ht = r.get('ht')
    # 1. yarı skoru: devre bittiyse HT, aksi halde (hâlâ ilk yarıdaysak) anlık skor
    h1 = a1 = None
    if ht:
        h1, a1 = ht
    elif r.get('minute') is not None and r['minute'] <= 45:
        h1, a1 = h, a

    def ou_decided(goals, s):
        ln = _line(s)
        if ln is None: return None
        if 'Üst' in s and goals > ln: return True
        if 'Alt' in s and goals > ln: return False
        return None  # çizgi aşılmadı; Alt ancak yarı/maç bitince kazanır

    def ou_final(goals, s):
        ln = _line(s)
        if ln is None: return None
        return (goals > ln) if 'Üst' in s else (goals < ln)

    if mk in ('2,5 Gol Alt/Üst', '3,5 Gol Alt/Üst') or re.fullmatch(r'\d\.5 (Alt|Üst)', nm):
        s = sel if ('Alt' in sel or 'Üst' in sel) else nm
        g = ou_decided(h + a, s)
        if g is not None: return g
    if ('3,5 Alt' in sel or '3.5 Alt' in nm or '3,5 Alt' in nm) and h + a > 3.5: return False
    if ('2,5 Alt' in sel or '2.5 Alt' in nm or '2,5 Alt' in nm) and h + a > 2.5: return False

    if (mk.startswith('Deplasman 0,5') or nm.startswith('Dep 0.5')) and 'Üst' in (sel + nm) and a > 0: return True
    if (mk.startswith('Ev Sahibi') or nm.startswith('Ev 0.5')) and 'Üst' in (sel + nm) and h > 0: return True
    if 'Karşılıklı' in mk and sel in ('Var', 'Evet') and h > 0 and a > 0: return True
    if 'KG Yok' in (sel + nm) and h > 0 and a > 0: return False
    if nm == 'KGKG' and ht and (ht[0] == 0 or ht[1] == 0): return False

    if ht and (mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102X]', nm)):
        x = nm.split()[-1]
        if x in '102X':
            return {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]
    if ht and nm.startswith('İYMS'):
        x = (sel.split('/')[0] if '/' in sel else '')
        if x in '102X' and not {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]:
            return False

    if h1 is not None:
        iy_s = sel if ('Alt' in sel or 'Üst' in sel) else nm
        if mk.startswith('1. Yarı 0,5') or nm.startswith('İY 0.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(h1 + a1, iy_s)
        if mk.startswith('1. Yarı 1,5') or '1. Yarı 1,5' in mk or nm.startswith('İY 1.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(h1 + a1, iy_s)
        if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'):
            g = ou_decided(a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(a1, iy_s)
    return None


for p in picks:
    r = result(p); p['result'] = r
    g = grade(p, r)
    if g is None: g = early_decide(p, r)
    p['won'] = g
    p['status'] = 'kazandı' if g is True else 'kaybetti' if g is False else ('bekliyor' if r['state'] in ('canlı', 'başlamadı') else r['state'])

json.dump(dict(generated_at=dt.datetime.now(TSI).isoformat(timespec='minutes'), placed=PLACED, picks=picks), open('/tmp/denetim/graded.json', 'w'), ensure_ascii=False, indent=1, default=str)
for cid, c in PLACED.items():
    print(f"== {cid} {c['odds']} {c['stake']} TL")
    for i in c['legs']:
        p = picks[i]; r = p['result']
        print(f"   {p['match'][:34]:34} {p['name'] or p['sel']:16} {p['odds']:5} P{(p['p'] or 0):.2f} -> {p['status']:9} {r.get('fm_match','')[:30]:30} HT{r.get('ht')} FT{r.get('ft')} sc{r.get('score')} red{r.get('red_status')}/{r.get('red_stats')} {r['state']}")
