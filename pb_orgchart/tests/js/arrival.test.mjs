/**
 * ORG CHART P4 §5 case 2 — the arrival payload (⌘K focus and shared links),
 * as the pure function the chart uses.
 *
 * Run: node pb_orgchart/tests/js/arrival.test.mjs   (exit 1 on failure)
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, "../../static/src/js/orgchart_arrival.js");
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "oc-arrival-")), "arrival.mjs");
fs.copyFileSync(src, tmp);
const { parseArrival } = await import(pathToFileURL(tmp).href);

let failed = 0;
let n = 0;
function eq(name, got, want) {
    n++;
    const a = JSON.stringify(got);
    const b = JSON.stringify(want);
    if (a !== b) { failed++; console.log("FAIL", name, "\n  got ", a, "\n  want", b); } else { console.log("ok  ", name); }
}
const base = { focus: null, me: false, mode: null, view: null, color: null, asOf: null, plan: null };

eq("nothing asked", parseArrival("", ""), null);
eq("an unrelated query", parseArrival("", "?emp=4&debug=1"), null);
eq("⌘K: who reports to me", parseArrival("me", ""), { ...base, me: true });
eq("⌘K: plan", parseArrival("plan", ""), { ...base, mode: "plan" });
eq("⌘K: suggest", parseArrival("suggest", ""), { ...base, mode: "suggest" });
eq("⌘K: an unknown focus", parseArrival("queue", ""), null);
eq("link: full view", parseArrival("", "?oc=1&oc_focus=123&oc_view=lr&oc_color=loc"),
   { ...base, focus: 123, view: "lr", color: "loc" });
eq("link: a day", parseArrival("", "oc=1&oc_as_of=2026-05-01&oc_view=tree&oc_color=dept"),
   { ...base, view: "tree", color: "dept", asOf: "2026-05-01" });
eq("link: a plan", parseArrival("", "?oc=1&oc_plan=7"), { ...base, plan: 7 });
eq("link: junk values are dropped", parseArrival("", "?oc=1&oc_focus=-3&oc_view=pie&oc_color=<b>&oc_as_of=yesterday&oc_plan=x"),
   { ...base });
eq("link: names never travel (ids only)", parseArrival("", "?oc=1&oc_focus=Nguyen").focus, null);
eq("link wins over nothing, ⌘K focus kept", parseArrival("me", "?oc=1&oc_view=list"), { ...base, me: true, view: "list" });
eq("no oc flag: link params ignored", parseArrival("", "?oc_focus=5&oc_view=lr"), null);

console.log(`\n${n - failed} of ${n} passed`);
process.exit(failed ? 1 : 0);
