const express = require("express");
const path = require("path");

const app = express();
const PORT = Number(process.env.PORT) || 3000;
const HOST = "0.0.0.0";

const docsDir = path.join(__dirname, "docs");
const terminalDir = path.join(__dirname, "terminal");

app.disable("x-powered-by");

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "quantfoot-dashboard" });
});

app.use("/terminal", express.static(terminalDir, { extensions: ["html"] }));
app.use(express.static(docsDir, { extensions: ["html"] }));

app.get("/terminal/*", (_req, res) => {
  res.sendFile(path.join(terminalDir, "index.html"));
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(docsDir, "index.html"));
});

app.listen(PORT, HOST, () => {
  console.log(`QuantFoot paneli çalışıyor: http://${HOST}:${PORT}`);
});
