// Minimal Chrome DevTools Protocol client for the VIFIX sweep (Node >= 22, no dependencies).
// Usage: const page = await openPage(9577); await page.eval("1+1"); await page.shot("x.png");
import fs from "node:fs";

export async function openPage(port, url = "about:blank") {
    const res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
    const target = await res.json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((ok, ko) => { ws.onopen = ok; ws.onerror = ko; });
    let id = 0;
    const pending = new Map();
    const listeners = [];
    ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.id && pending.has(msg.id)) {
            const { ok, ko } = pending.get(msg.id);
            pending.delete(msg.id);
            msg.error ? ko(new Error(JSON.stringify(msg.error))) : ok(msg.result);
        } else if (msg.method) {
            for (const l of listeners) l(msg);
        }
    };
    const send = (method, params = {}) => new Promise((ok, ko) => {
        const mid = ++id;
        pending.set(mid, { ok, ko });
        ws.send(JSON.stringify({ id: mid, method, params }));
    });
    const consoleErrors = [];
    listeners.push((m) => {
        if (m.method === "Runtime.exceptionThrown") {
            consoleErrors.push(m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text);
        } else if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
            consoleErrors.push((m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" "));
        }
    });
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    const page = {
        send,
        consoleErrors,
        async eval(expression, { awaitPromise = true } = {}) {
            const r = await send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
            if (r.exceptionDetails) {
                throw new Error("eval: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
            }
            return r.result.value;
        },
        async goto(u) {
            await send("Page.navigate", { url: u });
            await page.waitFor("document.readyState === 'complete'", 30000);
        },
        async waitFor(expr, timeout = 15000, every = 250) {
            const t0 = Date.now();
            while (Date.now() - t0 < timeout) {
                try { if (await page.eval(`!!(${expr})`)) return true; } catch (e) { /* page navigating */ }
                await sleep(every);
            }
            return false;
        },
        async shot(path) {
            const r = await send("Page.captureScreenshot", { format: "png" });
            fs.writeFileSync(path, Buffer.from(r.data, "base64"));
        },
        close() { ws.close(); },
    };
    return page;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
