/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

import { RULE_TABS } from "./recipe_text";

/**
 * The journey, as facts — no components, no services, nothing to mount.
 *
 * Everything the screen has to AGREE about lives here: what the six steps are,
 * what each one is called, what the primary button says, and how a number
 * becomes the short headline the pay panel shows. A hoot test can assert every
 * one of them without a browser, and the rail, the footer and the server can
 * never disagree about the order of the steps because there is only one list.
 *
 * Every visible word sits inside a literal `_t(...)` call so the translation
 * extractor can find it — `_t(someVariable)` extracts nothing, which is how a
 * screen ends up half-translated.
 */

/** The six steps, in order. Keys, never numbers (a number changes meaning). */
export const STEPS = ["start", "rules", "connect", "outputs", "test", "finish"];

/**
 * What each step is called, what it promises, and the words at the top of it.
 * `label`/`hint` are the rail; `eyebrow`/`title`/`lead` are the page head.
 */
export const STEP_META = {
    start: {
        label: _t("Start"),
        hint: _t("Name, starter, who you pay"),
        eyebrow: _t("01 / CHOOSE YOUR STARTING POINT"),
        title: _t("A clear start. A connected payroll."),
        lead: _t("Choose how to build this configuration. You can fill in the details now and connect the optional parts whenever you are ready."),
    },
    rules: {
        label: _t("Pay rules"),
        hint: _t("Components, tax, calendar"),
        eyebrow: _t("02 / WHAT GOES INTO PAY"),
        title: _t("Every component. One clear rule."),
        lead: _t("Each thing a person is paid, and each thing taken off, written as a sentence anyone can read — with the calculation underneath it."),
    },
    connect: {
        label: _t("Connect"),
        hint: _t("Sources, payslip, approvals"),
        eyebrow: _t("03 / CONNECT WHAT YOU NEED"),
        title: _t("Connect what you need. Continue when ready."),
        lead: _t("These tasks belong to this company and configuration. Set them up here, or skip individually and come back through the configuration's Settings later."),
    },
    outputs: {
        label: _t("Outputs"),
        hint: _t("Every formula, one table"),
        eyebrow: _t("04 / EVERY NUMBER, IN THE OPEN"),
        title: _t("Nothing hidden. Nothing assumed."),
        lead: _t("The whole configuration in one table: what each component works out, what it depends on, and what it produces for the sample employee."),
    },
    test: {
        label: _t("Test"),
        hint: _t("Try the days that aren't ordinary"),
        eyebrow: _t("05 / THE DAYS THAT AREN'T ORDINARY"),
        title: _t("One click. Meaningful checks."),
        lead: _t("A joiner, a leaver, a tax-band edge, a month with no working days. Every awkward case, run through the real engine."),
    },
    finish: {
        label: _t("Finish"),
        hint: _t("Review and open"),
        eyebrow: _t("06 / A CONFIGURATION YOU CAN EXPLAIN"),
        title: _t("Ready to review. Built to evolve."),
        lead: _t("Everything you decided, in one place — and a configuration you can hand to somebody else and have them understand it."),
    },
};

/** The step after this one, or the same step at the end of the journey. */
export function nextStep(step) {
    const i = STEPS.indexOf(step);
    if (i < 0) return STEPS[0];
    return STEPS[Math.min(i + 1, STEPS.length - 1)];
}

/** The step before this one, or the same step at the start. */
export function prevStep(step) {
    const i = STEPS.indexOf(step);
    if (i <= 0) return STEPS[0];
    return STEPS[i - 1];
}

/** 1-based position, for "Step 3 of 6" and the rail's number circles. */
export function stepNumber(step) {
    const i = STEPS.indexOf(step);
    return (i < 0 ? 0 : i) + 1;
}

/** True once `step` has been passed — the rail's green check. */
export function isDone(step, current) {
    return STEPS.indexOf(step) < STEPS.indexOf(current);
}

/**
 * The primary button never just says "Continue": it says where you are going,
 * so the click is a decision and not a leap.
 */
export function continueLabel(step) {
    switch (step) {
        case "start": return _t("Continue to pay rules");
        case "rules": return _t("Continue to connect");
        case "connect": return _t("Continue to outputs");
        case "outputs": return _t("Continue to test");
        case "test": return _t("Continue to finish");
        default: return _t("Finish & open");
    }
}

/**
 * The tabs a step has to walk through before it is allowed to leave.
 *
 * Keyed by step, so a step that grows tabs later says so here and nothing else
 * changes. A step absent from this map has no tabs and behaves as it always
 * did.
 */
export const STEP_TABS = {
    rules: RULE_TABS,
};

/**
 * Where the primary button goes from here, and what it says on it.
 *
 * A STEP WITH TABS IS NOT ONE SCREEN. Pay rules is three: the components, the
 * tax and protection rules, and the calendar. The button used to say "Continue
 * to connect" from all three, so pressing it on the first one walked past two
 * screens of decisions the person had never seen — and nothing on the way out
 * said they existed. The tab strip was the only clue, and a tab strip reads as
 * "more detail if you want it", not as "two thirds of this step".
 *
 * So the button walks the tabs first, naming each one, and only leaves the step
 * from the last of them. Nobody is trapped: the tab strip and the step rail
 * both still go anywhere in one click. What changes is the DEFAULT path, which
 * is the one almost everybody takes.
 *
 * Returns `{kind, label}` plus `tab` or `step` — one shape, so the caller
 * branches once and the label can never disagree with where it goes.
 */
export function continueTarget(step, tab) {
    const tabs = STEP_TABS[step];
    if (tabs && tabs.length) {
        const here = tab || tabs[0].key;
        const i = tabs.findIndex((t) => t.key === here);
        // An unknown tab counts as the first one, so a stored tab key from an
        // older version walks the whole strip rather than skipping the step.
        const next = tabs[i < 0 ? 1 : i + 1];
        if (next) {
            return { kind: "tab", tab: next.key,
                     label: _t("Continue to %s", next.label) };
        }
    }
    return { kind: "step", step: nextStep(step), label: continueLabel(step) };
}

/**
 * Where Back goes, the same walk in reverse.
 *
 * Symmetry is the whole reason this exists: a Continue that moved one tab and
 * a Back that jumped a whole step would make the pair impossible to reason
 * about, and pressing Back to undo a Continue would lose the step instead.
 */
export function backTarget(step, tab) {
    const tabs = STEP_TABS[step];
    if (tabs && tabs.length) {
        const i = tabs.findIndex((t) => t.key === (tab || tabs[0].key));
        if (i > 0) return { kind: "tab", tab: tabs[i - 1].key };
    }
    return { kind: "step", step: prevStep(step) };
}

/**
 * The headline number: "31.16m", "950k", "1,200", "0".
 *
 * Short because it is set at 36px and a Vietnamese monthly salary is nine
 * digits; the exact numbers stay on the four lines underneath, which are never
 * abbreviated.
 */
export function fmtShort(value) {
    if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
        return "—";
    }
    const n = Number(value);
    const sign = n < 0 ? "−" : "";
    const a = Math.abs(n);
    if (a >= 1e9) return `${sign}${trimZeros(a / 1e9)}bn`;
    if (a >= 1e6) return `${sign}${trimZeros(a / 1e6)}m`;
    if (a >= 1e4) return `${sign}${trimZeros(a / 1e3)}k`;
    return `${sign}${a.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function trimZeros(n) {
    return n.toFixed(2).replace(/\.?0+$/, "");
}

/** The full number, grouped, with a real minus sign for a negative. */
export function fmtFull(value) {
    if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
        return "—";
    }
    const n = Number(value);
    const body = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
    return n < 0 ? `− ${body}` : body;
}

/**
 * "+1.20m" / "−360k" — what changed since the last number on screen.
 * Returns null when there is nothing to say, so the chip is ABSENT rather than
 * empty (an empty chip reads as a value of zero).
 */
export function deltaLabel(prev, next) {
    if (prev === null || prev === undefined) return null;
    if (next === null || next === undefined) return null;
    const diff = Number(next) - Number(prev);
    if (!diff || Number.isNaN(diff)) return null;
    const sign = diff > 0 ? "+" : "−";
    return { text: `${sign}${fmtShort(Math.abs(diff))}`, up: diff > 0 };
}

/** A number the server will accept: finite, or null. */
export function toNumber(raw) {
    if (raw === "" || raw === null || raw === undefined) return null;
    const n = Number(String(raw).replace(/[\s,]/g, ""));
    return Number.isFinite(n) ? n : null;
}

/** The four "who are you paying" tiles. Local is on by default. */
export const AUDIENCES = [
    { key: "local", icon: "users", label: _t("Local employees"),
      hint: _t("Salary, allowances, insurance and income tax") },
    { key: "international", icon: "globe", label: _t("International employees"),
      hint: _t("Residency, insurance eligibility and payment currency") },
    { key: "shortterm", icon: "clock", label: _t("Short-term employees"),
      hint: _t("Contract length, payment threshold and tax commitment") },
    { key: "netpay", icon: "wallet", label: _t("Guaranteed take-home pay"),
      hint: _t("A specialist recipe for net-to-gross contracts") },
];

/** The real-life checklist. The first two are ticked to begin with. */
export const REALLIFE = [
    { key: "joiners", on: true, label: _t("Joiners & leavers"),
      hint: _t("Part-month pay for anyone who starts or stops mid-period") },
    { key: "annual", on: true, label: _t("Annual & event-based pay"),
      hint: _t("Thirteenth month, bonuses and one-off payments") },
    { key: "midmonth", on: false, label: _t("Salary changes within a month"),
      hint: _t("Two salaries in one period, split by the day it changed") },
    { key: "arrears", on: false, label: _t("Corrections & arrears"),
      hint: _t("Something missed last month, paid this month") },
];

/** The situations a brand-new journey starts with. */
export function freshSituations() {
    return {
        audiences: AUDIENCES.filter((a) => a.key === "local").map((a) => a.key),
        reallife: REALLIFE.filter((r) => r.on).map((r) => r.key),
    };
}

/** Toggle membership of a list, returning a new list (never mutating state). */
export function toggle(list, key) {
    const set = new Set(list || []);
    if (set.has(key)) {
        set.delete(key);
    } else {
        set.add(key);
    }
    return [...set];
}

/** The first day of next month, as `YYYY-MM-DD` — the effective-from default. */
export function firstOfNextMonth(today = new Date()) {
    const d = new Date(today.getFullYear(), today.getMonth() + 1, 1);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-01`;
}

/** "saved just now" / "saved 2 min ago" / "saved 3 hours ago". */
export function savedAgo(ms) {
    if (ms === null || ms === undefined) return "";
    const secs = Math.max(0, Math.round(ms / 1000));
    if (secs < 45) return _t("saved just now");
    const mins = Math.round(secs / 60);
    if (mins < 60) return _t("saved %s min ago", mins);
    const hours = Math.round(mins / 60);
    if (hours < 24) {
        return hours === 1 ? _t("saved 1 hour ago") : _t("saved %s hours ago", hours);
    }
    const days = Math.round(hours / 24);
    return days === 1 ? _t("saved 1 day ago") : _t("saved %s days ago", days);
}

/** A setup key that survives a reload of this journey but nothing more. */
export function freshToken() {
    const rnd = (globalThis.crypto && globalThis.crypto.randomUUID)
        ? globalThis.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `bp-${rnd}`;
}
