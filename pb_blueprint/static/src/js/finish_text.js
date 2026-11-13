/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

import { evidenceChip, lastRunLine } from "./outputs_text";
import { statusPill } from "./connect_text";

/**
 * The words on the Finish step — and nothing else.
 *
 * No component, no service, nothing to mount, so a hoot test can assert every
 * sentence this step is capable of saying without a browser or a server.
 *
 * **Every `_t()` is built inside a function.** A label created at module scope
 * is a lazy `TranslatedString` whose `valueOf()` refuses before translations
 * load, which is the whole of BP28/BP37; one created at call time is an
 * ordinary string. Nothing in this file can hit that path.
 */

/** The three counting tiles, in reading order. */
export function finishTiles(counts) {
    const c = counts || {};
    return [
        { key: "components", icon: "layers", value: Number(c.components || 0),
          label: _t("Pay components"),
          hint: _t("Everything this payroll can pay or take off") },
        { key: "formulas", icon: "sigma", value: Number(c.formulas || 0),
          label: _t("Formula rules"),
          hint: _t("Amounts the payroll works out for itself") },
        { key: "inputs", icon: "table", value: Number(c.inputs || 0),
          label: _t("Inputs"),
          hint: _t("Numbers the payroll has to be given each run") },
    ];
}

/**
 * The identity card: label / value pairs, in the order somebody reads them.
 *
 * A value the server had nothing to say about is left OUT rather than shown
 * empty — a row reading "Effective from —" is a question mark where there is no
 * question.
 */
export function identityRows(identity) {
    const id = identity || {};
    const cal = id.calendar || {};
    const pay = id.payment || {};
    const rows = [
        { key: "name", label: _t("Name"), value: id.name || "" },
        { key: "code", label: _t("Reference"), value: id.code || "", mono: true },
        { key: "company", label: _t("Company"), value: id.company || "" },
        { key: "country", label: _t("Country"), value: id.country || "" },
        { key: "cycle", label: _t("Kind of pay run"), value: id.cycle || "" },
        { key: "effective", label: _t("Effective from"),
          value: id.effective_from || _t("Not set") },
        { key: "starter", label: _t("Started from"), value: id.starter || "" },
        { key: "cutoff", label: _t("Inputs close on"),
          value: cutoffValue(cal) },
        { key: "payday", label: _t("Payday"),
          value: paydayValue(cal) },
        { key: "late", label: _t("An input that arrives late"),
          value: cal.late_label || "" },
        { key: "currency", label: _t("Paid in"), value: pay.currency || "" },
        { key: "bank", label: _t("Bank identifier"), value: pay.bank_label || "" },
    ];
    return rows.filter((r) => !!r.value);
}

/**
 * "A fixed day of the month — day 20" / "3 working days before payday".
 *
 * The same shape as `paydayValue` on purpose: the two rows sit next to each
 * other on the review page and they are the same kind of promise.
 */
export function cutoffValue(calendar) {
    const cal = calendar || {};
    if (!cal.cutoff_rule_label) {
        // A configuration saved before the cut-off became a rule: it carries a
        // day and nothing else, and that day is still exactly what it meant.
        return cal.cutoff_day ? _t("Day %s of the month", cal.cutoff_day) : "";
    }
    if (cal.cutoff_rule === "fixed" && cal.cutoff_day) {
        return _t("%(rule)s — day %(day)s",
                  { rule: cal.cutoff_rule_label, day: cal.cutoff_day });
    }
    if (cal.cutoff_rule === "before_payday") {
        const n = Number(cal.cutoff_days_before) || 0;
        return n === 1 ? _t("1 working day before payday")
                       : _t("%s working days before payday", n);
    }
    return cal.cutoff_rule_label;
}

/** "A fixed day of the month — the 25th" / "The last working day of the month". */
export function paydayValue(calendar) {
    const cal = calendar || {};
    if (!cal.payday_rule_label) {
        return "";
    }
    if (cal.payday_rule === "fixed" && cal.payday_day) {
        return _t("%(rule)s — day %(day)s",
                  { rule: cal.payday_rule_label, day: cal.payday_day });
    }
    return cal.payday_rule_label;
}

/**
 * The rule-pack line: which one, and whether this configuration still agrees.
 *
 * Returns null when there is no pack for this country, because "no rule pack"
 * is not a state a payroll manager has to be warned about — it is simply a
 * configuration whose statutory values are its own.
 */
export function packLine(identity) {
    const id = identity || {};
    const pack = id.pack;
    if (!pack) {
        return null;
    }
    const name = [pack.name, pack.version && _t("version %s", pack.version)]
        .filter(Boolean).join(" · ");
    if (id.pack_aligned) {
        return { cls: "is-good", name, text: _t("Aligned with the rule pack") };
    }
    const differ = Number(id.pack_differ || 0);
    if (!differ) {
        return { cls: "is-idle", name,
                 text: _t("None of the pack's values are used here") };
    }
    return {
        cls: "is-warn", name,
        text: differ === 1
            ? _t("1 value differs from the rule pack")
            : _t("%s values differ from the rule pack", differ),
    };
}

/** "3 open" — the chip beside the decisions heading. */
export function decisionCount(n) {
    const count = Number(n || 0);
    return count === 1 ? _t("1 open") : _t("%s open", count);
}

/**
 * What the decisions card says when there is nothing in it.
 *
 * Deliberately not a celebration: a configuration nobody has asked a question
 * about is the ordinary case, not an achievement.
 */
export function decisionsEmpty() {
    return _t("Nothing is waiting for a decision. Every rule says what it does.");
}

/** The line under the heading — the rule about what does and does not block. */
export function decisionsNote() {
    return _t("You can finish with open decisions. Calculations that do not work, and checks that need attention, have to be fixed first.");
}

/** "and 4 more" — said when the list was cut, never silently. */
export function decisionsMore(shown, total) {
    const rest = Math.max(0, Number(total || 0) - Number(shown || 0));
    if (!rest) {
        return "";
    }
    return rest === 1
        ? _t("1 more decision is open, on the step it belongs to.")
        : _t("%s more decisions are open, on the steps they belong to.", rest);
}

/** The checks line: the chip's words, plus when and by whom. */
export function checksLine(checks) {
    const chip = evidenceChip(checks || {});
    const last = lastRunLine(checks || {});
    return { ...chip, last };
}

/**
 * "12 of 12 checks passed" — the honest fraction beside the chip.
 *
 * Two things it will not do. It does not repeat the chip: when everything
 * passed, the chip already says "12 checks passed" and a second copy of the
 * same sentence reads as a screen with nothing to say. And it never claims a
 * pass in the present tense while the rules have MOVED since — the words then
 * are "passed — before the change", which is the only honest tense for
 * evidence somebody has since invalidated (BP43).
 */
export function checksFraction(checks) {
    const c = checks || {};
    const total = Number(c.checks || 0);
    const passed = Number(c.passed || 0);
    if (!total) {
        return _t("No checks yet");
    }
    if (c.stale) {
        return _t("%(passed)s of %(total)s passed — before the change",
                  { passed, total });
    }
    if (passed === total && !Number(c.failed || 0) && !Number(c.pending || 0)) {
        return "";
    }
    return _t("%(passed)s of %(total)s checks passed", { passed, total });
}

/** One optional-task row: its pill, and what it covered. */
export function optionalRow(row) {
    const r = row || {};
    const pill = statusPill(r.status);
    return { task: r.task, label: r.label || "", pill, detail: optionalDetail(r) };
}

/** "12 of 52 inputs have a source" / "8 of 111 components placed". */
export function optionalDetail(row) {
    const r = row || {};
    const total = Number(r.total || 0);
    const done = Number(r.mapped || 0);
    if (r.task === "approvals") {
        if (r.gap) { return r.gap; }
        const route = r.route || [];
        // The route in its own words, not a count: "who has to say yes" is the
        // question, and three names answer it where "3 steps" does not.
        return route.length
            ? route.join(" → ")
            : _t("Nobody has to approve a pay run on this scheme");
    }
    if (!total) {
        return "";
    }
    if (r.task === "mapping") {
        return total === 1
            ? _t("%s of 1 input has a source", done)
            : _t("%(done)s of %(total)s inputs have a source", { done, total });
    }
    return _t("%(done)s of %(total)s components placed", { done, total });
}

/**
 * The words on the primary button, and why it is disabled.
 *
 * A disabled button that says nothing is a dead end, so the reason travels with
 * it and the screen prints it beside the button as well — never in a toast
 * alone (the design bar's own rule).
 */
export function finishButton(gate, finished) {
    if (finished) {
        return { label: _t("Open the configuration"), enabled: true, reason: "" };
    }
    const g = gate || {};
    if (g.ok) {
        return { label: _t("Finish & open"), enabled: true, reason: "" };
    }
    const first = (g.reasons || [])[0] || {};
    return {
        label: _t("Finish & open"),
        enabled: false,
        reason: first.text || _t("This setup is not ready to finish yet."),
        action: first.action || "",
        step: first.step || "",
        tab: first.tab || "",
    };
}

/** "2 things to fix first" — the heading over the blocked list. */
export function blockedHeading(gate) {
    const n = ((gate || {}).reasons || []).length;
    return n === 1
        ? _t("One thing to fix before you can finish")
        : _t("%s things to fix before you can finish", n);
}

/** The sentence under the finish button. It never changes; it is the promise. */
export function finishNote() {
    return _t("Finishing marks the setup as complete and opens the configuration. Switching it on for real pay runs stays a separate, checked step.");
}

/** What the read-only Finish page says at the top of a completed setup. */
export function finishedNote(who, when) {
    if (who && when) {
        return _t("Setup was completed %(when)s by %(who)s.",
                  { when, who });
    }
    return _t("This setup is complete. The configuration is open for anyone to use.");
}

/** The discard dialog's sentence — it names the configuration and the count. */
export function discardText(name, counts) {
    const n = Number((counts || {}).components || 0);
    if (!n) {
        return _t("“%s” and everything set up in it is deleted. This cannot be undone.", name || "");
    }
    return n === 1
        ? _t("“%s” and the 1 component in it are deleted. This cannot be undone.", name || "")
        : _t("“%(name)s” and all %(n)s components in it are deleted. This cannot be undone.", { name: name || "", n });
}
