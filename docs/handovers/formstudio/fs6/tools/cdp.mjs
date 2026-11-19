// Headless Chrome driver (no dependencies; Node >= 22 global WebSocket/fetch).
// node cdp.mjs dump <outdir> <plan.json>
//   plan = {base, db, users:[{key, login, env}], records:[{key, model, id, cid}]}
//   password of each user is read from the environment variable named by `env`.
// node cdp.mjs shot <outdir> <plan.json>   (plan.shots = [{name, user, model, id, cid, width, tab?, scroll?}])
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const [, , mode, outdir, planFile] = process.argv;
const plan = JSON.parse(fs.readFileSync(planFile, "utf8"));
const DUMP_JS = fs.readFileSync(new URL("./formdump.js", import.meta.url), "utf8");
const PORT = 9461;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(outdir, { recursive: true });

const prof = path.join(path.dirname(new URL(import.meta.url).pathname), "chromeprof");
const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`,
    "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--hide-scrollbars",
    "--window-size=1440,1000", "about:blank",
], { stdio: "ignore" });
const killAll = () => { try { chrome.kill("SIGKILL"); } catch { /* */ } };
process.on("exit", killAll);
setTimeout(() => { console.error("GLOBAL TIMEOUT"); killAll(); process.exit(3); }, 40 * 60 * 1000);

let wsUrl;
for (let i = 0; i < 60 && !wsUrl; i++) {
    try { wsUrl = (await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json()).webSocketDebuggerUrl; }
    catch { await sleep(500); }
}
if (!wsUrl) { console.error("chrome did not start"); process.exit(2); }
const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
const listeners = [];
ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
    } else if (msg.method) {
        listeners.forEach((l) => l(msg));
    }
});
function send(method, params = {}, sessionId) {
    const id = ++seq;
    ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((res, rej) => {
        pending.set(id, { res, rej });
        setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error("timeout " + method)); } }, 120000);
    });
}

async function openSession(user, width = 1440) {
    const { browserContextId } = await send("Target.createBrowserContext", { disposeOnDetach: true });
    const { targetId } = await send("Target.createTarget", { url: "about:blank", browserContextId });
    const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
    const s = { sessionId, targetId, browserContextId, errors: [] };
    listeners.push((m) => {
        if (m.sessionId !== sessionId) return;
        if (m.method === "Runtime.exceptionThrown") s.errors.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text || "").slice(0, 300));
        if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") s.errors.push("CONSOLE " + m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 300));
        if (m.method === "Log.entryAdded" && m.params.entry.level === "error") s.errors.push("LOG " + (m.params.entry.text + " " + (m.params.entry.url || "")).slice(0, 300));
    });
    await send("Page.enable", {}, sessionId);
    await send("Runtime.enable", {}, sessionId);
    await send("Log.enable", {}, sessionId);
    await send("Network.enable", {}, sessionId);
    await setWidth(s, width);
    await nav(s, `${plan.base}/web/login`);
    const pw = process.env[user.env];
    const r = await evalIn(s, `fetch('/web/session/authenticate', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({jsonrpc:'2.0', method:'call', params:{db:${JSON.stringify(plan.db)}, login:${JSON.stringify(user.login)}, password:${JSON.stringify(pw)}}})})
        .then(r => r.json()).then(j => j.result ? 'ok ' + j.result.uid : 'fail ' + JSON.stringify(j.error && j.error.data && j.error.data.message))`);
    if (!String(r).startsWith("ok")) throw new Error("login failed " + user.login + " " + r);
    return s;
}
async function setWidth(s, width) {
    const mobile = width < 600;
    await send("Emulation.setDeviceMetricsOverride", { width, height: mobile ? 844 : 1000, deviceScaleFactor: 1, mobile }, s.sessionId);
}
async function closeSession(s) {
    await send("Target.closeTarget", { targetId: s.targetId });
    try { await send("Target.disposeBrowserContext", { browserContextId: s.browserContextId }); } catch { /* */ }
}
async function nav(s, url) {
    await send("Page.navigate", { url }, s.sessionId);
    for (let i = 0; i < 100; i++) {
        await sleep(200);
        const st = await evalIn(s, "document.readyState");
        if (st === "complete") return;
    }
}
async function evalIn(s, expression, awaitPromise = true) {
    const r = await send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true }, s.sessionId);
    if (r.exceptionDetails) throw new Error("eval: " + JSON.stringify(r.exceptionDetails).slice(0, 500));
    return r.result.value;
}
async function openRecord(s, rec) {
    await send("Network.setCookie", { name: "cids", value: String(rec.cid), url: plan.base }, s.sessionId);
    s.errors.length = 0;
    await nav(s, `${plan.base}/odoo/${rec.model}/${rec.id}`);
    for (let i = 0; i < 150; i++) {
        await sleep(200);
        const ok = await evalIn(s, `!!document.querySelector('.o_action_manager .o_form_view .o_form_renderer') && !document.querySelector('.o_loading_indicator, .o_blockUI')`);
        if (ok) break;
    }
    await sleep(1500);
}

if (mode === "dump") {
    const summary = [];
    for (const user of plan.users) {
        const s = await openSession(user);
        for (const rec of plan.records) {
            const key = `${user.key}__${rec.key}`;
            try {
                await openRecord(s, rec);
                const d = await evalIn(s, `(${DUMP_JS})()`);
                d.errors = [...s.errors];
                fs.writeFileSync(path.join(outdir, key + ".json"), JSON.stringify(d, null, 1));
                summary.push(`${key} rows=${(d.rows || []).length} vu=${d.vuForm} errors=${d.errors.length} ${d.error || ""}`);
            } catch (e) {
                summary.push(`${key} FAILED ${e.message.slice(0, 200)}`);
                fs.writeFileSync(path.join(outdir, key + ".json"), JSON.stringify({ error: e.message }));
            }
        }
        await closeSession(s);
    }
    fs.writeFileSync(path.join(outdir, "_summary.txt"), summary.join("\n") + "\n");
    console.log(summary.join("\n"));
} else if (mode === "probe") {
    // plan.evals = [{user, model, id, cid, width?, js}]
    for (const ev of plan.evals) {
        const user = plan.users.find((u) => u.key === ev.user);
        const s = await openSession(user, ev.width || 1440);
        await openRecord(s, ev);
        const v = await evalIn(s, ev.js);
        console.log("EVAL", ev.name || "", JSON.stringify(v), "errors", s.errors.length, s.errors.slice(0, 3).join(" | "));
        await closeSession(s);
    }
} else if (mode === "shot") {
    for (const shot of plan.shots) {
        const user = plan.users.find((u) => u.key === shot.user);
        const s = await openSession(user, shot.width || 1440);
        await openRecord(s, shot);
        if (shot.tab) {
            await evalIn(s, `(async()=>{const a=[...document.querySelectorAll('.o_notebook_headers .nav-link')].find(x=>(x.getAttribute('name')||'')===${JSON.stringify(shot.tab)}||x.innerText.trim()===${JSON.stringify(shot.tab)}); if(a){a.click();} await new Promise(r=>setTimeout(r,700)); if(a){a.scrollIntoView({block:'start'});} return !!a;})()`);
        }
        await evalIn(s, `(()=>{document.querySelectorAll('.o_notification_manager').forEach(e=>e.style.display='none'); const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()==='Later'); if(b) b.click(); return 1;})()`);
        if (shot.js) await evalIn(s, shot.js);
        await sleep(600);
        const full = shot.full !== false;
        let clip;
        if (full) {
            const h = await evalIn(s, `Math.min(6000, Math.max(document.documentElement.scrollHeight, ...[...document.querySelectorAll('.o_content, .o_action_manager .o_form_view, .o_form_renderer')].map(e=>e.scrollHeight)))`);
            await send("Emulation.setDeviceMetricsOverride", { width: shot.width || 1440, height: Math.ceil(h) + 80, deviceScaleFactor: 1, mobile: (shot.width || 1440) < 600 }, s.sessionId);
            await sleep(900);
        }
        const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, s.sessionId);
        fs.writeFileSync(path.join(outdir, shot.name + ".png"), Buffer.from(data, "base64"));
        console.log("shot", shot.name, "errors", s.errors.length, s.errors.slice(0, 3).join(" | "));
        await closeSession(s);
    }
}
killAll();
process.exit(0);
