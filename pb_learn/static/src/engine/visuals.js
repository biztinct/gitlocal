/** @odoo-module **/
/* =============================================================================
   The four "moments" a lesson step can show.

     calc      the arithmetic behind a number, term by term
     pipeline  a record's lifecycle, stepped forward one stage at a time
     morph     the same record before and after an action, on a manual toggle
     trace     handled in spotlight.js (it needs the overlay layer)

   calc and pipeline read the FIXTURE, because their contents are product facts
   that the practice screens also draw and check_contract.py guards. morph reads
   the LESSON, because its captions are consequence prose that exists only
   inside a lesson.
   ========================================================================== */
import { CASE, CHAINS, STATUS_LABELS } from "./fixture";
import { $, $$, esc, ic, reduced, tx, M, SP} from "./runtime";

/* Lifecycle stage labels come from STATUS_LABELS, which holds the product's
   REAL selection keys. Drawing a stepper out of prose would let the tutorial
   and the product disagree about what a stage is called without anything
   noticing. */
function stageLabel(chain, key) {
    const s = (STATUS_LABELS[chain] || {})[key];
    return s ? tx(s.l) : key;
}

export function pipeHTML(chain, active) {
    const c = CHAINS[chain];
    if (!c) {
        return "";
    }
    const parts = c.nodes.map((n, i) => `
        <span class="lrn-pn ${i === active ? "on" : i < active ? "past" : ""}" data-pn="${i}">
            ${i < active ? ic("check") : ""}${esc(stageLabel(chain, n))}</span>${
        i < c.nodes.length - 1 ? '<span class="lrn-pa"></span>' : ""}`).join("");
    return `<div class="lrn-pipe" data-chain="${esc(chain)}">${parts}
        <span class="lrn-pa"></span>
        <span class="lrn-pn branch">${ic("git-branch")}${esc(tx(c.branch))}</span></div>`;
}

/** Advance a chain one node at a time. Instant under reduced motion — the
 *  information is the order of the stages, not the animation of them. */
export function runPipeline(root, chain) {
    const wrap = $(`.lrn-pipe[data-chain="${chain}"]`, root);
    if (!wrap) {
        return;
    }
    const nodes = $$(".lrn-pn[data-pn]", wrap);
    if (reduced()) {
        nodes.forEach((n, i) => {
            n.className = "lrn-pn " + (i === nodes.length - 1 ? "on" : "past");
        });
        return;
    }
    let i = 0;
    const tick = () => {
        if (!document.body.contains(wrap)) {
            return;
        }
        nodes.forEach((n, k) => {
            n.className = "lrn-pn " + (k === i ? "on" : k < i ? "past" : "");
        });
        i += 1;
        if (i < nodes.length) {
            setTimeout(tick, 620);
        }
    };
    tick();
}

/* ------------------------------------------------------------------- calc
   Mai's July payslip, term by term. The renderer prints the sign, so a
   deduction is stored as a positive number and stays comparable. */
export function calcHTML() {
    const rows = CASE.slip.map((t) =>
        `<div class="lrn-cr ${t.sub ? "sub" : ""}"><span>${esc(tx(t.k))}</span>
            <b>${t.neg ? "−" : ""}${esc(M(t.v))}</b></div>`).join("");
    return `<div class="lrn-calc">${rows}
        <div class="lrn-cr tot"><span>${esc(tx(CASE.slipTotal.k))}</span>
        <b>${esc(M(CASE.slipTotal.v))}</b></div></div>`;
}

/* Last month to this month, decomposed. The flat insurance line is the point:
   overtime moves gross and tax, and does NOT move a contribution charged on
   the registered contract base. */
export function calcKpiHTML() {
    const v = CASE.variance;
    const rows = v.rows.map((r) =>
        `<div class="lrn-cr"><span>${esc(tx(r.k))}</span>
            <b>${r.v > 0 ? "+" : ""}${esc(M(r.v))}</b></div>`).join("");
    return `<div class="lrn-calc">
        <div class="lrn-cr sub"><span>${esc(tx(v.from))}${SP}→ ${esc(tx(v.to))}</span><b></b></div>
        ${rows}
        <div class="lrn-cr tot"><span>${esc(tx(v.total.k))}</span>
        <b>${v.total.v > 0 ? "+" : ""}${esc(M(v.total.v))}</b></div></div>`;
}

/* ---------------------------------------------------------------------- morph
   A manual Before/After toggle, never an automatic cross-fade: the learner
   controls the comparison and can sit on either side for as long as they want.
   Required by the spec, and it is also the only version that works for someone
   reading in their second language. */
/* Row contract, set by the generator and readable straight off the record:
     value = "head|<big number>"   the side's title and its headline figure
     value = "detail"              a line of explanation
     value = "delta"               the one-line "so what", shown last          */
function side(rows, role) {
    const mine = rows.filter((r) => r.role === role);
    const head = mine.find((r) => r.value.startsWith("head|"));
    return {
        title: head ? head.label : "",
        big: head ? head.value.slice(5) : "",
        details: mine.filter((r) => r.value === "detail"),
        delta: mine.find((r) => r.value === "delta"),
    };
}

export function morphHTML(step, shownSide) {
    const rows = step.lines || [];
    const before = side(rows, "morph_before");
    const after = side(rows, "morph_after");
    if (!before.title || !after.title) {
        return "";
    }
    const s = shownSide === "after" ? after : before;
    return `<div class="lrn-morph">
        <div class="lrn-seg">
            <button data-act="morph-before" aria-pressed="${shownSide !== "after"}"
                >${esc(tx(before.title))}</button>
            <button data-act="morph-after" aria-pressed="${shownSide === "after"}"
                >${esc(tx(after.title))}</button>
        </div>
        <div class="lrn-side ${shownSide === "after" ? "after" : ""}">
            <h4>${esc(tx(s.title))}</h4>
            <div class="lrn-big">${esc(s.big)}</div>
            ${s.details.map((r) => `<div class="lrn-mdet">${esc(tx(r.label))}</div>`).join("")}
            ${s.delta ? `<div class="lrn-delta">${esc(tx(s.delta.label))}</div>` : ""}
        </div>
    </div>`;
}
