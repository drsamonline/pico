/* Runs the console's own engine headlessly so its answers can be compared with
   Python's. Reads a JSON array of commands, writes a JSON object keyed by index.
   Usage: node tools/demo_run.js web/index.html commands.json */
const fs = require("fs"), vm = require("vm"), path = require("path");

const [htmlPath, cmdPath] = process.argv.slice(2);
const html = fs.readFileSync(htmlPath, "utf8");
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("no <script> found"); process.exit(2); }
let js = m[1].replace("/*__PICO_TOKEN__*/null", "null");

/* keep only the engine: everything before the boot block */
const lines = js.split("\n");
const cut = lines.findIndex(l => l.startsWith('$("#ver").textContent'));
js = lines.slice(0, cut < 0 ? lines.length : cut).join("\n");
/* return the result instead of only painting it */
js = js.replace("  render(resolved,src,tier,String(out),text);",
  '  if(typeof __PICO_PROBE__!=="undefined"&&__PICO_PROBE__){setStat("ready");return {out:String(out),resolved,src,tier};}\n' +
  "  render(resolved,src,tier,String(out),text);");

const ctx = vm.createContext({__PICO_PROBE__: true, console, setTimeout, clearTimeout,
  setInterval, clearInterval, Date, Math, JSON, String, Number, Array, Object, RegExp, Error});
vm.runInContext(fs.readFileSync(path.join(__dirname, "demo_stub.js"), "utf8"), ctx, {filename: "stub.js"});
vm.runInContext(js, ctx, {filename: "demo.js"});

const cmds = JSON.parse(fs.readFileSync(cmdPath, "utf8"));
const out = {};
(async () => {
  for (let i = 0; i < cmds.length; i++) {
    const c = cmds[i];
    try {
      const r = await ctx.run(c);
      out[i] = {cmd: c, out: r.out, resolved: r.resolved, src: r.src, tier: r.tier};
    } catch (e) { out[i] = {cmd: c, error: String(e.message)}; }
  }
  console.log(JSON.stringify(out));
})();
