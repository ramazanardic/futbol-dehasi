import assert from "node:assert/strict";
import test from "node:test";
import worker, {findMatches, matchResearch} from "../terminal/research-worker.mjs";

const eventId = "101";
const date = "2026-11-23T20:00:00Z";
const team = (id,displayName)=>({id,displayName});
const brentford = team("1","Brentford");
const everton = team("2","Everton");
const competition = (id,home,away,kickoff=date)=>({
  id,date:kickoff,competitors:[{homeAway:"home",team:home},{homeAway:"away",team:away}],
  status:{type:{name:"STATUS_SCHEDULED"}}
});
const fixture = (id,home=brentford,away=everton,kickoff=date)=>({id,date:kickoff,competitions:[competition(id,home,away,kickoff)]});

test("matches both names, recognizes reverse input, and respects the date in Istanbul",async t=>{
  t.mock.method(globalThis,"fetch",async()=>Response.json({events:[
    fixture(eventId),fixture("102",team("3","Brentford Women"),team("4","Everton Women")),
    fixture("103",brentford,everton,"2026-11-23T22:00:00Z")
  ]}));
  const found = await findMatches("Everton","Brentford","2026-11-23");
  assert.equal(found.available,3);
  assert.deepEqual(found.candidates.map(m=>m.id),[eventId]);
  assert.equal(found.candidates[0].home,"Brentford");
});

test("confirmed fixture is supplemented only with records available for that match",async t=>{
  t.mock.method(globalThis,"fetch",async url=>{
    assert.match(url,/\/all\/summary\?event=101$/);
    return Response.json({
      header:{competitions:[competition(eventId,brentford,everton)],league:{name:"Test league"}},
      gameInfo:{venue:{fullName:"Test stadium"}},
      lastFiveGames:[{team:brentford,events:[
        {gameDate:"2026-11-22T17:00:00Z",opponent:{displayName:"A"},score:"1-1"},
        {gameDate:"2026-11-24T17:00:00Z",opponent:{displayName:"B"},score:"2-1"}
      ]}]
    });
  });
  const report = await matchResearch(eventId);
  assert.equal(report.game.venue,"Test stadium");
  assert.equal(report.teams[0].recent.length,1);
  assert.equal(report.teams[1].table,null);
  assert.deepEqual(report.teams[1].lineup,[]);
  assert.equal(report.weather,null);
});

test("requires an explicit, valid same-origin search",async()=>{
  const path = "https://terminal.example/api/match-research";
  const call = (origin,body) => worker.fetch(new Request(path,{method:"POST",headers:{origin,"content-type":"application/json"},body:JSON.stringify(body)}));
  assert.equal((await call("https://elsewhere.example",{})).status,403);
  assert.equal((await call("https://terminal.example",{id:"https://elsewhere.example"})).status,400);
  assert.equal((await call("https://terminal.example",{home:"Aaa",away:"Bbb",date:"2026-02-29"})).status,400);
});
