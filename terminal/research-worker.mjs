const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer";
const WHOLE_DAY = 86400000;
const COUNTRY_CODES = {
  England:"GB", Scotland:"GB", Wales:"GB", "United Kingdom":"GB", Spain:"ES", France:"FR", Italy:"IT",
  Germany:"DE", Portugal:"PT", Netherlands:"NL", Belgium:"BE", Turkey:"TR", Türkiye:"TR", Brazil:"BR",
  Argentina:"AR", "United States":"US", Canada:"CA", Mexico:"MX", Japan:"JP", Australia:"AU"
};
const TEAM_ALIASES = {
  "man utd":"manchester united", "man united":"manchester united",
  "man city":"manchester city", "psg":"paris saint germain",
  "bayern munchen":"bayern munich", "inter milan":"internazionale", "inter":"internazionale",
  "fc barcelona":"barcelona", "barca":"barcelona", "ath madrid":"atletico madrid",
  "wolverhampton":"wolverhampton wanderers", "wolves":"wolverhampton wanderers"
};
const STATS = {
  possessionPct:"Topa sahip olma", totalShots:"Şut", shotsOnTarget:"İsabetli şut",
  wonCorners:"Korner", foulsCommitted:"Faul", yellowCards:"Sarı kart", redCards:"Kırmızı kart",
  offsides:"Ofsayt", saves:"Kurtarış", expectedGoals:"xG"
};
const assets = /* SITE_ASSETS */ {};

const array = value => Array.isArray(value) ? value : [];
const text = (value, fallback = "") => typeof value === "string" ? value : fallback;
function dateInIstanbul(value) {
  return new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Istanbul",year:"numeric",month:"2-digit",day:"2-digit"})
    .format(new Date(value));
}

function normalize(value) {
  const key = value.toLowerCase().replace(/ı/g,"i").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .replace(/[^a-z0-9 ]/g," ").trim().replace(/\s+/g," ");
  return TEAM_ALIASES[key] || key;
}

function matchName(input, team) {
  const key = normalize(input);
  if (key.length < 2) return 0;
  const names = [team?.displayName,team?.shortDisplayName,team?.name,team?.location,team?.abbreviation]
    .filter(Boolean).map(normalize);
  const descriptor = names[0] || "";
  const classTag = /\b(?:women|femenino|femenina|feminine|frauen|u1[789]|u2[013]|reserves|reserve|ii|b)\b/;
  if (classTag.test(descriptor) && !classTag.test(key)) return 0;
  if (names.includes(key)) return 3;
  return key.length >= 4 && names.some(n => (" " + n + " ").includes(" " + key + " ")) ? 1 : 0;
}

function sides(comp) {
  const bySide = new Map(array(comp?.competitors).map(entry => [entry.homeAway,entry]));
  return [bySide.get("home"),bySide.get("away")];
}

function gameRecord(event, comp) {
  const [home,away] = sides(comp);
  if (!home?.team?.displayName || !away?.team?.displayName || !Number.isFinite(Date.parse(event.date))) return null;
  return {
    id:String(event.id), kickoff:event.date, home:home.team.displayName, away:away.team.displayName,
    homeId:String(home.team.id || ""), awayId:String(away.team.id || ""),
    status:comp.status?.type?.name || event.status?.type?.name || "",
    score:[home.score,away.score].map(score => typeof score === "string" || typeof score === "number" ? String(score) : null),
    venue:comp.venue?.fullName || null
  };
}

async function jsonFrom(url) {
  try {
    const response = await fetch(url,{headers:{Accept:"application/json"},signal:AbortSignal.timeout(7500),redirect:"error"});
    if (response.ok) return await response.json();
  } catch {}
  return null;
}

function dateValue(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) return null;
  const parsed = new Date(date+"T00:00:00Z");
  const year = parsed.getUTCFullYear();
  return year >= 2000 && year <= 2100 && parsed.toISOString().slice(0,10) === date ? parsed.getTime() : null;
}

export async function findMatches(home, away, day) {
  const timestamp = dateValue(day);
  const days = [-1,0,1].map(offset=>new Date(timestamp+WHOLE_DAY*offset).toISOString().slice(0,10).replaceAll("-",""));
  const boards = await Promise.all(days.map(on => jsonFrom(ESPN+"/all/scoreboard?dates="+on+"&limit=500")));
  const records = new Map();
  for (const board of boards) {
    for (const event of array(board?.events)) {
      const comp = event.competitions?.[0];
      const [h,a] = sides(comp);
      const direct = [matchName(home,h?.team),matchName(away,a?.team)];
      const reverse = [matchName(home,a?.team),matchName(away,h?.team)];
      const confidence = Math.max(...[direct,reverse].map(pair=>pair.every(Boolean) ? pair[0]+pair[1] : 0));
      if (!confidence) continue;
      const game = gameRecord(event,comp);
      if (game && /^\d+$/.test(game.id) && dateInIstanbul(game.kickoff) === day) {
        records.set(game.id,{...game,competition:event.season?.slug || null, confidence});
      }
    }
  }
  return {
    candidates:[...records.values()].sort((a,b)=>b.confidence-a.confidence || a.kickoff.localeCompare(b.kickoff)).slice(0,12),
    available:boards.filter(b=>Array.isArray(b?.events)).length
  };
}

function gameHistory(events,kickoff) {
  return array(events).filter(g=>Date.parse(g.gameDate) < Date.parse(kickoff))
    .sort((a,b)=>Date.parse(b.gameDate)-Date.parse(a.gameDate)).slice(0,6).map(g=>({
    date:text(g.gameDate), opponent:g.opponent?.displayName || null, score:text(g.score),
    result:text(g.gameResult), location:text(g.atVs)
  })).filter(g=>g.opponent && g.score);
}

function leagueTable(data, ids) {
  const out = {};
  for (const league of array(data?.groups || data?.children)) {
    for (const item of array(league.standings?.entries)) {
      const id = String(item.team?.id || item.id);
      if (!ids.includes(id)) continue;
      const stats = Object.fromEntries(array(item.stats).map(x=>[x.name,x.displayValue ?? x.value]));
      out[id] = {rank:stats.rank,points:stats.points,played:stats.gamesPlayed,won:stats.wins,
                 drawn:stats.ties,lost:stats.losses,goalDiff:stats.pointDifferential};
    }
  }
  return out;
}

function teamDetails(summary,id,table,kickoff) {
  const sameTeam = row=>String(row?.team?.id) === id;
  const last = array(summary.lastFiveGames).find(sameTeam);
  const leaders = array(summary.leaders).find(sameTeam);
  const roster = array(summary.rosters).find(sameTeam);
  const players = array(roster?.roster).filter(p=>p.starter === true).map(p=>p.athlete?.displayName).filter(Boolean);
  const stats = array(summary.boxscore?.teams).find(sameTeam)?.statistics;
  const ranked = array(leaders?.leaders).slice(0,4).flatMap(category =>
    array(category.leaders).slice(0,2).map(p=>({category:category.displayName || category.name,
      player:p.athlete?.displayName, value:p.displayValue}))).filter(p=>p.player);
  const unavailable = array(summary.injuries).filter(sameTeam).flatMap(group =>
    array(group.injuries).map(p=>({name:p.athlete?.displayName,status:p.status || p.type?.description}))).filter(p=>p.name);
  return {recent:gameHistory(last?.events,kickoff),table:table[id] || null,
    lineup:players.length >= 11 ? players : [], unavailable, leaders:ranked,
    stats:array(stats).filter(s=>STATS[s.name] && s.displayValue != null).map(s=>({name:STATS[s.name],value:s.displayValue}))};
}

async function weatherAt(summary,kickoff) {
  const address = summary.gameInfo?.venue?.address || {};
  const code = COUNTRY_CODES[address.country], city = address.city;
  if (!code || !city || Math.abs(Date.parse(kickoff)-Date.now()) > 13*WHOLE_DAY) return null;
  const params = new URLSearchParams({name:city,countryCode:code,count:"10",language:"en",format:"json"});
  const geo = await jsonFrom("https://geocoding-api.open-meteo.com/v1/search?"+params);
  const places = array(geo?.results).filter(p=>p.country_code === code && normalize(p.name) === normalize(city));
  if (!places.length || places.some(p=>Math.hypot(p.latitude-places[0].latitude,p.longitude-places[0].longitude)>0.04)) {
    return null;
  }
  const {latitude,longitude} = places[0];
  const at = new Date(kickoff);
  at.setUTCMinutes(0,0,0);
  const hour = at.toISOString().slice(0,16), day = hour.slice(0,10);
  const when = new URLSearchParams({latitude,longitude,start_date:day,end_date:day,timezone:"GMT",
    hourly:"temperature_2m,precipitation,wind_speed_10m"});
  const url = "https://api.open-meteo.com/v1/forecast?"+when;
  const data = await jsonFrom(url);
  const i = array(data?.hourly?.time).indexOf(hour);
  return i < 0 ? null : {city,url,hour:hour+"Z",temp:data.hourly.temperature_2m?.[i] ?? null,
    rain:data.hourly.precipitation?.[i] ?? null,wind:data.hourly.wind_speed_10m?.[i] ?? null,
    forecast:Date.parse(kickoff) >= Date.now()};
}

function odds(offers) {
  return array(offers).slice(0,3).map(offer=>({
    provider:offer.provider?.name || offer.provider?.displayName, line:offer.details,
    total:offer.overUnder, moneyline:["home","draw","away"].map(side=>{
      const value = offer.moneyline?.[side]?.close?.odds ?? offer.moneyline?.[side]?.open?.odds;
      return typeof value === "string" || typeof value === "number" ? value : null;
    })
  })).filter(o=>o.provider);
}

async function premierAvailability(game,league) {
  if (league !== "eng.1" || Date.parse(game.kickoff) < Date.now() || Date.parse(game.kickoff) - Date.now() > 7*WHOLE_DAY) return null;
  const data = await jsonFrom("https://fantasy.premierleague.com/api/bootstrap-static/");
  if (!Array.isArray(data?.teams) || !Array.isArray(data?.elements)) return null;
  const status = {i:"Sakat",s:"Cezalı",d:"Şüpheli",u:"Kadro dışı",n:"Oynayamaz"};
  return [game.home,game.away].map(name=>{
    const team = data.teams.find(t=>normalize(t.name || "") === normalize(name));
    return team ? data.elements.filter(p=>p.team === team.id && status[p.status]).map(p=>({
      name:[p.first_name,p.second_name].filter(Boolean).join(" "),status:status[p.status]
    })).filter(p=>p.name) : null;
  });
}

export async function matchResearch(id) {
  const summary = await jsonFrom(ESPN+"/all/summary?event="+id);
  if (!summary) return null;
  const comp = summary.header?.competitions?.[0];
  const event = {...summary.header,id,date:comp?.date};
  const game = gameRecord(event,comp);
  if (!game || String(comp.id) !== id) return null;
  const league = summary.header?.league || {};
  const liveTable = leagueTable(summary.standings,[game.homeId,game.awayId]);
  const [weather,alternate,availability] = await Promise.all([
    weatherAt(summary,game.kickoff),
    Object.keys(liveTable).length < 2 && /^[a-z0-9.]+$/.test(league.slug || "") && Date.parse(game.kickoff) >= Date.now()
      ? jsonFrom("https://site.api.espn.com/apis/v2/sports/soccer/"+league.slug+"/standings")
      : null,
    premierAvailability(game,league.slug)
  ]);
  const table = {...leagueTable(alternate,[game.homeId,game.awayId]),...liveTable};
  const sources = [{name:"ESPN maç merkezi",url:"https://www.espn.com/soccer/match/_/gameId/"+id}];
  if (alternate && Object.keys(table).length && /^[a-z0-9.]+$/.test(league.slug)) {
    sources.push({name:"ESPN lig tablosu",url:"https://www.espn.com/soccer/table/_/league/"+league.slug});
  }
  if (availability?.some(Array.isArray)) sources.push({name:"Premier League oyuncu durumu",url:"https://fantasy.premierleague.com/"});
  if (weather) sources.push({name:"Open-Meteo",url:weather.url});
  return {game:{...game,venue:game.venue || summary.gameInfo?.venue?.fullName || null,league:league.name || null},checkedAt:new Date().toISOString(),
    teams:[game.homeId,game.awayId].map((team,index)=>{
      const detail = teamDetails(summary,team,table,game.kickoff);
      return {...detail,availability:availability?.[index] || [],officialAvailability:Array.isArray(availability?.[index])};
    }),
    h2h:array(summary.seasonseries).flatMap(series=>array(series.events))
      .filter(g=>Date.parse(g.date || g.gameDate) < Date.parse(game.kickoff)).slice(0,6).flatMap(g=>{
        const [home,away] = sides(g);
        if (!home?.team?.displayName || !away?.team?.displayName) return [];
        return [{date:g.date || g.gameDate,name:home.team.displayName+" – "+away.team.displayName,
          score:home.score != null && away.score != null ? home.score+"–"+away.score : null}];
      }),
    news:array(summary.news?.[0]?.articles || summary.news?.articles).slice(0,5).map(item=>item.headline).filter(Boolean),
    officials:array(summary.gameInfo?.officials).map(item=>item.displayName || item.fullName).filter(Boolean),
    weather, odds:odds(summary.pickcenter), sources};
}

function answer(body,status=200) {
  return Response.json(body,{status,headers:{"cache-control":"no-store","x-content-type-options":"nosniff"}});
}
function validNames(home,away) {
  return [home,away].every(name=>typeof name === "string" && name.length <= 90 && normalize(name).length >= 2)
    && normalize(home) !== normalize(away);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/api/match-research") {
      if (request.method !== "POST") return answer({error:"Araştırmayı formdan başlat."},405);
      if (request.headers.get("origin") !== url.origin) return answer({error:"Araştırma isteğini Terminal’den gönder."},403);
      try {
        if (!request.headers.get("content-type")?.startsWith("application/json") ||
            Number(request.headers.get("content-length") || 0) > 2048) return answer({error:"İstek biçimi geçersiz."},400);
        const raw = await request.text();
        if (raw.length > 2048) return answer({error:"İstek çok uzun."},400);
        const {home,away,date,id} = JSON.parse(raw);
        if (id != null) {
          if (typeof id !== "string" || !/^\d{1,12}$/.test(id)) return answer({error:"Maç kodu geçersiz."},400);
          const details = await matchResearch(id);
          return details ? answer({details}) : answer({error:"ESPN maç ayrıntısı şu anda alınamadı."},502);
        }
        if (!validNames(home,away) || dateValue(date) === null) return answer({error:"İki farklı takım ve geçerli bir tarih gir."},400);
        const {candidates,available} = await findMatches(home,away,date);
        if (!available) return answer({error:"ESPN maç bülteni şu anda alınamadı."},502);
        if (candidates.length === 1) {
          const details = await matchResearch(candidates[0].id);
          if (details) return answer({details,candidates,coverage:available});
        }
        return answer({candidates,coverage:available});
      } catch (error) {
        return error instanceof SyntaxError || error instanceof TypeError
          ? answer({error:"Araştırma isteği okunamadı."},400)
          : answer({error:"Araştırma sırasında kaynaklardan yanıt alınamadı."},502);
      }
    }
    if (!["GET","HEAD"].includes(request.method)) return new Response(null,{status:405});
    const page = assets[url.pathname === "/" ? "/index.html" : url.pathname];
    if (!page) return new Response("Dosya bulunamadı.",{status:404});
    return new Response(request.method === "HEAD" ? null : page.body,{headers:{"content-type":page.type,"cache-control":"no-cache","x-content-type-options":"nosniff"}});
  }
};
