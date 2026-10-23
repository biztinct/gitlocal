/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Steps 4 and 5, as words. No components, no services, nothing to mount.
 *
 * Every sentence the outputs table, the inspector, the run card and the
 * scoreboard say is built here, from the numbers the server sent, so a hoot
 * test can assert the wording without a browser and no screen can invent a
 * phrase of its own.
 *
 * **Every `_t()` in this file is inside a function.** A label built at module
 * scope is constructed before any language is known, which ships English for
 * ever — and, in a unit test, hands back an object that refuses to be read at
 * all until translations are loaded (BP28, BP37).
 */

/** The filter chips, in the order they are read. `final` is the default. */
export const FILTER_KEYS = [
    "final", "inputs", "earning", "deduction", "benefit",
    "intermediate", "manual", "review", "all",
];

/** The four verdicts a scenario can have, worst news first. */
export const VERDICTS = ["attention", "pending", "not_run", "passed"];

/** What each filter chip says. */
export function filterLabel(key) {
    switch (key) {
        case "final": return _t("Final outputs");
        case "inputs": return _t("Inputs & fixed values");
        case "earning": return _t("Earnings");
        case "deduction": return _t("Deductions");
        case "benefit": return _t("Benefits & employer costs");
        case "intermediate": return _t("Behind the scenes");
        case "manual": return _t("Edited by hand");
        case "review": return _t("Needs a decision");
        default: return _t("All");
    }
}

/** The one line under the chips, explaining what this view is showing. */
export function filterHint(key) {
    switch (key) {
        case "final":
            return _t("The numbers this configuration exists to produce — take-home pay, gross pay, income tax, deductions and employer cost.");
        case "inputs":
            return _t("Numbers the payroll is given, and values that never change.");
        case "earning":
            return _t("Everything added to somebody's pay.");
        case "deduction":
            return _t("Everything taken off.");
        case "benefit":
            return _t("What the employer pays on top, and benefits in kind.");
        case "intermediate":
            return _t("Working figures that exist so another calculation has a number to use.");
        case "manual":
            return _t("Calculations somebody wrote as Excel. These are never rewritten for you.");
        case "review":
            return _t("Components with a question still open, or a calculation the engine cannot read.");
        default:
            return _t("Every component in this configuration.");
    }
}

/** The badge on a row: one word about the calculation behind it. */
export function badgeLabel(badge) {
    switch (badge) {
        // Short on purpose: it sits in a 116px column beside a component name
        // that deserves the room, and the column heading already asks "where
        // did this come from".
        case "generated": return _t("From your settings");
        case "manual": return _t("Written as Excel");
        case "review": return _t("Needs a decision");
        case "problem": return _t("Problem");
        // Not "Given to the payroll" again: the calculation column already says
        // that, and a row that says the same thing twice reads as a mistake.
        case "input": return _t("From your data");
        case "constant": return _t("Fixed value");
        default: return _t("From your settings");
    }
}

/** Which part of pay a component belongs to. */
export function groupLabel(group) {
    switch (group) {
        case "earning": return _t("Earnings");
        case "deduction": return _t("Deductions");
        case "benefit": return _t("Benefits & employer costs");
        case "total": return _t("Totals");
        default: return _t("Inputs & fixed values");
    }
}

/**
 * The money-flow strip: four nodes, three arrows, and what each one filters to.
 *
 * The last node is the point of the whole step — every input and every
 * calculation exists to produce those two numbers — so it carries them rather
 * than a count.
 */
export function flowNodes(strip, totals) {
    const s = strip || {};
    const t = totals || {};
    return [
        {
            key: "inputs",
            n: Number(s.inputs || 0),
            label: Number(s.inputs) === 1
                ? _t("input & fixed value") : _t("inputs & fixed values"),
            filters: ["inputs"],
        },
        {
            key: "components",
            n: Number(s.components || 0),
            label: Number(s.components) === 1 ? _t("component") : _t("components"),
            filters: ["earning", "deduction", "benefit"],
        },
        {
            key: "rules",
            n: Number(s.rules || 0),
            label: Number(s.rules) === 1 ? _t("calculation") : _t("calculations"),
            filters: ["all"],
        },
        {
            key: "totals",
            n: null,
            label: _t("Net pay & employer cost"),
            net: t.net === undefined ? null : t.net,
            employer: t.employer_cost === undefined ? null : t.employer_cost,
            filters: ["final"],
        },
    ];
}

/** A number a person reads: grouped, never abbreviated, "—" when there is none. */
export function fmtValue(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const n = Number(value);
    if (Number.isNaN(n)) {
        return String(value);
    }
    const body = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
    return n < 0 ? `− ${body}` : body;
}

/** What the formula column shows for a row that has no formula. */
export function formulaText(row) {
    const r = row || {};
    if (r.column_type === "input") {
        return _t("Given to the payroll");
    }
    if (r.column_type === "constant") {
        return fmtValue(r.constant_value);
    }
    return r.excel_codes || _t("Nothing is worked out yet");
}

/** True when the formula is long enough to be worth a "show all" toggle. */
export function isLongFormula(row) {
    return String((row || {}).excel_codes || "").length > 52;
}

/**
 * "18 of 21 calculations are checked · 2 are used on the way · 1 is untested".
 *
 * Only the parts that have something in them are named: a clause reading
 * "0 are untested" is noise, and noise is how a line stops being read.
 */
export function coverageLine(coverage) {
    const c = coverage || {};
    const total = Number(c.total || 0);
    if (!total) {
        return _t("There are no calculations to check yet.");
    }
    const asserted = Number(c.asserted || 0);
    const bits = [
        asserted === 1
            ? _t("1 of %s calculations is checked by a confirmed scenario", total)
            : _t("%(asserted)s of %(total)s calculations are checked by a confirmed scenario",
                 { asserted, total }),
    ];
    const exercised = Number(c.exercised || 0);
    if (exercised) {
        bits.push(exercised === 1
            ? _t("1 is used on the way")
            : _t("%s are used on the way", exercised));
    }
    const untested = Number(c.untested_count || 0);
    if (untested) {
        bits.push(untested === 1
            ? _t("1 is untested")
            : _t("%s are untested", untested));
    }
    return bits.join(" · ");
}

/** "Nothing is untested" deserves saying out loud, once, in green. */
export function coverageIsComplete(coverage) {
    const c = coverage || {};
    return Number(c.total || 0) > 0 && Number(c.untested_count || 0) === 0;
}

/**
 * The evidence chip, shared by the Components tab, the Tax tab and the Test
 * step — one answer to "is what we checked still true", said the same way in
 * three places.
 */
export function evidenceChip(evidence) {
    const e = evidence || {};
    if (!e.ever_run) {
        return { cls: "is-idle", icon: "clock", text: _t("Not checked yet") };
    }
    if (e.stale) {
        return {
            cls: "is-stale", icon: "alert",
            text: _t("Changed since the last check — run it again"),
        };
    }
    const failed = Number(e.failed || 0);
    if (failed) {
        return {
            cls: "is-bad", icon: "alert",
            text: failed === 1
                ? _t("1 check needs attention")
                : _t("%s checks need attention", failed),
        };
    }
    const pending = Number(e.pending || 0);
    if (pending) {
        return {
            cls: "is-wait", icon: "clock",
            text: pending === 1
                ? _t("1 check is waiting for you to confirm it")
                : _t("%s checks are waiting for you to confirm them", pending),
        };
    }
    const passed = Number(e.passed || 0);
    return {
        cls: "is-good", icon: "checkCheck",
        text: passed === 1 ? _t("1 check passed") : _t("%s checks passed", passed),
    };
}

/** "Last checked 2 min ago by Mai" — said only when there is something to say. */
export function lastRunLine(evidence) {
    const e = evidence || {};
    if (!e.ever_run) {
        return "";
    }
    const when = agoFrom(e.run_at);
    if (e.run_by && when) {
        return _t("Last checked %(when)s by %(who)s", { when, who: e.run_by });
    }
    if (when) {
        return _t("Last checked %s", when);
    }
    return "";
}

/** "just now" / "4 min ago" / "3 hours ago", from a server timestamp. */
export function agoFrom(stamp, now = Date.now()) {
    if (!stamp) {
        return "";
    }
    const when = Date.parse(String(stamp).replace(" ", "T") + "Z");
    if (Number.isNaN(when)) {
        return "";
    }
    const secs = Math.max(0, Math.round((now - when) / 1000));
    if (secs < 60) {
        return _t("just now");
    }
    const mins = Math.round(secs / 60);
    if (mins < 60) {
        return mins === 1 ? _t("1 min ago") : _t("%s min ago", mins);
    }
    const hours = Math.round(mins / 60);
    if (hours < 24) {
        return hours === 1 ? _t("1 hour ago") : _t("%s hours ago", hours);
    }
    const days = Math.round(hours / 24);
    return days === 1 ? _t("1 day ago") : _t("%s days ago", days);
}

/** The pill beside a scenario. */
export function verdictPill(verdict) {
    switch (verdict) {
        case "passed":
            return { key: "passed", cls: "is-good", icon: "check",
                     label: _t("Passed") };
        case "attention":
            return { key: "attention", cls: "is-bad", icon: "alert",
                     label: _t("Needs attention") };
        case "pending":
            return { key: "pending", cls: "is-wait", icon: "clock",
                     label: _t("Pending your confirmation") };
        default:
            return { key: "not_run", cls: "is-idle", icon: "circle",
                     label: _t("Not checked yet") };
    }
}

/** "the starter's 5 scenarios · 6 boundary cases · your 2 samples". */
export function runPlan(samples) {
    const rows = samples || [];
    const count = (kind) => rows.filter((r) => r.kind === kind).length;
    const bits = [];
    const starter = count("starter");
    if (starter) {
        bits.push(starter === 1
            ? _t("the starting point's 1 scenario")
            : _t("the starting point's %s scenarios", starter));
    }
    const boundary = count("boundary");
    if (boundary) {
        bits.push(boundary === 1
            ? _t("1 boundary case")
            : _t("%s boundary cases", boundary));
    }
    const real = count("real");
    if (real) {
        bits.push(real === 1
            ? _t("1 real person")
            : _t("%s real people", real));
    }
    const yours = count("yours");
    if (yours) {
        bits.push(yours === 1 ? _t("1 of your own") : _t("%s of your own", yours));
    }
    return bits.join(" · ");
}

/** "One click. 12 meaningful checks." — or the honest version of nothing. */
export function runHeadline(samples) {
    const n = (samples || []).length;
    if (!n) {
        return _t("Nothing to check yet.");
    }
    return n === 1
        ? _t("One click. 1 meaningful check.")
        : _t("One click. %s meaningful checks.", n);
}

/** "902 people" / "1 person" — a pay run, in the picker. */
export function peopleCount(n) {
    const count = Number(n || 0);
    return count === 1 ? _t("1 person") : _t("%s people", count);
}

/** "3 values came from a real source" — how much of this person is real. */
export function sourcedLine(n) {
    const count = Number(n || 0);
    if (!count) {
        return _t("no value came from a real source");
    }
    return count === 1
        ? _t("1 value came from a real source")
        : _t("%s values came from a real source", count);
}

/** What "Show the whole chain" says when it had to stop. */
export function chainMore(more) {
    const n = Number(more || 0);
    if (!n) {
        return "";
    }
    return n === 1
        ? _t("and 1 more further away")
        : _t("and %s more further away", n);
}

/** The five things this release does not do, said plainly rather than hidden. */
export function beyondRecipes() {
    return [
        { key: "rates",
          title: _t("More than one salary rate in a month"),
          text: _t("Somebody whose pay changed part-way through the period, split by the day it changed.") },
        { key: "arrears",
          title: _t("Arrears from a previous year"),
          text: _t("Money owed for a period that has already been reported to the tax office.") },
        { key: "advance",
          title: _t("Mid-cycle advances and loan recovery"),
          text: _t("An advance paid in the middle of the month and taken back at the end of it.") },
        { key: "netpay",
          title: _t("Guaranteed take-home pay and shadow payroll"),
          text: _t("A contract written as a net figure, where the tax has to be worked backwards.") },
        { key: "missing",
          title: _t("Two rules that both apply, or an input nobody sent"),
          text: _t("What a payroll should do when the answer is genuinely ambiguous.") },
    ];
}

/** Rows that match what somebody typed, across name, code and calculation. */
export function filterRows(rows, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
        return rows || [];
    }
    return (rows || []).filter((r) =>
        String(r.name || "").toLowerCase().includes(q)
        || String(r.code || "").toLowerCase().includes(q)
        || String(r.excel_codes || "").toLowerCase().includes(q)
        || String(r.letter || "").toLowerCase() === q);
}

/**
 * Which slice of a long list to actually paint.
 *
 * Fixed row height, a few rows of overscan either side. Returns the slice and
 * the two spacer heights that keep the scrollbar honest, so a configuration
 * with four hundred components scrolls like one with ten.
 */
export function windowOf(total, scrollTop, viewport, rowHeight, overscan = 6) {
    const rows = Math.max(0, Number(total || 0));
    const h = Math.max(1, Number(rowHeight || 44));
    const first = Math.max(0, Math.floor(Number(scrollTop || 0) / h) - overscan);
    const visible = Math.ceil(Math.max(0, Number(viewport || 0)) / h) + overscan * 2;
    const last = Math.min(rows, first + visible);
    return { first, last, top: first * h, bottom: Math.max(0, (rows - last) * h) };
}
