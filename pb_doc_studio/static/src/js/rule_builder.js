/** @odoo-module **/
/**
 * "Show only when…" — the small rule builder of a paragraph (DOCSTUDIO F3).
 *
 * A rule is `{match: "all"|"any", lines: [{field, op, value}]}`, the same
 * shape the server checks against its fixed operator table (no expression is
 * ever evaluated). The sentence under the lines is the pill the paragraph
 * will carry: "Only when Country of work is Indonesia".
 */
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { dsIc } from "./doc_icons";
import { fold } from "./doc_words";

const NO_VALUE = ["empty", "filled"];

/** The plain sentence of a rule (mirrors pb.doc.studio._pbds_rule_sentence). */
export function ruleSentence(rule, conditions) {
    if (!rule || !(rule.lines || []).length || !conditions) { return ""; }
    const fields = Object.fromEntries((conditions.fields || []).map((f) => [f.key, f]));
    const opLabel = (kind, op) => {
        const row = ((conditions.ops || {})[kind] || []).find((o) => o.value === op);
        return row ? row.label : op;
    };
    const parts = [];
    for (const line of rule.lines) {
        const f = fields[line.field];
        if (!f) { parts.push(_t("a field that no longer exists")); continue; }
        const op = opLabel(f.type, line.op);
        if (NO_VALUE.includes(line.op)) { parts.push(`${f.label} ${op}`); continue; }
        if (f.type === "bool") { parts.push(`${f.label} ${op} ${line.value ? _t("Yes") : _t("No")}`); continue; }
        const labels = Object.fromEntries((f.options || []).map((o) => [String(o.value), o.label]));
        const vals = Array.isArray(line.value) ? line.value : [line.value];
        const shown = vals.filter((v) => v !== null && v !== undefined && v !== "")
            .map((v) => labels[String(v)] || String(v)).join(", ");
        parts.push(`${f.label} ${op} ${shown || "…"}`);
    }
    const joiner = rule.match === "any" ? _t(" or ") : _t(" and ");
    return _t("Only when %s", parts.join(joiner));
}

export function ruleComplete(rule, conditions) {
    if (!rule || !(rule.lines || []).length) { return false; }
    const fields = Object.fromEntries(((conditions && conditions.fields) || []).map((f) => [f.key, f]));
    return rule.lines.every((l) => {
        const f = fields[l.field];
        if (!f || !l.op) { return false; }
        if (NO_VALUE.includes(l.op) || f.type === "bool") { return true; }
        if (l.op === "in") { return Array.isArray(l.value) && l.value.length > 0; }
        return l.value !== null && l.value !== undefined && l.value !== "";
    });
}

export class RuleBuilder extends Component {
    static template = "pb_doc_studio.RuleBuilder";
    static props = {
        rule: { type: Object, optional: true },
        conditions: { type: Object },
        isNew: { type: Boolean, optional: true },
        onSave: { type: Function },
        onRemove: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        const start = this.props.rule && (this.props.rule.lines || []).length
            ? JSON.parse(JSON.stringify(this.props.rule))
            : { match: "all", lines: [this.blankLine()] };
        this.state = useState({ rule: start, optTerm: {} });
        this.first = useRef("first");
        onMounted(() => {
            const sel = this.first.el && this.first.el.querySelector("select");
            if (sel) { sel.focus(); }
        });
    }

    ic(n, s = 14) { return dsIc(n, s); }
    get fields() { return this.props.conditions.fields || []; }
    get ownFields() { return this.fields.filter((f) => f.own); }
    get baseFields() { return this.fields.filter((f) => !f.own); }
    field(key) { return this.fields.find((f) => f.key === key); }
    blankLine() {
        const f = (this.props.conditions.fields || [])[0];
        return { field: f ? f.key : "", op: f && f.type === "bool" ? "is" : "is", value: f && f.type === "bool" ? true : "" };
    }
    ops(line) {
        const f = this.field(line.field);
        return f ? (this.props.conditions.ops[f.type] || []) : [];
    }
    kind(line) { const f = this.field(line.field); return f ? f.type : "text"; }
    options(line) {
        const f = this.field(line.field);
        const term = fold(this.state.optTerm[line.field] || "");
        const opts = (f && f.options) || [];
        return term ? opts.filter((o) => fold(o.label).includes(term)) : opts;
    }
    needsValue(line) { return !NO_VALUE.includes(line.op); }
    get sentence() { return ruleSentence(this.state.rule, this.props.conditions); }
    get complete() { return ruleComplete(this.state.rule, this.props.conditions); }

    setMatch(m) { this.state.rule.match = m; }
    setField(line, ev) {
        line.field = ev.target.value;
        const f = this.field(line.field);
        line.op = "is";
        line.value = f && f.type === "bool" ? true : "";
    }
    setOp(line, ev) {
        const op = ev.target.value;
        if (op === "in" && !Array.isArray(line.value)) {
            line.value = line.value ? [String(line.value)] : [];
        } else if (op !== "in" && Array.isArray(line.value)) {
            line.value = line.value[0] || "";
        }
        if (NO_VALUE.includes(op)) { line.value = null; }
        line.op = op;
    }
    setValue(line, ev) {
        const k = this.kind(line);
        const v = ev.target.value;
        if (k === "bool") { line.value = v === "1"; return; }
        if (line.op === "in" && k === "text") {
            line.value = v.split(",").map((s) => s.trim()).filter(Boolean);
            return;
        }
        line.value = v;
    }
    textList(line) { return Array.isArray(line.value) ? line.value.join(", ") : (line.value || ""); }
    isValue(line, opt) { return String(opt.value) === String(line.value); }
    isPicked(line, opt) { return Array.isArray(line.value) && line.value.includes(String(opt.value)); }
    togglePick(line, opt) {
        const v = String(opt.value);
        const list = Array.isArray(line.value) ? [...line.value] : [];
        const at = list.indexOf(v);
        if (at >= 0) { list.splice(at, 1); } else { list.push(v); }
        line.value = list;
    }
    onOptTerm(line, ev) { this.state.optTerm[line.field] = ev.target.value; }
    addLine() { this.state.rule.lines.push(this.blankLine()); }
    removeLine(i) {
        this.state.rule.lines.splice(i, 1);
        if (!this.state.rule.lines.length) { this.state.rule.lines.push(this.blankLine()); }
    }
    save() {
        if (!this.complete) { return; }
        this.props.onSave(JSON.parse(JSON.stringify(this.state.rule)));
    }
    onKeydown(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); this.props.onClose(); }
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); this.save(); }
    }
}
