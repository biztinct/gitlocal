#!/usr/bin/env node
// WDGAP PR-A — the Studio flowchart calculator against the SAME date cases
// the engine runs (pb_hr_payroll_formula/tools/date_function_cases.json).
//
//   node pb_formula_studio/tools/date_functions_battery.mjs
//
// Exit 0 = every case gives the engine's (Excel's) answer. Cases marked
// py_only read component CODES, which the flowchart (cell references only)
// does not, and are skipped here.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const source = readFileSync(join(repo, "pb_formula_studio", "static", "src", "js", "formula_flow_eval.js"), "utf8");
const mod = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const spec = JSON.parse(readFileSync(join(repo, "pb_hr_payroll_formula", "tools", "date_function_cases.json"), "utf8"));

const LETTERS = (s, e) => {
    const out = [];
    for (let c = s.charCodeAt(0); c <= e.charCodeAt(0); c++) out.push(String.fromCharCode(c));
    return out;
};

let pass = 0, fail = 0, skipped = 0;
for (const c of spec.cases) {
    if (c.py_only) { skipped++; continue; }
    const values = { ...spec.defaults, ...(c.values || {}) };
    const got = mod.evalFlowNode(mod.parseFormula(c.formula), { values, expandRange: LETTERS });
    const ok = typeof got === "number" && Math.abs(got - c.expected) < 1e-9;
    if (ok) pass++; else fail++;
    console.log(`[${ok ? "PASS" : "FAIL"}] ${c.id.padEnd(26)} ${c.formula.padEnd(48)} expected=${c.expected} got=${got}`);
}
console.log(`\nJS mirror: ${pass} passed, ${fail} failed, ${skipped} engine-only cases skipped`);
console.log(fail ? `RESULT: ${fail} FAILURES` : "RESULT: ALL GREEN");
process.exit(fail ? 1 : 0);
