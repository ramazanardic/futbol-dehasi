import csv,re
rows=[];seen=set()
for l in open('raw.txt',encoding='utf8'):
    l=l.rstrip('\n')
    if not l: continue
    tab,idx,cid,lt,legs=l.split('|',4)
    if cid in seen: continue
    seen.add(cid)
    m=re.match(r'(\d+ \S+ \d{4} \d\d:\d\d) (\d+) ([\d.,]+) (\S+) TL (.*)$',lt)
    dt,n,odds,stake,rest=m.groups()
    win=rest if 'TL' in rest else ''
    status={'Kazanan':'Kazandı','Kaybeden':'Kaybetti','Bekleyen':'Devam'}[tab]
    for leg in legs.split(' ## '):
        p=leg.split(';'); name,market,sel,lo,tm,score,ic=(p+['']*7)[:7]
        res='won' if ic=='ni-check' else 'lost' if ic=='ni-times' else 'void/unknown' if ic=='ni-void' else 'pending(live,'+('winning' if 'up' in ic else 'losing')+')' if 'thumbs' in ic else 'pending'
        rows.append([cid,dt,stake,odds,win,status,n,name,'',market,sel,lo,res,tm,score])
with open('nesine_kupon_gecmisi.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['coupon_id','placed','stake_TL','total_odds','win_TL','status','legs_count','match','league','market','selection','leg_odds','leg_result','time_state','score']);w.writerows(rows)
print(len(rows),len(seen))
