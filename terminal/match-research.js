"use strict";

const searchForm = get("match-research-form");
const resultPanel = get("live-result");
const liveStatus = get("live-status");
const liveButton = get("submit-live");
const researchSite = "https://quantfoot-terminal-ramazan.ramazanardic.chatgpt.site/";
const longDate = new Intl.DateTimeFormat("tr-TR",{timeZone:"Europe/Istanbul",dateStyle:"medium",timeStyle:"short"});
const shortDate = new Intl.DateTimeFormat("tr-TR",{timeZone:"Europe/Istanbul",dateStyle:"short"});
const validMoment = value => Number.isFinite(Date.parse(value));
const showDate = (value,formatter=longDate) => validMoment(value) ? formatter.format(new Date(value)) : "";
const toText = value => value === null || value === undefined || value === "" ? "—" : escapeHtml(value);

function statusLabel(type) {
  const labels = {STATUS_SCHEDULED:"Başlamadı",STATUS_IN_PROGRESS:"Devam ediyor",STATUS_HALFTIME:"İlk yarı bitti",
    STATUS_FULL_TIME:"Bitti",STATUS_FINAL:"Bitti",STATUS_POSTPONED:"Ertelendi",STATUS_CANCELED:"İptal",
    STATUS_SUSPENDED:"Askıya alındı",STATUS_DELAYED:"Gecikmeli"};
  return Object.hasOwn(labels,type) ? labels[type] : "Durum doğrulanmadı";
}

function reveal(label,content,open=false) {
  return '<details class="panel research-block"'+(open ? " open" : "")+'><summary>'+label+'</summary><div class="live-detail">'+content+'</div></details>';
}

function list(items,empty) {
  return items.length ? "<ul>"+items.map(item=>"<li>"+escapeHtml(item)+"</li>").join("")+"</ul>" : '<p class="muted">'+empty+'</p>';
}

function teamSection(home,away,entries) {
  return '<div class="workspace"><div><h3>'+escapeHtml(home)+'</h3>'+entries[0]+'</div><div><h3>'+escapeHtml(away)+'</h3>'+entries[1]+'</div></div>';
}

function quickTable(teams,game) {
  const keys = {rank:"Lig sırası",points:"Puan",played:"Oynanan maç",won:"Galibiyet",
                drawn:"Beraberlik",lost:"Mağlubiyet",goalDiff:"Averaj"};
  const rows = Object.entries(keys).map(([key,label])=>[label,teams[0]?.table?.[key],teams[1]?.table?.[key]]);
  const matched = teams.map(team=>new Map(safeArray(team.stats).map(s=>[s.name,s.value])));
  for (const title of new Set([...matched[0].keys(),...matched[1].keys()])) {
    rows.push([title,...matched.map(stats=>stats.get(title))]);
  }
  const cells = rows.filter(r=>r[1] != null || r[2] != null).map(r=>'<tr><th scope="row">'+escapeHtml(r[0])+'</th><td>'+toText(r[1])+'</td><td>'+toText(r[2])+'</td></tr>').join("");
  return cells ? '<div class="scroll"><table><thead><tr><th>İstatistik</th><th>'+escapeHtml(game.home)+'</th><th>'+escapeHtml(game.away)+'</th></tr></thead><tbody>'+cells+'</tbody></table></div>'
    : '<p class="muted">Seçilen maç için lig tablosu veya maç istatistiği bulunamadı.</p>';
}

function marketRows(data) {
  return safeArray(data).flatMap(offer => {
    if (!offer.provider) return [];
    const parts = [offer.provider,offer.line,
      offer.total != null ? "Gol çizgisi "+offer.total : null,
      safeArray(offer.moneyline).some(x=>x != null) ? "1 / X / 2 ("+offer.moneyline.map(x=>x ?? "—").join(" / ")+")" : null
    ].filter(x=>x != null && x !== "");
    return [parts.join(" · ")];
  });
}

function allowedSource(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["www.espn.com","api.open-meteo.com","fantasy.premierleague.com"].includes(url.hostname);
  } catch { return false; }
}

function renderReport(data) {
  const game = data.game, teams = data.teams;
  const score = game.status !== "STATUS_SCHEDULED" && safeArray(game.score).length === 2 && game.score.every(s=>s!=null)
    ? '<span class="fixture-score">'+game.score.map(escapeHtml).join(" – ")+'</span>' : "";
  const context = [game.league,showDate(game.kickoff)+" TSİ",game.venue,statusLabel(game.status)].filter(Boolean).map(escapeHtml).join(" · ");
  const form = teams.map(team=>list(safeArray(team.recent).map(g=>[showDate(g.date,shortDate),g.opponent,g.score,{W:"G",D:"B",L:"M"}[g.result]].filter(Boolean).join(" · ")), "Kaynakta son maç kaydı bulunamadı."));
  const squad = teams.map(team=>{
    const availability = new Map([...safeArray(team.unavailable),...safeArray(team.availability)].filter(p=>p.name).map(p=>[p.name,p.status]));
    const absences = [...availability.entries()].map(([name,state])=>[name,state].filter(Boolean).join(" · "));
    return '<p class="live-note">İlk 11</p>'+list(safeArray(team.lineup),"Doğrulanmış ilk 11 bulunamadı.")+
      '<p class="live-note">Sakat, cezalı ve şüpheli oyuncular</p>'+list(absences,team.officialAvailability
        ? "Resmî listede bu takım için kayıt yok." : "Bu kaynakta oyuncu durumu doğrulanamadı.");
  });
  const leaders = teams.map(team=>list(safeArray(team.leaders).map(p=>[p.player,p.category,p.value].filter(Boolean).join(" · ")), "Oyuncu liderleri yayımlanmamış."));
  const h2h = safeArray(data.h2h).map(g=>[showDate(g.date,shortDate),g.name,typeof g.score === "string" ? g.score : ""].filter(Boolean).join(" · "));
  const sources = safeArray(data.sources).filter(s=>allowedSource(s.url)).map(s=>'<a href="'+escapeHtml(s.url)+'" target="_blank" rel="noopener noreferrer">'+escapeHtml(s.name)+'</a>').join("");
  const weather = data.weather;
  const wx = weather ? [
    weather.temp == null ? null : weather.temp+" °C",
    weather.rain == null ? null : weather.rain+" mm yağış",
    weather.wind == null ? null : weather.wind+" km/sa rüzgâr"
  ].filter(Boolean) : [];
  const weatherText = weather && wx.length ? '<p>'+escapeHtml([weather.city,showDate(weather.hour)+" TSİ",...wx].join(" · "))+'</p>'+
    (weather.forecast ? '<p class="live-note">Maç saati için hava tahmini.</p>' : '<p class="live-note">Model verisi.</p>') : '<p class="muted">Stadyum konumu veya maç saati için hava verisi doğrulanamadı.</p>';
  resultPanel.innerHTML = '<div class="live-results"><div class="panel padded fixture-heading"><div><p class="muted">'+context+'</p><h2>'+
    escapeHtml(game.home)+" – "+escapeHtml(game.away)+'</h2><p class="research-note">Kaynak kontrolü '+escapeHtml(showDate(data.checkedAt))+' TSİ</p></div>'+score+'</div>'+
    reveal("Son maçlar ve takım formu",teamSection(game.home,game.away,form),true)+
    reveal("Lig tablosu ve maç istatistikleri",quickTable(teams,game),true)+
    reveal("İlk 11 ve eksikler",teamSection(game.home,game.away,squad))+
    reveal("Öne çıkan oyuncular",teamSection(game.home,game.away,leaders))+
    reveal("İkili karşılaşmalar",list(h2h,"İkili geçmişin skorları kaynakta bulunamadı."))+
    reveal("Maç haberleri ve hakem",list(safeArray(data.news),"Maçla ilgili haber kaydı bulunamadı.")+
      '<p class="live-note">Hakem</p>'+list(safeArray(data.officials),"Hakem bilgisi bulunamadı."))+
    reveal("Maç saati hava durumu",weatherText)+
    reveal("Yayımlanan oranlar",list(marketRows(data.odds),"Kaynakta oran kaydı bulunamadı.")+
      '<p class="live-note">Rakamlar sağlayıcının yayımladığı biçimde gösterilir. QuantFoot tahmin olasılıkları ayrı bültende yer alır.</p>')+
    '<div class="panel padded"><h3>Kaynaklar</h3><div class="source-links">'+sources+'</div></div></div>';
}

function renderChoices(matches) {
  resultPanel.innerHTML = '<section class="panel"><div class="panel-head"><h2>Karşılaşmayı seç</h2></div><div class="candidate-list">'+
    matches.map((match,index)=>'<button class="btn" type="button" data-fixture-index="'+index+'"><span>'+escapeHtml(match.home)+" – "+escapeHtml(match.away)+
      '</span><span class="source">'+escapeHtml(showDate(match.kickoff))+' TSİ</span></button>').join("")+'</div></section>';
  resultPanel.querySelectorAll("button[data-fixture-index]").forEach(button=>button.onclick=()=>research({id:matches[Number(button.dataset.fixtureIndex)].id}));
}

async function research(payload) {
  if (liveButton.disabled) return;
  liveButton.disabled = true;
  liveStatus.classList.add("info");
  liveStatus.textContent = "Karşılaşma ve kaynaklar araştırılıyor…";
  resultPanel.innerHTML = '<div class="live-loading" aria-hidden="true"></div>';
  try {
    const response = await fetch("/api/match-research",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload),signal:AbortSignal.timeout(40000)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Araştırma kaynağına ulaşılamadı.");
    if (data.details) {
      liveStatus.textContent = "";
      renderReport(data.details);
    } else if (safeArray(data.candidates).length) {
      liveStatus.textContent = data.candidates.length === 1 ? "Maç bulundu. Ayrıntıları yeniden istemek için maçı seç." : "Birden fazla maç bulundu.";
      renderChoices(data.candidates);
    } else {
      liveStatus.textContent = data.coverage < 3 ? "ESPN bülteni kısmi açıldı. Bu adlarla doğrulanmış bir maç bulunamadı."
        : "ESPN bülteninde bu tarihte eşleşme bulunamadı. Takım adlarını veya tarihi kontrol et.";
      resultPanel.replaceChildren();
    }
  } catch (error) {
    resultPanel.replaceChildren();
    liveStatus.classList.remove("info");
    liveStatus.textContent = error.name === "TimeoutError" ? "Kaynak yanıtı zaman aşımına uğradı. Yeniden dene." :
      error instanceof SyntaxError ? "Araştırma sunucusu kullanılabilir bir yanıt göndermedi." : error.message;
  } finally {
    liveButton.disabled = false;
  }
}

get("live-date").value = new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Istanbul",dateStyle:"short"}).format(new Date());
if (location.hostname === "127.0.0.1" && location.port === "8765") switchTab("bulletin");

searchForm.addEventListener("submit",event=>{
  event.preventDefault();
  const payload = {home:get("live-home").value.trim(),away:get("live-away").value.trim(),date:get("live-date").value};
  if (location.hostname === "127.0.0.1" && location.port === "8765") {
    const hash = new URLSearchParams(payload);
    location.assign(researchSite+"#"+hash);
    return;
  }
  research(payload);
});
const prefill = new URLSearchParams(location.hash.slice(1));
for (const field of ["home","away","date"]) {
  if (prefill.has(field)) get("live-"+field).value = prefill.get(field);
}
