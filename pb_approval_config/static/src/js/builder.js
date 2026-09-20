/** @odoo-module **/
/**
 * The workflow builder: Purpose → People → Safeguards → Review & publish.
 *
 * THE HERO IS THE SENTENCE. At the top of the People step is one line of
 * ordinary English saying exactly what this route does — "After it is sent in,
 * the HR lead for its part of the business reviews it. Then the Finance
 * approver gives final approval when the amount is 300,000,000 or more." It
 * rewrites itself on every change, so nobody has to read a diagram to know what
 * they just built. The browser writes it for speed; the server writes the one
 * that is stored, and every save replaces the mirror with the real one.
 *
 * THE SECOND HERO IS "TRY AN EXAMPLE". A route is abstract until it names
 * people. The right-hand panel runs the draft against facts the reader chooses
 * and prints who it would actually reach — including the backup standing in for
 * somebody on holiday, including the step that is skipped because the amount is
 * too small, and including the step nobody can fill, with the one button that
 * mends it. Underneath, "Check whole coverage" does the same for every part of
 * the business at once, because one good example is not proof.
 *
 * NOTHING HERE BLOCKS THE BUSINESS. The four warnings the engine can raise —
 * nobody checks this, only one person signs it off, the independence rule is
 * off, a part of the business has nobody — are shown as things to CONFIRM, one
 * tick box each, recorded with the publish under the publisher's name. Only a
 * structural error (a route that could not be read, two routes that tie) stops
 * a publish, because only a structural error is a fact rather than an opinion.
 *
 * WHAT IT NEVER SHOWS. A model name, a state key, a step "kind" as stored, or
 * the word for any of the machinery. Every string goes through `_t`.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { PickerDrawer } from "@pb_approval_config/js/picker_drawer";
import {
    copy, decisionSteps, initials, kindLabel, money, nextStepKey, sentence,
    shortMoney, when, whoLabel,
} from "@pb_approval_config/js/sentence";

/** The four amounts the ladder offers before anybody types one of their own. */
const LADDER = [0, 100000000, 300000000, 600000000, 1000000000];

export class ApprovalBuilder extends Component {
    static template = "pb_approval_config.ApprovalBuilder";
    static components = { PickerDrawer };
    static props = {
        workflowId: { type: Number },
        onBack: { type: Function },
        onOpenPeople: { type: Function, optional: true },
        onOpenInbox: { type: Function, optional: true },
    };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.kindLabel = kindLabel;
        this.money = money;
        this.shortMoney = shortMoney;
        this.when = when;
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            failed: "",
            step: 1,
            data: null,
            definition: null,
            summary: "",
            saved: _t("Saved"),
            saving: false,
            errors: [],
            warnings: [],
            addMenu: false,
            picker: null,
            example: {},
            preview: null,
            previewBusy: false,
            coverage: null,
            coverageBusy: false,
            publication: null,
            confirmed: {},
            publishAt: "",
            reason: "",
            published: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    // ============================================================== reading
    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            const data = await this.orm.call(
                "pb.approval.matrix", "get_workflow", [this.props.workflowId]);
            this.state.data = data;
            this.state.definition = copy(data.draft.definition);
            this.state.summary = data.draft.summary || this.mirror;
            this.state.example = {
                ...copy(data.example_defaults),
                facts: {},
            };
            this.state.publishAt = "";
            this.state.reason = "";
            await this.runExample();
        } catch (error) {
            this.state.failed = error.data && error.data.message
                ? error.data.message
                : _t("This workflow could not be opened.");
        } finally {
            this.state.loading = false;
        }
    }

    // =============================================================== labels
    get workflow() { return (this.state.data || {}).workflow || {}; }
    get capabilities() { return (this.state.data || {}).capabilities || {}; }
    get roles() { return (this.state.data || {}).roles || []; }
    get definition() { return this.state.definition || { steps: [] }; }
    get steps() { return this.definition.steps || []; }
    get tiers() { return this.definition.tiers || {}; }
    get safeguards() { return this.definition.safeguards || {}; }
    get currency() {
        return ((this.state.data || {}).example_defaults || {}).currency_name
            || "";
    }

    get roleNames() {
        const names = {};
        for (const role of this.roles) { names[role.key] = role.name; }
        return names;
    }

    get peopleNames() {
        const names = {};
        for (const row of (this.state.preview || {}).steps || []) {
            for (const person of row.people || []) {
                names[person.user_id] = person.name;
            }
        }
        return names;
    }

    get factLabels() {
        const labels = {};
        for (const [key, spec] of Object.entries(this.capabilities.facts || {})) {
            labels[key] = (spec || {}).label || key;
        }
        return labels;
    }

    /** The browser's own sentence, for the keystroke it was just given. */
    get mirror() {
        return sentence(this.definition, this.roleNames, this.peopleNames,
                        this.factLabels, this.currency);
    }

    get progress() {
        return [
            { n: 1, label: _t("Purpose") },
            { n: 2, label: _t("People") },
            { n: 3, label: _t("Safeguards") },
            { n: 4, label: _t("Review & publish") },
        ];
    }

    get decisionSteps() { return decisionSteps(this.definition); }

    get numericFacts() {
        return Object.entries(this.capabilities.facts || {})
            .filter(([, spec]) => ["decimal", "int", "percent"]
                .includes((spec || {}).type))
            .map(([key, spec]) => ({ key, label: (spec || {}).label || key }));
    }

    get conditionFacts() {
        return Object.entries(this.capabilities.facts || {})
            .map(([key, spec]) => ({
                key, label: (spec || {}).label || key,
                type: (spec || {}).type || "char",
            }));
    }

    /** The bands the ladder draws, and which one the example lands in. */
    get bands() {
        const thresholds = [...new Set(this.decisionSteps
            .map((step) => Number(step.min_amount || 0)))].sort((a, b) => a - b);
        const amount = Number(this.state.example.amount || 0);
        return thresholds.map((from, index) => {
            const to = thresholds[index + 1];
            return {
                from, to,
                hit: amount >= from && (to === undefined || amount < to),
                label: from === 0
                    ? (to === undefined
                        ? _t("Any amount")
                        : _t("Under %s", shortMoney(to, this.currency)))
                    : (to === undefined
                        ? _t("%s and above", shortMoney(from, this.currency))
                        : _t("%(from)s to %(to)s", {
                            from: shortMoney(from, this.currency),
                            to: shortMoney(to, this.currency) })),
                route: this.decisionSteps
                    .filter((step) => Number(step.min_amount || 0) <= from)
                    .map((step) => whoLabel(step.who, this.roleNames,
                                            this.peopleNames)),
            };
        });
    }

    get ladderAmounts() {
        return LADDER.map((value) => ({
            value,
            label: value === 0
                ? _t("for any amount")
                : _t("from %s", money(value, this.currency)),
        }));
    }

    get addItems() {
        return [
            { key: "review", icon: "eye", title: _t("Review"),
              sub: _t("Somebody checks it and passes it on.") },
            { key: "approve", icon: "stamp", title: _t("Final approval"),
              sub: _t("Somebody signs it off.") },
            { key: "joint", icon: "users", title: _t("Joint approval"),
              sub: _t("Named people must all approve.") },
            { key: "any", icon: "userCheck", title: _t("Any one of a team"),
              sub: _t("The first person free decides it.") },
            { key: "cond", icon: "filter", title: _t("Only when…"),
              sub: _t("A step that applies in some cases and not others.") },
            { key: "notify", icon: "bell", title: _t("Tell somebody"),
              sub: _t("Let a person know. Never counted as a check.") },
            { key: "fast", icon: "zap", title: _t("No approval needed"),
              sub: _t("Applied at once and recorded. Replaces the steps; you confirm it when you publish.") },
        ];
    }

    // =============================================================== saving
    async save() {
        if (!this.state.data) { return; }
        this.state.saving = true;
        this.state.saved = _t("Saving…");
        try {
            const result = await this.orm.call(
                "pb.approval.matrix", "save_draft",
                [this.state.data.draft.version_id,
                 this.state.data.draft.draft_revision,
                 this.state.definition,
                 { name: this.workflow.name }]);
            this.state.data.draft.draft_revision = result.draft_revision;
            this.state.summary = result.summary;
            this.state.errors = result.errors || [];
            this.state.warnings = result.warnings || [];
            this.state.saved = _t("Saved just now");
            this.state.coverage = null;
            this.state.publication = null;
            await this.runExample();
        } catch (error) {
            this.state.saved = _t("Could not save");
            this.notif.add(
                (error.data && error.data.message)
                || _t("That change could not be saved."),
                { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    /** Every edit goes through here, so the sentence and the save stay in step. */
    async edit(change) {
        change();
        this.state.summary = this.mirror;
        await this.save();
    }

    async renameWorkflow(ev) {
        const name = (ev.target.textContent || "").trim();
        if (!name || name === this.workflow.name) { return; }
        this.state.data.workflow.name = name;
        await this.save();
    }

    async renameStep(key, ev) {
        const title = (ev.target.textContent || "").trim();
        const step = this.steps.find((one) => one.key === key);
        if (!step || !title || title === step.title) { return; }
        await this.edit(() => { step.title = title; });
    }

    // ============================================================= the steps
    async addStep(kind) {
        this.state.addMenu = false;
        const key = nextStepKey(this.definition);
        if (kind === "fast") {
            await this.edit(() => {
                this.state.definition.steps = [{
                    key, kind: "fast", title: _t("No approval needed"),
                    who: { mode: "people", user_ids: [] },
                    min_amount: 0, condition: null,
                }].concat(this.steps.filter((s) => s.kind === "notify"));
                this.state.definition.tiers = { enabled: false, fact: null };
            });
            this.notif.add(
                _t("Nothing will be checked before this happens. Every one is still recorded, and you confirm the choice when you publish."),
                { type: "warning" });
            return;
        }
        const firstRole = (this.roles[0] || {}).key || "";
        const made = {
            joint: { kind: "joint", title: _t("Joint sign-off"),
                     who: { mode: "people", user_ids: [], all: true } },
            any: { kind: "any", title: _t("Team check"),
                   who: { mode: "team", user_ids: [], label: _t("The desk") } },
            notify: { kind: "notify", title: _t("Tell whoever sent it in"),
                      who: { mode: "preparer" } },
            cond: { kind: "approve", title: _t("Extra check"),
                    who: { mode: "role", role: firstRole, scope: "company" },
                    condition: { fact: (this.conditionFacts[0] || {}).key || "",
                                 op: "eq", value: true } },
            review: { kind: "review", title: _t("Review"),
                      who: { mode: "role", role: firstRole, scope: "area" } },
            approve: { kind: "approve", title: _t("Final approval"),
                       who: { mode: "role", role: firstRole,
                              scope: "company" } },
        }[kind];
        const step = {
            key, min_amount: 0, condition: null, ...copy(made),
        };
        await this.edit(() => {
            const steps = this.steps.filter((one) => one.kind !== "fast");
            const notifyAt = steps.findIndex((one) => one.kind === "notify");
            if (step.kind !== "notify" && notifyAt >= 0) {
                steps.splice(notifyAt, 0, step);
            } else {
                steps.push(step);
            }
            this.state.definition.steps = steps;
        });
        if (step.kind !== "notify") { this.openPicker(key); }
    }

    async removeStep(key) {
        await this.edit(() => {
            this.state.definition.steps = this.steps
                .filter((one) => one.key !== key);
            if (!this.steps.some((one) => one.kind !== "notify")) {
                this.state.definition.steps.unshift({
                    key: nextStepKey(this.state.definition), kind: "fast",
                    title: _t("No approval needed"),
                    who: { mode: "people", user_ids: [] },
                    min_amount: 0, condition: null,
                });
                this.state.definition.tiers = { enabled: false, fact: null };
            }
        });
        if (this.steps.some((one) => one.kind === "fast")) {
            this.notif.add(
                _t("No steps are left, so this would be applied at once and recorded. Add a step to bring a check back."),
                { type: "warning" });
        }
    }

    async removeFast(key) {
        await this.edit(() => {
            this.state.definition.steps = this.steps
                .filter((one) => one.key !== key);
        });
        this.state.addMenu = true;
    }

    async moveStep(index, delta) {
        const target = index + delta;
        if (target < 0 || target >= this.steps.length) { return; }
        await this.edit(() => {
            const steps = this.steps;
            const held = steps[index];
            steps[index] = steps[target];
            steps[target] = held;
        });
    }

    async setSeatMode(key, all) {
        await this.edit(() => {
            const step = this.steps.find((one) => one.key === key);
            step.who.all = all;
            step.kind = all ? "joint" : "any";
        });
    }

    async setMinAmount(key, ev) {
        const value = Number(ev.target.value || 0);
        await this.edit(() => {
            this.steps.find((one) => one.key === key).min_amount = value;
        });
    }

    async setCondition(key, ev) {
        const fact = ev.target.value;
        await this.edit(() => {
            const step = this.steps.find((one) => one.key === key);
            if (!fact) {
                step.condition = null;
                return;
            }
            const spec = this.conditionFacts.find((one) => one.key === fact)
                || {};
            step.condition = {
                fact,
                op: "eq",
                value: spec.type === "bool" ? true : "",
            };
        });
    }

    async setConditionValue(key, ev) {
        const raw = ev.target.value;
        await this.edit(() => {
            const step = this.steps.find((one) => one.key === key);
            if (!step.condition) { return; }
            step.condition.value = raw === "true" ? true
                : raw === "false" ? false : raw;
        });
    }

    stepNumber(step) {
        return this.decisionSteps.indexOf(step) + 1;
    }

    whoOf(step) {
        return whoLabel(step.who, this.roleNames, this.peopleNames);
    }

    previewOf(key) {
        return ((this.state.preview || {}).steps || [])
            .find((row) => row.key === key) || null;
    }

    // ------------------------------------------------------------ the tiers
    async toggleTiers() {
        await this.edit(() => {
            const on = !this.tiers.enabled;
            this.state.definition.tiers = {
                enabled: on,
                fact: on ? (this.tiers.fact
                            || (this.numericFacts[0] || {}).key || null)
                    : null,
            };
            if (!on) {
                for (const step of this.steps) { step.min_amount = 0; }
            }
        });
    }

    async setTierFact(ev) {
        const fact = ev.target.value;
        await this.edit(() => { this.state.definition.tiers.fact = fact; });
    }

    // ------------------------------------------------------- the safeguards
    async setIndependent(value) {
        await this.edit(() => { this.safeguards.independent = value; });
    }

    async toggleSelfException() {
        await this.edit(() => {
            const current = this.safeguards.self_exception || {};
            this.safeguards.self_exception = { enabled: !current.enabled };
        });
    }

    async setRepeated(ev) {
        const value = ev.target.value;
        await this.edit(() => { this.safeguards.repeated = value; });
    }

    async setDueKind(ev) {
        const kind = ev.target.value;
        await this.edit(() => {
            this.safeguards.due = { ...(this.safeguards.due || {}), kind };
        });
    }

    async setDueDays(ev) {
        const days = Math.max(Number(ev.target.value || 1), 1);
        await this.edit(() => {
            this.safeguards.due = { ...(this.safeguards.due || {}), days };
        });
    }

    async setLate(field, ev) {
        const value = Math.max(Number(ev.target.value || 1), 1);
        await this.edit(() => {
            this.safeguards.late = {
                ...(this.safeguards.late || {}), [field]: value };
        });
    }

    async toggleReassign() {
        await this.edit(() => {
            const late = this.safeguards.late || {};
            this.safeguards.late = { ...late, reassign: !late.reassign };
        });
    }

    async addEvidence() {
        await this.edit(() => {
            const list = this.safeguards.evidence || [];
            list.push({ name: _t("A document"), when: _t("Before it is approved"),
                        on: true });
            this.safeguards.evidence = list;
        });
    }

    async toggleEvidence(index) {
        await this.edit(() => {
            const item = (this.safeguards.evidence || [])[index];
            if (item) { item.on = !item.on; }
        });
    }

    async renameEvidence(index, field, ev) {
        const text = (ev.target.value || "").trim();
        await this.edit(() => {
            const item = (this.safeguards.evidence || [])[index];
            if (item) { item[field] = text; }
        });
    }

    async removeEvidence(index) {
        await this.edit(() => {
            this.safeguards.evidence = (this.safeguards.evidence || [])
                .filter((unused, n) => n !== index);
        });
    }

    // ======================================================== try an example
    async runExample() {
        if (!this.state.data) { return; }
        this.state.previewBusy = true;
        try {
            this.state.preview = await this.orm.call(
                "pb.approval.matrix", "preview",
                [this.state.data.draft.version_id, this.state.example]);
        } catch (error) {
            this.state.preview = null;
            this.notif.add(
                (error.data && error.data.message)
                || _t("The example could not be worked out."),
                { type: "danger" });
        } finally {
            this.state.previewBusy = false;
        }
    }

    async setExampleAmount(ev) {
        const amount = Number(ev.target.value || 0);
        this.state.example.amount = amount;
        const fact = this.tiers.fact;
        if (fact) {
            this.state.example.facts = {
                ...(this.state.example.facts || {}),
                [fact]: { value: amount, unit: this.currency },
            };
        }
        await this.runExample();
    }

    async setExampleScope(ev) {
        const key = ev.target.value;
        const option = this.scopeOptions.find((one) => one.key === key);
        this.state.example.scope_keys = key ? [key, ""] : [""];
        this.state.example.scope_label = option
            ? option.label : this.workflow.company_name;
        await this.runExample();
    }

    async setExampleFact(key, ev) {
        const spec = this.conditionFacts.find((one) => one.key === key) || {};
        const raw = ev.target.value;
        const value = spec.type === "bool" ? raw === "true"
            : ["decimal", "int", "percent"].includes(spec.type)
                ? Number(raw || 0) : raw;
        this.state.example.facts = {
            ...(this.state.example.facts || {}), [key]: { value, unit: "" },
        };
        await this.runExample();
    }

    get scopeOptions() {
        const out = [];
        for (const level of (this.state.data || {}).scope_options || []) {
            out.push(...(level.options || []));
        }
        return out;
    }

    get exampleFacts() {
        return this.conditionFacts.filter(
            (fact) => fact.key !== this.tiers.fact);
    }

    exampleValue(key) {
        const held = (this.state.example.facts || {})[key];
        return held ? held.value : "";
    }

    get resultBadge() {
        const level = (this.state.preview || {}).level || "ready";
        return {
            ready: { tone: "ok", icon: "checkCircle",
                     label: _t("Ready for this example") },
            warn: { tone: "warn", icon: "alert",
                    label: _t("Worth a look") },
            block: { tone: "err", icon: "xCircle",
                     label: _t("Could not be sent in") },
        }[level];
    }

    /** The fix buttons on an issue actually act — none of them is a label. */
    async applyFix(fix) {
        if (fix.act === "assign") {
            const [roleKey, scopeKey] = String(fix.arg || "").split("|");
            if (this.props.onOpenPeople) {
                this.props.onOpenPeople(roleKey, scopeKey || "");
            }
            return;
        }
        if (fix.act === "independence_off") {
            await this.setIndependent(false);
            this.notif.add(
                _t("The independence rule is off for this route. The same person may prepare and approve. You confirm this when you publish."),
                { type: "warning" });
            return;
        }
        if (fix.act === "use_backup") {
            this.notif.add(
                _t("On a real request this is a move to somebody else, recorded with a reason. The example shows who that would be."),
                { type: "info" });
            return;
        }
        if (this.props.onOpenPeople) { this.props.onOpenPeople("", ""); }
    }

    // -------------------------------------------------------- whole coverage
    async checkCoverage() {
        this.state.coverageBusy = true;
        try {
            this.state.coverage = await this.orm.call(
                "pb.approval.matrix", "check_coverage",
                [this.state.data.draft.version_id]);
            const gaps = this.state.coverage.gaps;
            this.notif.add(
                gaps
                    ? _t("%s place(s) need somebody named before this can be used.", gaps)
                    : _t("Every part of the business has a full route."),
                { type: gaps ? "warning" : "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("The coverage check could not run."),
                { type: "danger" });
        } finally {
            this.state.coverageBusy = false;
        }
    }

    // ========================================================= the publish
    async goto(step) {
        this.state.step = step;
        this.state.addMenu = false;
        if (step === 4) { await this.loadPublication(); }
    }

    async loadPublication() {
        try {
            this.state.publication = await this.orm.call(
                "pb.approval.matrix", "publication_preview",
                [this.state.data.draft.version_id]);
            this.state.confirmed = {};
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("This could not be checked over."),
                { type: "danger" });
        }
    }

    toggleConfirm(code) {
        this.state.confirmed[code] = !this.state.confirmed[code];
    }

    get outstanding() {
        const warnings = (this.state.publication || {}).warnings || [];
        return warnings.filter((one) => !this.state.confirmed[one.code]);
    }

    get canPublish() {
        const publication = this.state.publication;
        if (!publication || !publication.can_publish) { return false; }
        if ((publication.errors || []).length) { return false; }
        return this.outstanding.length === 0;
    }

    /**
     * What happens to the requests that were already in flight.
     *
     * ONE STRING WITH A PLACEHOLDER, not a sentence built around an
     * interpolation in the template. A template that writes "The" before a
     * number and the rest of the clause after it hands the translator the
     * word "The" on its own, which cannot be translated and cannot be
     * reordered into a language that puts the count somewhere else.
     */
    get publishedNote() {
        const count = (this.state.published || {}).in_progress || 0;
        return _t(
            "The %s already under way keep the people and steps they were given.",
            count);
    }

    async publish() {
        const publication = this.state.publication || {};
        try {
            this.state.published = await this.orm.call(
                "pb.approval.matrix", "publish",
                [this.state.data.draft.version_id,
                 this.state.data.draft.draft_revision,
                 this.state.publishAt || false,
                 this.state.reason,
                 (publication.warnings || []).map((one) => one.code)]);
            this.notif.add(
                _t("Published. New requests follow this route from now on."),
                { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("This could not be published."),
                { type: "danger" });
        }
    }

    // =========================================================== the picker
    openPicker(key) {
        const step = this.steps.find((one) => one.key === key);
        if (!step) { return; }
        this.state.picker = { key, title: step.title, who: copy(step.who) };
    }

    closePicker() { this.state.picker = null; }

    /**
     * What this step would resolve to right now, for the drawer's preview.
     *
     * The BUILDER already has the answer for the step as it stands, so a
     * change of mode is answered from the example that is already on screen
     * rather than by a round trip per click; a mode the example has nothing to
     * say about answers honestly with nothing rather than with a guess.
     */
    resolveFor(who) {
        const current = this.previewOf((this.state.picker || {}).key);
        const step = this.steps.find(
            (one) => one.key === (this.state.picker || {}).key);
        if (!step || !current) { return null; }
        if (JSON.stringify(who) === JSON.stringify(step.who)) { return current; }
        return null;
    }

    async savePicker(who) {
        const key = this.state.picker.key;
        this.state.picker = null;
        await this.edit(() => {
            const step = this.steps.find((one) => one.key === key);
            step.who = who;
            const many = (who.user_ids || []).length > 1;
            if (who.mode === "people" && many) {
                step.kind = who.all ? "joint" : "any";
            } else if (who.mode === "team") {
                step.kind = "any";
            } else if (["joint", "any"].includes(step.kind)) {
                step.kind = "approve";
            }
        });
    }

    openPeopleFromPicker(roleKey, scopeKey) {
        this.state.picker = null;
        if (this.props.onOpenPeople) {
            this.props.onOpenPeople(roleKey, scopeKey);
        }
    }
}
