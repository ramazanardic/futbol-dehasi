"use strict";

const get = id => document.getElementById(id);
const format = new Intl.NumberFormat("tr-TR", {maximumFractionDigits: 2});
const whole = new Intl.NumberFormat("tr-TR");
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);
const num = value => {
  if (!["string", "number"].includes(typeof value) || String(value).trim() === "") return null;
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
};
const probability = value => {
  const p = num(value);
  return p !== null && p >= 0 && p <= 1 ? p : null;
};
const pct = value => value == null ? "—" : "%" + format.format(value * 100);
const display = value => value == null ? "—" : format.format(value);
const safeArray = value => Array.isArray(value) ? value : [];
const timeFormat = new Intl.DateTimeFormat("tr-TR", {timeZone:"Europe/Istanbul", hour:"2-digit", minute:"2-digit"});
const aiNames = {chatgbttahmin:"ChatGPT", claudetahmin:"Claude", geminitahmin:"Gemini", antigravitytahmin:"Antigravity", grokbottahmin:"Grok Bot"};
const state = {matches:[], page:0, arena:[]};
const pageSize = 20;
const familyPrefixes = [
  ["İY/MS", "İY/MS"], ["MS ", "Maç sonucu"], ["ÇŞ ", "Çifte şans"], ["KG", "Karşılıklı gol"],
  ["İY KG", "İY karşılıklı gol"], ["2Y KG", "2Y karşılıklı gol"], ["İY ", "İlk yarı"], ["2Y ", "İkinci yarı"],
  ["Ev ", "Ev sahibi golleri"], ["Dep ", "Deplasman golleri"], ["Hnd", "Handikap"], ["Fark ", "Handikap"],
  ["İlk Gol", "İlk gol"], ["Son Gol", "İlk gol"], ["Tek", "Tek/Çift"], ["Çift", "Tek/Çift"]
];

function csvRows(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < source.length; index++) {
    const char = source[index];
    if (quoted) {
      if (char !== '"') cell += char;
      else if (source[index + 1] === '"') { cell += '"'; index++; }
      else quoted = false;
    } else if (char === '"' && cell === "") quoted = true;
    else if (char === ",") { row.push(cell); cell = ""; }
    else if (char === "\r" || char === "\n") {
      row.push(cell); rows.push(row); row = []; cell = "";
      if (char === "\r" && source[index + 1] === "\n") index++;
    } else cell += char;
  }
  if (quoted) throw new Error("CSV’de kapanmamış bir tırnak var.");
  if (row.length || cell) rows.push([...row, cell]);
  return rows.filter(line => line.some(value => value.trim() !== ""));
}

function parseCsv(text, required, allowEmpty = false) {
  const [headers, ...rows] = csvRows(text);
  if (!headers || !required.every(key => headers.includes(key))) {
    throw new Error("Bu dosyanın sütunları beklenen QuantFoot biçimiyle uyuşmuyor.");
  }
  if (!allowEmpty && rows.length === 0) throw new Error("Dosyada kayıt yok.");
  if (rows.some(row => row.length !== headers.length)) throw new Error("CSV’de sütun sayısı uyuşmayan satır var.");
  return rows.map(row => Object.fromEntries(headers.map((key, index) => [key, row[index]])));
}

function marketFamily(name) {
  const n = String(name ?? "").replace(/^DEĞİL\(/, "").trim();
  if (n.startsWith("İY/MS")) return "İY/MS";
  if (n.includes("&")) return "Kombine (A & B)";
  if (["En Çok Gol","Her İki Yarıyı Kazanır","En Az Bir Yarıyı Kazanır","İki Yarıda Gol"].some(part => n.includes(part))) return "Yarı özel";
  if (n === "İki Yarıda KG Var") return "Yarı karşılıklı gol";
  if (/^(?:İY |2Y )?Skor /.test(n)) return "Doğru skor";
  if (n.includes("Kart")) return "Kart";
  if (n.includes("Korner")) return n.startsWith("İY ") ? "İY korner" : "Korner";
  const known = familyPrefixes.find(([prefix]) => n.startsWith(prefix));
  if (known) return known[1];
  if (/^\d/.test(n) && /Alt|Üst/.test(n)) return "Alt/Üst";
  return n.includes("Gol") ? "Gol aralığı" : "Diğer";
}

function topFamilies(options) {
  const winners = new Map();
  for (const selection of options) {
    if (selection.p === null) continue;
    const current = winners.get(selection.family);
    if (!current || selection.p > current.p) winners.set(selection.family, selection);
  }
  return [...winners.values()].sort((a,b) => b.p - a.p).slice(0,5);
}

function legacyTop(text) {
  return String(text || "").split(" · ").flatMap(part => {
    const result = part.match(/^(.*?)\s*%([\d,.]+)$/);
    const p = result ? probability(num(result[2]) / 100) : null;
    if (!result || p === null || num(result[2]) === null) return [];
    return [{name:result[1], family:marketFamily(result[1]), p}];
  });
}

function kickoffFromCsv(date, hour) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(hour)) return null;
  const stamp = Date.parse(date + "T" + hour + ":00+03:00");
  return Number.isFinite(stamp) ? stamp + (hour < "07:00" ? 86400000 : 0) : null;
}

function parseBulletin(text) {
  if (/^\s*[\[{]/.test(text)) {
    const data = JSON.parse(text);
    if (!Array.isArray(data?.matches) || !data.matches.length) throw new Error("JSON’da maç listesi bulunamadı.");
    if (data.matches.some(m => !m || typeof m !== "object" || !m.home || !m.away || m.code == null)) {
      throw new Error("Bülten en az bir eksik maç kaydı içeriyor.");
    }
    return data.matches.map(m => {
      const selections = safeArray(m.selections).filter(s => s && s.name);
      const pricedByKey = new Map(selections.filter(s => s.key).map(s => [s.key, s]));
      const offered = Array.isArray(m.offered_selections) ? m.offered_selections : selections;
      const selectionsShown = offered.filter(o => o && (o.name || o.selection)).map(o => {
        const s = pricedByKey.get(o.key) || o;
        const name = String(s.name || s.selection);
        return {name, family:marketFamily(name), p:probability(s.fair_prob), odds:num(o.odds ?? s.odds)};
      });
      for (const name of safeArray(m.untranslated_selections)) {
        if (typeof name === "string") selectionsShown.push({name, family:"Eşlenemeyen Nesine pazarları", p:null, odds:null});
      }
      const top = Array.isArray(m.en_yuksek_5)
        ? topFamilies(m.en_yuksek_5.filter(s => s && s.name).map(s => ({name:s.name, family:s.family || marketFamily(s.name), p:probability(s.p)})))
        : [];
      const timestamp = Date.parse(m.kickoff_iso || "");
      return {code:String(m.code), name:m.home + " - " + m.away, league:m.league || "Lig belirtilmemiş",
        timestamp:Number.isFinite(timestamp) ? timestamp : null, clock:typeof m.kickoff === "string" ? m.kickoff.slice(-5) : "",
        xg:[num(m.mu_home),num(m.mu_away)], outcome:safeArray(m.fair_1x2).map(probability), source:m.reference,
        top:top.length ? top : topFamilies(selectionsShown), adjusted:top.length > 0, other:selectionsShown, complete:true};
    });
  }
  return parseCsv(text, ["tarih","saat","mac","nesine_kodu"]).map(m => ({
    code:m.nesine_kodu, name:m.mac, league:m.lig || "Lig belirtilmemiş", timestamp:kickoffFromCsv(m.tarih,m.saat),
    clock:m.saat, xg:[num(m.beklenen_gol_ev),num(m.beklenen_gol_dep)], outcome:[m.olasilik_1,m.olasilik_X,m.olasilik_2].map(probability),
    source:m.fiyat_kaynagi, primary:m.secim_adi || m.ana_secim, primaryP:probability(m.olasilik),
    top:legacyTop(m.en_yuksek_5_olasilik), adjusted:true, other:[], complete:false
  }));
}

function notice(id, message, error = false) {
  const target = get(id + "-notice");
  target.textContent = message;
  target.classList.toggle("error", error);
}

function useMatchSource(text, source) {
  const matches = parseBulletin(text);
  state.matches = matches;
  state.page = 0;
  get("bulletin-source").textContent = source;
  get("search").value = "";
  get("status").value = "";
  const leagues = [...new Set(matches.map(m => m.league))].sort((a,b) => a.localeCompare(b,"tr"));
  get("league").replaceChildren(new Option("Tüm ligler", ""), ...leagues.map(l => new Option(l, l)));
  notice("bulletin", matches.some(m => m.complete)
    ? "Bülten açıldı. Başlama saati TSİ ile gösterilir. Ayrıntı için maç adına dokun."
    : "Tahmin CSV’si açıldı. Tüm bahis ailelerinin ayrıntıları için nesine_global.json yükle.");
  renderBulletin();
}

function matchStatus(m, now) {
  return m.timestamp === null ? "unknown" : m.timestamp > now ? "upcoming" : "started";
}

function renderBulletin() {
  if (!state.matches.length) {
    get("match-list").innerHTML = '<div class="empty">Yüklediğin maçlar burada görünecek.</div>';
    return;
  }
  const now = Date.now();
  const metrics = [
    ["Bültendeki maç",state.matches.length],
    ["Başlamamış",state.matches.filter(m => matchStatus(m,now) === "upcoming").length],
    ["İlk beşi hesaplanmış",state.matches.filter(m => m.top.length).length]
  ];
  get("metrics").hidden = false;
  get("metrics").innerHTML = metrics.map(([label,value]) => '<div class="metric"><strong>' + whole.format(value) + '</strong><span>' + label + '</span></div>').join("");
  const query = get("search").value.trim().toLocaleLowerCase("tr");
  const league = get("league").value, status = get("status").value;
  const filtered = state.matches.map((m,index) => ({...m,index})).filter(m =>
    (!league || m.league === league) && (!status || matchStatus(m,now) === status)
      && (m.name + " " + m.league + " " + m.code).toLocaleLowerCase("tr").includes(query));
  const pages = Math.ceil(filtered.length / pageSize);
  state.page = Math.min(state.page,Math.max(0,pages - 1));
  get("paging").hidden = pages < 2;
  get("prev").disabled = state.page === 0;
  get("next").disabled = state.page + 1 >= pages;
  get("page-count").textContent = (state.page + 1) + " / " + pages;
  if (!filtered.length) {
    get("match-list").innerHTML = '<div class="empty">Bu filtrelere uyan maç bulunamadı.</div>';
    return;
  }
  const rows = filtered.slice(state.page * pageSize, (state.page + 1) * pageSize).map(m => {
    const top = m.top[0];
    const clock = m.timestamp ? timeFormat.format(m.timestamp) : m.clock || "—";
    return '<tr><td class="num">' + escapeHtml(clock) + '<p>' + ({upcoming:"Başlamamış",started:"Başlamış",unknown:"Belirsiz"})[matchStatus(m,now)] + '</p></td>'
      + '<td><button class="match-btn" data-index="' + m.index + '">' + escapeHtml(m.name) + '</button><p>' + escapeHtml(m.league) + '</p></td>'
      + '<td>' + escapeHtml(top?.name || m.primary || "—") + '<p class="listed">' + pct(top?.p ?? m.primaryP) + '</p></td>'
      + '<td class="num">' + m.xg.map(display).join(" / ") + '</td></tr>';
  }).join("");
  get("match-list").innerHTML = '<div class="scroll"><table class="table-bulletin"><thead><tr><th>Saat</th><th>Maç</th><th>Öne çıkan seçim</th><th>Ev / Dep. xG</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
}

function probList(rows) {
  if (!rows.length) return '<p class="muted">Bu dosyada hesaplanmış olasılık bulunmuyor.</p>';
  return '<ol class="prob-list">' + rows.map(row => '<li><div>' + escapeHtml(row.name) + '<br><small>' + escapeHtml(row.family) +
    '</small></div><strong class="num listed">' + pct(row.p) + '</strong><div class="track" aria-hidden="true"><span style="width:' + row.p * 100 + '%"></span></div></li>').join("") + '</ol>';
}

function familyDetails(options, includeOdds = true) {
  const groups = new Map();
  for (const o of options) {
    if (!groups.has(o.family)) groups.set(o.family,[]);
    groups.get(o.family).push(o);
  }
  return [...groups.entries()].map(([family, selections]) =>
    '<details><summary>' + escapeHtml(family) + ' · ' + selections.length + ' seçim</summary><div class="scroll"><table><thead><tr><th>Seçim</th><th>Olasılık</th>' + (includeOdds ? '<th>Nesine oranı</th>' : '') + '</tr></thead><tbody>' +
    selections.sort((a,b) => (b.p ?? -1) - (a.p ?? -1)).map(s => '<tr><td>' + escapeHtml(s.name) + '</td><td class="num">' + pct(s.p) + '</td>' + (includeOdds ? '<td class="num">' + display(s.odds) + '</td>' : '') + '</tr>').join("") +
    '</tbody></table></div></details>').join("");
}

function openMatch(match) {
  get("dialog-league").textContent = match.league;
  const labels = ["MS 1", "MS X", "MS 2"];
  const outcomes = match.outcome.slice(0,3).map((p,i) => '<span class="tag">' + labels[i] + ' ' + pct(p) + '</span>').join("");
  const topSource = match.adjusted ? "Raporda kayıtlı kalibre olasılıklar." : "Dosyadaki adil piyasa olasılıklarından sıralandı.";
  get("match-detail").innerHTML = '<h2>' + escapeHtml(match.name) + '</h2><p class="muted">' + escapeHtml(match.source || "Kaynak belirtilmemiş") +
    ' · Ev / Dep. xG ' + match.xg.map(display).join(" / ") + '</p><div class="tags">' + outcomes + '</div>' +
    '<h3 class="section-space">En yüksek 5 bahis ailesi</h3>' + (match.top.length ? '<p class="subtle">' + topSource + '</p>' : "") + probList(match.top) +
    '<h3 class="section-space">Tüm bahis aileleri</h3>' + (match.other.length ? '<p class="subtle">Ayrıntıda dosyadaki adil piyasa olasılıkları ve kayıtlı oranlar gösterilir.</p>' + familyDetails(match.other) : '<p class="muted">Bu dosyada aile ayrıntıları bulunmuyor.</p>') +
    (match.xg.every(x => x !== null) ? '<button class="btn section-space" id="simulate-match">Bu xG ile simüle et</button>' : "");
  if (get("simulate-match")) get("simulate-match").onclick = () => {
    const [home, ...away] = match.name.split(" - ");
    get("match-dialog").close();
    switchTab("simulation");
    get("home").value = home;
    get("away").value = away.join(" - ") || "Deplasman";
    get("home-xg").value = String(match.xg[0]);
    get("away-xg").value = String(match.xg[1]);
    get("sim-form").requestSubmit();
  };
  get("match-dialog").showModal();
}

function poisson(mean) {
  const values = [Math.exp(-mean)];
  for (let i = 1; i <= 30; i++) values.push(values[i-1] * mean / i);
  return values;
}

function model(homeXg, awayXg) {
  const scores = [];
  const home = poisson(homeXg), away = poisson(awayXg);
  for (const [h,p] of home.entries()) {
    for (const [a,q] of away.entries()) scores.push({h,a,p:p*q});
  }
  const mass = scores.reduce((sum,s) => sum + s.p,0);
  const chance = rule => Math.min(1, scores.reduce((sum,s) => rule(s.h,s.a) ? sum + s.p : sum,0)/mass);
  const selections = [
    ["MS 1","Maç sonucu",chance((h,a) => h>a)], ["MS X","Maç sonucu",chance((h,a) => h===a)], ["MS 2","Maç sonucu",chance((h,a) => h<a)],
    ["KG Var","Karşılıklı gol",chance((h,a) => h>0&&a>0)], ["KG Yok","Karşılıklı gol",chance((h,a) => h===0||a===0)]
  ];
  for (const line of [1.5,2.5,3.5]) {
    const label = format.format(line);
    selections.push([label+" Alt","Alt/Üst",chance((h,a) => h+a<line)], [label+" Üst","Alt/Üst",chance((h,a) => h+a>line)]);
  }
  for (const line of [0.5,1.5,2.5]) {
    const label = format.format(line);
    for (const [team,fn] of [["Ev sahibi", (h,a) => h],["Deplasman",(h,a) => a]]) {
      const family = team + " golleri";
      selections.push([team+" "+label+" Alt",family,chance((h,a)=>fn(h,a)<line)], [team+" "+label+" Üst",family,chance((h,a)=>fn(h,a)>line)]);
    }
  }
  return {selections:selections.map(([name,family,p])=>({name,family,p,odds:null})), scores:scores.sort((a,b)=>b.p-a.p).slice(0,4)};
}

function renderSimulation(event) {
  event.preventDefault();
  const home = get("home").value.trim(), away = get("away").value.trim();
  const a = num(get("home-xg").value), b = num(get("away-xg").value);
  if (!home || !away || [a,b].some(v => v === null || v < 0 || v > 10)) {
    get("sim-message").textContent = "Takım adlarını gir ve her takım için 0 ile 10 arasında bir xG kullan.";
    return;
  }
  get("sim-message").textContent = "";
  const {selections,scores} = model(a,b);
  const scoreTags = scores.filter(s=>s.p>0).map(s => '<span class="tag">' + s.h + "–" + s.a + " · " + pct(s.p) + '</span>').join("");
  get("sim-result").innerHTML = '<h2>' + escapeHtml(home) + ' – ' + escapeHtml(away) + '</h2><p class="muted">Manuel xG · ' +
    display(a) + ' / ' + display(b) + '</p><div class="tags">' + scoreTags + '</div><h3 class="section-space">En yüksek 5 bahis ailesi</h3>' +
    probList(topFamilies(selections)) + '<h3 class="section-space">Hesaplanan tüm seçimler</h3>' + familyDetails(selections, false);
}

function renderCoupons(text, source) {
  const legs = parseCsv(text, ["kupon","kupon_no","mac","secim","nesine_oran"], true);
  const groups = new Map();
  for (const leg of legs) {
    const key = [leg.tarih,leg.kupon,leg.kupon_no].join("|");
    if (!groups.has(key)) groups.set(key,[]);
    groups.get(key).push(leg);
  }
  notice("coupons", source + " · " + groups.size + " kupon · " + legs.length + " bacak");
  get("coupon-list").innerHTML = [...groups.values()].map(lines => {
    const first = lines[0];
    const rows = lines.map(l => '<tr><td>' + escapeHtml(l.mac) + '<p>' + escapeHtml(l.saat) + '</p></td><td>' + escapeHtml(l.secim_adi || l.secim) +
      '</td><td class="num">' + display(num(l.nesine_oran)) + '</td><td class="num">' + pct(probability(l.olasilik)) + '</td></tr>').join("");
    return '<article class="panel"><div class="panel-head"><h2>' + escapeHtml(first.kupon) + '</h2><span class="source">Kupon ' + escapeHtml(first.kupon_no) + '</span></div>' +
      '<div class="padded"><p class="muted">' + escapeHtml(first.tarih) + ' · ' + lines.length + ' bacak</p><div class="tags"><span class="tag">Toplam oran ' +
      display(num(first.kupon_toplam_oran)) + '</span><span class="tag">Tutma olasılığı ' + pct(probability(first.kupon_tutma_olasiligi)) + '</span></div></div>' +
      '<div class="scroll"><table><thead><tr><th>Maç</th><th>Seçim</th><th>Oran</th><th>Olasılık</th></tr></thead><tbody>' + rows + '</tbody></table></div></article>';
  }).join("");
}

function useArena(text, source) {
  const parsed = JSON.parse(text);
  const entries = Array.isArray(parsed) ? parsed : [parsed];
  if (!entries.length || entries.some(d => !d || typeof d.date !== "string" || !d.ais || typeof d.ais !== "object" || Array.isArray(d.ais))) {
    throw new Error("Geçerli bir QuantFoot değerlendirme kaydı bulunamadı.");
  }
  state.arena = entries.sort((a,b) => b.date.localeCompare(a.date));
  get("arena-date").replaceChildren(...state.arena.map((d,i) => new Option(d.date, String(i))));
  get("arena-date").disabled = false;
  notice("arena", source + " · " + state.arena.length + " gün");
  renderArena();
}

function renderArena() {
  const data = state.arena[Number(get("arena-date").value)];
  if (!data) return;
  const rows = Object.entries(aiNames).map(([key, label])=>{
    const stats = data.ais[key] || {};
    const coverage = data.coverage?.[key];
    const total = num(stats.main_picks);
    const hits = num(coverage?.correct ?? stats.hits);
    const wrong = num(coverage?.wrong) ?? (total !== null && hits !== null ? total-hits : null);
    const unresolved = num(coverage?.not_final_or_missing);
    return {label,hits,wrong,unresolved,rate:hits !== null && wrong !== null && hits+wrong > 0 ? hits/(hits+wrong) : null,missing:coverage?.has_prediction_csv === false};
  }).sort((a,b) => (b.rate ?? -1) - (a.rate ?? -1));
  const caption = data.status === "interim" ? "Ara karne · " + String(data.built || "").replace("T"," ").slice(0,16) + " TSİ" : "Günlük değerlendirme";
  get("arena-results").className = "";
  get("arena-results").innerHTML = '<p class="padded muted">' + escapeHtml(caption) + '</p><div class="scroll"><table><thead><tr><th>Yapay zekâ</th><th>Doğru</th><th>Yanlış</th><th>Bekleyen / eksik</th><th>İsabet</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + escapeHtml(r.label) + (r.missing ? '<p>Standart tahmin CSV’si yok</p>' : '') + '</td><td>' +
      display(r.hits) + '</td><td>' + display(r.wrong) + '</td><td>' + display(r.unresolved) + '</td><td class="num listed">' + pct(r.rate) + '</td></tr>').join("") +
    '</tbody></table></div><p class="padded subtle">İsabet yüzdesi, sonucu puanlanan ana tahminler üzerinden hesaplanır.</p>';
}

function switchTab(id) {
  for (const view of document.querySelectorAll(".view")) view.hidden = view.id !== id;
  for (const button of document.querySelectorAll("nav button")) {
    if (button.dataset.tab === id) button.setAttribute("aria-current","page");
    else button.removeAttribute("aria-current");
  }
}

function importFile(id, apply, target) {
  get(id).addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 30 * 1024 * 1024) throw new Error("30 MB sınırını aşan dosyaları günlere bölerek yükle.");
      apply(await file.text(),file.name);
    } catch (error) {
      notice(target,error.message,true);
    } finally {
      event.target.value = "";
    }
  });
}

function archive(button, url, handler, label, target) {
  get(button).addEventListener("click", async event => {
    const control = event.currentTarget;
    control.disabled = true;
    try {
      const result = await fetch(url);
      if (!result.ok) throw new Error("Arşiv dosyası açılmadı.");
      handler(await result.text(),label);
    } catch (error) {
      notice(target,error.message,true);
    } finally {
      control.disabled = false;
    }
  });
}

document.querySelectorAll("nav button").forEach(button => button.onclick = () => switchTab(button.dataset.tab));
for (const name of ["search","league","status"]) {
  get(name).addEventListener(name === "search" ? "input" : "change",()=>{state.page=0;renderBulletin()});
}
get("next").onclick = ()=>{state.page++;renderBulletin()};
get("prev").onclick = ()=>{state.page--;renderBulletin()};
get("close-dialog").onclick = ()=>get("match-dialog").close();
get("match-list").addEventListener("click", event => {
  const button = event.target.closest("button[data-index]");
  if (button) openMatch(state.matches[Number(button.dataset.index)]);
});
get("sim-form").addEventListener("submit",renderSimulation);
get("arena-date").addEventListener("change",renderArena);
get("local-date").textContent = new Intl.DateTimeFormat("tr-TR",{dateStyle:"full",timeZone:"Europe/Istanbul"}).format(new Date()) + " · TSİ";
importFile("bulletin-file",useMatchSource,"bulletin");
importFile("coupons-file",renderCoupons,"coupons");
importFile("arena-file",useArena,"arena");
archive("load-archive","arsiv-maclar.csv",useMatchSource,"21 Kasım 2026 · ChatGPT arşivi","bulletin");
archive("load-coupons","arsiv-kuponlar.csv",renderCoupons,"21 Kasım 2026 · ChatGPT arşivi","coupons");
archive("load-arena","arsiv-arena.txt",useArena,"Ortak GitHub değerlendirme arşivi","arena");
renderBulletin();

const repo = "ramazanardic/futbol-dehasi";
const rawRoot = "https://raw.githubusercontent.com/" + repo + "/main/";
const localRuntime = location.hostname === "127.0.0.1";
let tracking = false;

function currentDay() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone:"Europe/Istanbul",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"
  }).formatToParts().reduce((result, {type,value})=>({...result,[type]:value}),{});
  const utc = Date.UTC(+parts.year,+parts.month-1,+parts.day-(+parts.hour<7 ? 1 : 0));
  return new Date(utc).toISOString().slice(0,10);
}

function selectedDay() {
  const day = get("engine-date").value;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error("Önce bahis gününü seç.");
  return day;
}

function engineStatus(text, error = false) {
  get("engine-status").textContent = text;
  get("engine-status").classList.toggle("info", !error);
}

async function readText(url, missing) {
  let response;
  try {
    response = await fetch(url,{cache:"no-store"});
  } catch {
    throw new Error("Veri kaynağına bağlanılamadı.");
  }
  if (!response.ok) throw new Error(response.status === 404 ? missing : "Veri kaynağı şu anda yanıt vermiyor.");
  return response.text();
}

function fromGithub(button, path, handler, target) {
  get(button).addEventListener("click", async event => {
    const control = event.currentTarget;
    control.disabled = true;
    try {
      const day = selectedDay();
      handler(await readText(rawRoot + path(day),"GitHub’da bu güne ait dosya yayımlanmamış."),day + " · GitHub main");
    } catch (error) {
      notice(target,error.message,true);
    } finally {
      control.disabled = false;
    }
  });
}

async function loadLocalBulletin(day) {
  const base = "/api/reports/" + day;
  const text = await readText(base + "/bulten","Bu güne ait bülten kaydı bulunamadı. Önce analiz başlat.");
  useMatchSource(text,day + " · Yerel QuantFoot");
  const familyReport = get("family-report");
  familyReport.href = base + "/aile";
  familyReport.download = day + "_bahis_aileleri.md";
  familyReport.hidden = false;
}

async function statusFromEngine() {
  const payload = await readText("/api/terminal","Yerel QuantFoot motoru bulunamadı.");
  return JSON.parse(payload);
}

function engineBusy(busy) {
  for (const id of ["start-analysis","start-coupon","start-check","load-local"]) get(id).disabled = busy;
}

async function watchRun() {
  if (tracking) return;
  tracking = true;
  engineBusy(true);
  try {
    let snapshot = (await statusFromEngine()).run;
    while (snapshot.state === "running") {
      engineStatus(snapshot.date + " · " + snapshot.stage + " sürüyor.");
      await new Promise(resolve=>setTimeout(resolve,1600));
      snapshot = (await statusFromEngine()).run;
    }
    if (snapshot.state === "error") {
      throw new Error("QuantFoot işlemi tamamlanamadı. Yerel terminaldeki hata kaydını kontrol et.");
    }
    if (snapshot.state === "finished") {
      engineStatus(snapshot.date + " · İşlem tamamlandı.");
      if (snapshot.mode !== "kontrol") await loadLocalBulletin(snapshot.date);
    }
  } catch (error) {
    engineStatus(error.message,true);
  } finally {
    tracking = false;
    engineBusy(false);
  }
}

async function startRun(mode) {
  if (tracking) return;
  engineBusy(true);
  try {
    const response = await fetch("/api/terminal", {
      method:"POST", headers:{"Content-Type":"application/json","X-QuantFoot-Terminal":"1"},
      body:JSON.stringify({date:selectedDay(),mode})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    await watchRun();
  } catch (error) {
    engineStatus(error.message,true);
    engineBusy(false);
  }
}

get("engine-date").value = currentDay();
fromGithub("github-report",day=>"tahminler/chatgbttahmin/"+day+"/mac_tahminleri.csv",useMatchSource,"bulletin");
fromGithub("github-coupons",day=>"tahminler/chatgbttahmin/"+day+"/kuponlar.csv",renderCoupons,"coupons");
fromGithub("github-arena",day=>"degerlendirme/"+day+".json",useArena,"arena");

if (localRuntime) {
  statusFromEngine().then(({day,profile,run})=>{
    get("engine-date").value = day;
    get("engine-description").textContent = profile + " · Bu bilgisayardaki ortak QuantFoot motoru";
    get("local-actions").hidden = false;
    get("local-coupons").hidden = false;
    get("local-link").hidden = true;
    for (const id of ["load-archive","github-report","load-coupons","github-coupons","load-arena"]) get(id).hidden = true;
    if (run.state === "running") watchRun();
  }).catch(()=>{});
}
get("start-analysis").onclick = ()=>startRun("analiz");
get("start-coupon").onclick = ()=>startRun("kupon");
get("start-check").onclick = ()=>startRun("kontrol");
get("load-local").onclick = async ()=>{
  try { await loadLocalBulletin(selectedDay()); }
  catch (error) { engineStatus(error.message,true); }
};
get("local-coupons").onclick = async ()=>{
  try {
    const day = selectedDay();
    renderCoupons(await readText("/api/reports/"+day+"/kupon","Bu güne ait yerel kupon yok."),day+" · Yerel QuantFoot");
  } catch (error) { notice("coupons",error.message,true); }
};
