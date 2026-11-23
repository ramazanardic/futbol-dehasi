/* Build a Sites-compatible Worker from repository sources. Run in the Site checkout. */
import assert from "node:assert/strict";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import {join, resolve} from "node:path";

const root = resolve(process.argv[2] || ".");
const source = join(root,"terminal");
const dist = join(root,"dist");
const manifest = JSON.parse(await readFile(join(root,".openai","hosting.json"),"utf8"));
assert.equal(typeof manifest.project_id,"string");
assert.equal(manifest.static,undefined,"Use Worker hosting for live match research.");

const filenames = {
  "/index.html":"text/html",
  "/style.css":"text/css",
  "/app.js":"text/javascript",
  "/match-research.js":"text/javascript",
  "/arsiv-maclar.csv":"text/csv",
  "/arsiv-kuponlar.csv":"text/csv",
  "/arsiv-arena.txt":"text/plain"
};
const assets = {};
for (const [path,mime] of Object.entries(filenames)) {
  const filename = path.slice(1);
  try {
    const body = await readFile(join(source,filename),"utf8");
    assets[path] = {type:mime+"; charset=utf-8",body};
  } catch (error) {
    if (error.code !== "ENOENT" || !filename.startsWith("arsiv-")) throw error;
  }
}
const worker = await readFile(join(source,"research-worker.mjs"),"utf8");
const marker = "/* SITE_ASSETS */ {}";
assert(worker.includes(marker));
const code = worker.replace(marker,()=>JSON.stringify(assets));
const moduleUrl = "data:text/javascript;base64,"+Buffer.from(code).toString("base64");
const built = await import(moduleUrl);
assert.equal(typeof built.default?.fetch,"function");
assert.equal((await built.default.fetch(new Request("https://terminal.example/"))).status,200);
await mkdir(join(dist,"server"),{recursive:true});
await mkdir(join(dist,".openai"),{recursive:true});
await Promise.all([
  writeFile(join(dist,"server","index.js"),code),
  writeFile(join(dist,".openai","hosting.json"),JSON.stringify(manifest,null,2)+"\n")
]);
