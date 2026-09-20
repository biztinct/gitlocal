/** @odoo-module **/
/**
 * "Who should decide this step?" — the one drawer that answers it.
 *
 * FIVE WAYS TO FIND A PERSON, and they are genuinely different questions, not
 * five spellings of one:
 *
 *   their manager / their manager's manager  — the request is ABOUT somebody,
 *       so the right approver is worked out from that person's own record.
 *   a responsibility                          — the right approver depends on
 *       WHERE the request comes from, and is named once in People & backups
 *       rather than again in every workflow.
 *   named people                              — a fixed signatory list, which
 *       is what a bank mandate actually is.
 *   one of a team                             — whoever is free first.
 *
 * THE PANEL AT THE BOTTOM IS THE POINT. Every choice above is abstract until
 * it says a NAME, so the drawer runs the step against the example the builder
 * is already showing and prints the people it would really reach — including a
 * backup standing in, and including "nobody, and here is the door that mends
 * it". Choosing without seeing that is how a route gets published that cannot
 * resolve anywhere.
 *
 * NAMING SOMEBODY HERE GRANTS THEM NOTHING. A person who cannot yet open this
 * kind of request is still offered, still choosable, and carries the words
 * "Needs permission" plus what to do about it — because refusing the choice
 * would leave the reader with a puzzle and no way to finish the sentence.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { copy, initials, whoLabel } from "@pb_approval_config/js/sentence";

export class PickerDrawer extends Component {
    static template = "pb_approval_config.PickerDrawer";
    static props = {
        who: { type: Object },
        stepTitle: { type: String, optional: true },
        roles: { type: Array },
        companyId: { type: Number },
        processKey: { type: String, optional: true },
        /** The resolved people for the example, for the preview panel. */
        resolve: { type: Function },
        onSave: { type: Function },
        onClose: { type: Function },
        onAssign: { type: Function, optional: true },
    };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.orm = useService("orm");

        this.state = useState({
            who: copy(this.props.who),
            people: [],
            search: "",
            loading: false,
            held: [],
            preview: null,
        });

        onWillStart(async () => {
            await this.loadPeople();
            await this.loadHeld();
            this.refreshPreview();
        });
    }

    // ------------------------------------------------------------ the modes
    get modes() {
        return [
            { key: "manager", icon: "user", title: _t("Their manager"),
              sub: _t("Best when the request is about one person.") },
            { key: "skip", icon: "users", title: _t("Their manager's manager"),
              sub: _t("For the bigger asks.") },
            { key: "role", icon: "briefcase",
              title: _t("Somebody's responsibility"),
              sub: _t("Best for whole batches — the right person per part of the business.") },
            { key: "people", icon: "userCheck", title: _t("Named people"),
              sub: _t("A fixed list, such as who may sign at the bank.") },
            { key: "team", icon: "inbox", title: _t("One of a team"),
              sub: _t("Whoever gets to it first decides.") },
        ];
    }

    get role() {
        return this.props.roles.find((r) => r.key === this.state.who.role)
            || this.props.roles[0] || {};
    }

    get chosenIds() {
        return this.state.who.user_ids || [];
    }

    get label() {
        const roles = {};
        for (const role of this.props.roles) { roles[role.key] = role.name; }
        const names = {};
        for (const person of this.state.people) { names[person.id] = person.name; }
        return whoLabel(this.state.who, roles, names);
    }

    get canSave() {
        const who = this.state.who;
        if (who.mode === "people") { return this.chosenIds.length > 0; }
        if (who.mode === "team") { return this.chosenIds.length > 0; }
        if (who.mode === "role") { return Boolean(who.role); }
        return true;
    }

    get filtered() {
        const term = this.state.search.trim().toLowerCase();
        if (!term) { return this.state.people; }
        return this.state.people.filter(
            (person) => person.name.toLowerCase().includes(term)
                || String(person.title || "").toLowerCase().includes(term));
    }

    // -------------------------------------------------------------- reading
    async loadPeople() {
        this.state.loading = true;
        try {
            this.state.people = await this.orm.call(
                "pb.approval.matrix", "user_options",
                [this.state.search, this.state.who.role, this.props.companyId,
                 this.props.processKey || false]);
        } finally {
            this.state.loading = false;
        }
    }

    async loadHeld() {
        if (this.state.who.mode !== "role") { this.state.held = []; return; }
        const grid = await this.orm.call(
            "pb.approval.matrix", "get_people", [this.props.companyId]);
        const row = (grid.roles || []).find(
            (r) => r.key === this.state.who.role);
        this.state.held = row ? row.cells : [];
    }

    refreshPreview() {
        this.state.preview = this.props.resolve(copy(this.state.who));
    }

    // -------------------------------------------------------------- writing
    async setMode(mode) {
        const who = this.state.who;
        who.mode = mode;
        if (mode === "role" && !who.role) {
            who.role = (this.props.roles[0] || {}).key || "";
            who.scope = "area";
        }
        if ((mode === "people" || mode === "team") && !who.user_ids) {
            who.user_ids = [];
            who.all = mode === "people";
        }
        if (mode === "team" && !who.label) {
            who.label = _t("The desk");
        }
        if (mode === "role") { await this.loadHeld(); }
        this.refreshPreview();
    }

    async setRole(ev) {
        this.state.who.role = ev.target.value;
        await this.loadHeld();
        this.refreshPreview();
    }

    setScope(ev) {
        this.state.who.scope = ev.target.value;
        this.refreshPreview();
    }

    setTeamName(ev) {
        this.state.who.label = ev.target.value;
    }

    togglePerson(id) {
        const ids = this.state.who.user_ids || [];
        this.state.who.user_ids = ids.includes(id)
            ? ids.filter((one) => one !== id)
            : ids.concat(id);
        this.refreshPreview();
    }

    setAll(all) {
        this.state.who.all = all;
        this.refreshPreview();
    }

    async onSearch(ev) {
        this.state.search = ev.target.value;
        await this.loadPeople();
    }

    assign(cell) {
        if (this.props.onAssign) {
            this.props.onAssign(this.state.who.role, cell.scope_key);
        }
    }

    save() {
        this.props.onSave(copy(this.state.who));
    }
}
