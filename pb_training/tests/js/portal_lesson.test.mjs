/**
 * LEARNING L7 — T2: the phone's replay queue, in node.
 *
 * `static/src/js/portal_lesson.js` is a plain script (no module system), so
 * it is run here in a fresh context with a fake window: a localStorage, a
 * fetch we control, and NO document (the page half stays asleep). Asserts:
 *   1. presses are kept in order, capped at 50 (the oldest dropped first);
 *   2. replay sends OLDEST FIRST and STOPS AT THE FIRST ONE THAT CANNOT GET
 *      THROUGH — it and everything after it stay, in order;
 *   3. a server ANSWER, even a refusal, takes the press off the phone;
 *   4. a second replay after the signal returns sends the rest;
 *   5. a broken storage (private window) never throws;
 *   6. only lesson routes are ever kept or sent.
 *
 * Run: node pb_training/tests/js/portal_lesson.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.join(HERE, "..", "..", "static", "src", "js", "portal_lesson.js"), "utf-8");

let passed = 0;
let failed = 0;
function check(name, ok, detail) {
    if (ok) { passed += 1; } else { failed += 1; console.log("FAIL", name, detail === undefined ? "" : JSON.stringify(detail)); }
}

function world({ brokenStorage = false } = {}) {
    const store = new Map();
    const localStorage = brokenStorage ? {
        getItem() { throw new Error("blocked"); },
        setItem() { throw new Error("blocked"); },
    } : {
        getItem: (k) => (store.has(k) ? store.get(k) : null),
        setItem: (k, v) => store.set(k, String(v)),
    };
    const win = { localStorage, Date, JSON, Math, Promise, setTimeout, console };
    win.window = win;
    vm.createContext(win);
    vm.runInContext(SRC, win);
    return { win, api: win.pbtrLesson, store };
}

function item(slide, kind = "done") {
    return { route: `/my/training/7/${slide}/${kind}`, kind, channel_id: 7, slide_id: slide, next_id: 0, answers: [] };
}

// 1. order and the cap
{
    const { api } = world();
    for (let i = 1; i <= 55; i++) { api.push(item(i)); }
    const q = api.readQueue();
    check("cap 50", q.length === 50, q.length);
    check("oldest dropped first", q[0].slide_id === 6 && q[49].slide_id === 55, [q[0].slide_id, q[49].slide_id]);
    check("each press has an id and a time", q.every((it) => it.id && it.at));
}

// 2 + 3 + 4. replay order, stop at the first failure, then the rest
{
    const { api } = world();
    [1, 2, 3, 4].forEach((n) => api.push(item(n, n === 2 ? "quiz" : "done")));
    const sent = [];
    let down = false;
    const send = (it) => {
        if (it.slide_id === 3 && !down) { down = true; return Promise.reject(new Error("offline")); }
        sent.push(it.slide_id);
        return Promise.resolve(it.slide_id === 2 ? { ok: true, passed: true } : { ok: true });
    };
    const res = await api.replay(send);
    check("sent oldest first, up to the failure", JSON.stringify(sent) === "[1,2]", sent);
    check("stopped", res.stopped === true && res.left === 2, res);
    check("outcomes carry the answers", res.sent.length === 2 && res.sent[1].answer.passed === true, res.sent);
    const left = api.readQueue().map((it) => it.slide_id);
    check("the failed one and after stay, in order", JSON.stringify(left) === "[3,4]", left);
    const again = await api.replay(send);
    check("replay after the signal returns sends the rest", JSON.stringify(sent) === "[1,2,3,4]" && again.left === 0 && !again.stopped, sent);
    check("queue empty", api.readQueue().length === 0);
}

// 3. a refusal is an answer: the press goes
{
    const { api } = world();
    api.push(item(9));
    const res = await api.replay(() => Promise.resolve({ ok: false, problem: "mine" }));
    check("refusal taken off the phone", api.readQueue().length === 0 && res.sent[0].answer.ok === false, res);
}

// a send that throws synchronously stops like a network failure
{
    const { api } = world();
    api.push(item(1));
    const res = await api.replay(() => { throw new Error("boom"); });
    check("a throwing send stops and keeps", res.stopped && api.readQueue().length === 1, res);
}

// 5. broken storage never throws
{
    const { api } = world({ brokenStorage: true });
    let threw = false;
    try {
        api.push(item(1));
        check("broken storage reads empty", api.readQueue().length === 0);
        const res = await api.replay(() => Promise.resolve({ ok: true }));
        check("broken storage replays nothing", res.sent.length === 0 && res.left === 0, res);
    } catch (e) { threw = true; }
    check("broken storage never throws", !threw);
}

// 6. only lesson routes
{
    const { api, store } = world();
    check("route ok", api.routeOk("/my/training/1/2/done") && api.routeOk("/my/training/1/2/quiz"));
    check("route refused", !api.routeOk("/web/session/destroy") && !api.routeOk("/my/training/1/2/done?x=1") && !api.routeOk("https://x/my/training/1/2/done"));
    store.set("pbtr.queue", JSON.stringify([{ route: "/web/session/destroy", id: "a" }, item(5)]));
    const q = api.readQueue();
    check("a foreign route is never read back", q.length === 1 && q[0].slide_id === 5, q);
    const res = await api.sendReal({ route: "/web/session/destroy" }).then(() => "sent", () => "refused");
    check("a foreign route is never sent", res === "refused", res);
}

// the queue holds ids and answers only
{
    const { api } = world();
    api.push({ ...item(3, "quiz"), answers: [{ q: 11, a: 22 }] });
    const keys = Object.keys(api.readQueue()[0]).sort().join(",");
    check("only ids, answers and a time", keys === "answers,at,channel_id,id,kind,next_id,route,slide_id", keys);
}

console.log(`portal_lesson: ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
