/** @odoo-module **/
/**
 * SOURCING S4 — the source vocabulary, in ONE place.
 *
 * Eight kinds, eight labels, eight glyphs, and the single sentence every surface
 * says about a component. The components rail, the card subtitle, the Cell Editor,
 * the grid header and both mapping boards all read from here, because five surfaces
 * paraphrasing the same fact five ways is exactly the confusion this programme
 * exists to remove — and because a duplicated predicate is a predicate that will be
 * half-fixed (MF31).
 *
 * The ICON carries the meaning and the colour is decoration: grid, cloud, sigma,
 * briefcase, person, equals, padlock and dashed circle are distinguishable at 12px
 * with no colour at all, so the chips stay readable to a colour-blind user.
 *
 * Labels are resolved through `_t()` at CALL time, never at module scope — at module
 * scope the translations are not loaded yet and every label would freeze in English.
 */
import { _t } from "@web/core/l10n/translation";

export const SOURCES = [
    { key: "excel", icon: "sheet" },
    { key: "feed", icon: "cloud" },
    { key: "rule", icon: "sigma" },
    // JOURNEY J10 — the record destination is a SOURCE, at rank 4, and it now
    // has three spellings instead of one. "Employee record" was being shown for
    // a mapping onto the contract as readily as one onto the employee, because
    // the tier it came from was a bare set of ids that could not tell them
    // apart. Each glyph is distinguishable from the others at 12px with no
    // colour: a document is not a briefcase and neither is a bank.
    { key: "employee_field", icon: "person" },
    { key: "contract_field", icon: "filetext" },
    { key: "bank_account", icon: "bank" },
    { key: "contract_component", icon: "briefcase" },
    { key: "calculated", icon: "equals" },
    { key: "constant", icon: "lock" },
    { key: "none", icon: "dashed" },
];

/** Kinds that describe where a component READS, as opposed to what it IS. Only
 *  these can meaningfully disagree with what a run did. */
const READ_KINDS = ["excel", "feed", "rule", "none"];

export function srcMeta(kind) {
    return SOURCES.find((s) => s.key === (kind || "none")) || SOURCES[SOURCES.length - 1];
}

export function srcIcon(kind) {
    return srcMeta(kind).icon;
}

export function srcLabel(kind) {
    return {
        excel: _t("Spreadsheet"),
        feed: _t("Connected system"),
        rule: _t("Rule output"),
        contract_component: _t("Contract component"),
        employee_field: _t("Employee record"),
        contract_field: _t("Contract record"),
        bank_account: _t("Bank account"),
        calculated: _t("Calculated"),
        constant: _t("Fixed value"),
        none: _t("No source"),
    }[kind || "none"] || _t("No source");
}

export function srcDeclared(c) {
    return (c && c.source && c.source.declared) || { kind: "none", key: "" };
}

export function srcActual(c) {
    return (c && c.source && c.source.actual) || null;
}

export function srcOf(c) {
    return srcDeclared(c).kind || "none";
}

/** Does what the last run did differ from what the component is set to read?
 *  This is deliberately a first-class question: a disagreement is the single most
 *  useful thing these chips can tell an owner, so nothing averages it away. */
export function srcDisagrees(c) {
    const d = srcDeclared(c);
    const a = srcActual(c);
    if (!a || !d || !READ_KINDS.includes(d.kind)) {
        return false;
    }
    return a.kind !== d.kind;
}

/** Is this component FED from somewhere, as opposed to being something the scheme
 *  produces itself? A calculated or fixed component has no source to report, and a
 *  surface that already says "Calculated formula" must not then add "Calculated". */
export function srcIsFed(c) {
    return !["calculated", "constant"].includes(srcOf(c));
}

/** The one sentence, used verbatim by every surface. */
export function srcSentence(c, hasAnyRun = true) {
    const d = srcDeclared(c);
    const a = srcActual(c);
    const q = (k) => (k ? ` “${k}”` : "");
    // J10 — a record source folds on the TECHNICAL field name (`job_id`) and
    // ships the human one beside it. Show the human one; the key is for
    // comparing, not for reading.
    let out = d.kind === "none" ? _t("No source chosen")
        : `${srcLabel(d.kind)}${q(d.label || d.key)}`;
    if (!a) {
        return hasAnyRun ? out : `${out} · ${_t("This scheme has not been run yet")}`;
    }
    if (a.fell_back) {
        out += ` · ${_t("Fell back to")} ${srcLabel(a.kind)}`;
    } else if (srcDisagrees(c)) {
        out += ` · ${_t("Last run used a different source")}: ${srcLabel(a.kind)}${q(a.key)}`;
    } else if (a.key && a.key !== d.key) {
        out += ` · ${_t("last run matched")}${q(a.key)}`;
    }
    if (a.ignored) {
        out += ` · ${_t("Also arrived from")} ${srcLabel(a.ignored.src)} — ${_t("not used")}`;
    }
    if (a.run) {
        out += ` · ${a.run}`;
    }
    return out;
}
