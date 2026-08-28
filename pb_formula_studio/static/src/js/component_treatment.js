/** @odoo-module **/
/**
 * How each component is treated — one board, one home.
 *
 * VALUEKIND P5. This board was born inside the Source Atlas, which is reached
 * from a pay run, and that was the wrong home for it. What it edits is a
 * property of the SCHEME: change a pay role while standing in June's run and
 * you have changed July, August and every run already computed. A surface whose
 * effects outlive the thing you are standing in does not belong inside it.
 *
 * So it lives here, beside the other scheme-wide boards under Mappings, and the
 * Atlas renders the same component with `readonly` — because the run is where
 * you NOTICE something is wrong, and this is where you fix it. Look there, fix
 * here. One implementation, so the two can never drift apart.
 *
 * Reads and writes `hr.formula.config`: the type of a value is a property of
 * the pay COMPONENT, so the model that owns the component owns the write. That
 * is also why one board covers a spreadsheet column, an API wire, a contract
 * field and a computed column alike — none of them holds the type.
 */
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const LANE_LABELS = {
    feed: _t("Connected system"),
    excel: _t("Spreadsheet"),
    contract_component: _t("Contract"),
    formula: _t("Computed here"),
    record: _t("Employee record"),
    constant: _t("Fixed value"),
};

export class ComponentTreatmentBoard extends Component {
    static template = "pb_formula_studio.ComponentTreatmentBoard";
    static props = {
        configId: { type: [Number, Boolean], optional: true },
        runId: { type: [Number, Boolean], optional: true },
        readonly: { type: Boolean, optional: true },
        // The Atlas passes this so its read-only copy can send the reader here.
        onEdit: { type: Function, optional: true },
        // The Mapping shell's header counts what the board holds; only the
        // board knows, and only after it has read.
        onLoaded: { type: Function, optional: true },
        // `true` when the HOST page scrolls and this board should simply flow
        // to its full height (the Source Atlas). Left false, the board takes
        // the height its frame gives it and scrolls its own rows (Mappings).
        // Named for the layout rather than inferred from `readonly`, so a third
        // host cannot inherit the wrong one by accident: an `overflow: auto`
        // that never scrolls still becomes the sticky header's container, and
        // the header then pins itself to a box that is off screen.
        flow: { type: Boolean, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { readonly: false, flow: false };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            board: null,
            loading: false,
            saving: false,
            fixing: false,
            dirty: {},
            filter: "",
            error: "",
        });
        onWillStart(() => this.load());
        onWillUpdateProps((next) => {
            if (next.configId !== this.props.configId || next.runId !== this.props.runId) {
                this.load(next);
            }
        });
    }

    async load(props = this.props) {
        if (!props.configId) {
            this.state.board = null;
            this.state.error = _t("No scheme to read components from.");
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.board = await this.orm.call(
                "hr.formula.config", "value_kind_board",
                [[props.configId], props.runId || null]
            );
            this.state.dirty = {};
            if (props.onLoaded) {
                props.onLoaded((this.state.board.rows || []).length);
            }
        } catch (error) {
            this.state.error =
                error?.data?.message || error?.message || _t("Could not read the components.");
        }
        this.state.loading = false;
    }

    laneLabel(lane) {
        return LANE_LABELS[lane] || lane || _t("Elsewhere");
    }

    /**
     * Read-only cells show the WORDS, never the stored key. A row reading
     * "identifier" where the editable board reads "Reference code" is the same
     * screen speaking two languages.
     */
    labelOf(list, value) {
        const hit = (this.state.board?.[list] || []).find((o) => o.value === value);
        return hit ? hit.label : (value || "\u2014");
    }

    roleLabel(row) {
        return this.labelOf("pay_roles", this.valueOf(row, "pay_role"));
    }

    kindLabel(row) {
        return this.labelOf("options", this.valueOf(row, "kind"));
    }

    signalLabel(row) {
        return this.labelOf("signals", this.valueOf(row, "signal"));
    }

    get rows() {
        const rows = this.state.board?.rows || [];
        if (this.state.filter === "drift") {
            return rows.filter((r) => r.drift);
        }
        if (this.state.filter === "review") {
            return rows.filter((r) => r.needs_review);
        }
        if (this.state.filter === "conflict") {
            return rows.filter((r) => r.role_conflict);
        }
        return rows;
    }

    setFilter(which) {
        this.state.filter = this.state.filter === which ? "" : which;
    }

    get dirtyCount() {
        return Object.keys(this.state.dirty).length;
    }

    /**
     * The axes are edited together, so a pending change is a PATCH per
     * component rather than a single value: a person who moves a component to
     * a new group and then corrects its pay role has made one change to one
     * row, and one Save should carry both.
     */
    patchOf(row) {
        return this.state.dirty[row.code] || {};
    }

    valueOf(row, field) {
        const patch = this.patchOf(row);
        return field in patch ? patch[field] : row[field];
    }

    /**
     * VALUEKIND P5 — the value type gates the pay role, and it has to gate it
     * against the type being chosen RIGHT NOW rather than the one on the
     * record. Otherwise switching a row to "Quantity (hours, days)" leaves
     * "Adds to net pay" selectable until the save comes back refusing it.
     */
    moneyAllowed(row) {
        const kind = this.valueOf(row, "kind");
        const opt = (this.state.board?.options || []).find((o) => o.value === kind);
        return opt ? opt.money : true;
    }

    /**
     * The role a row ALREADY holds stays in its own list even when the value
     * type forbids it. Dropping it made the cell read "— not set —" over a
     * component the database says is an earning: the screen would be denying
     * the very state the banner above it is asking about. It is offered, it is
     * flagged amber, and no OTHER money role can be chosen — once the reader
     * moves off it, it is gone.
     */
    roleOptions(row) {
        const allowed = this.moneyAllowed(row);
        const current = this.valueOf(row, "pay_role");
        return (this.state.board?.pay_roles || []).filter(
            (pr) => allowed || !pr.money || pr.value === current);
    }

    onChange(row, field, ev) {
        const target = ev.target;
        const chosen = target.type === "checkbox" ? target.checked : target.value;
        const patch = { ...this.patchOf(row) };
        if (chosen === row[field]) {
            delete patch[field];
        } else {
            patch[field] = chosen;
        }
        // Choosing a non-money type retires a money role in the same keystroke,
        // so the row is never left saying two things that cannot both be true.
        if (field === "kind") {
            const role = "pay_role" in patch ? patch.pay_role : row.pay_role;
            if (role && !this.moneyAllowedFor(chosen) && role !== "info") {
                patch.pay_role = "info";
            }
        }
        if (Object.keys(patch).length) {
            this.state.dirty[row.code] = patch;
        } else {
            delete this.state.dirty[row.code];
        }
    }

    moneyAllowedFor(kind) {
        const opt = (this.state.board?.options || []).find((o) => o.value === kind);
        return opt ? opt.money : true;
    }

    async save() {
        if (!this.dirtyCount || this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const res = await this.orm.call(
                "hr.formula.config", "set_component_setup",
                [[this.state.board.config_id], { ...this.state.dirty }]
            );
            this.notif.add(res.note, { type: "success" });
            await this.load();
        } catch (error) {
            this.notif.add(
                error?.data?.message || error?.message || _t("Could not save."),
                { type: "danger" }
            );
        }
        this.state.saving = false;
    }

    /** The one action behind the conflict banner. */
    async fixConflicts() {
        if (this.state.fixing) {
            return;
        }
        this.state.fixing = true;
        try {
            const fixed = await this.orm.call(
                "hr.formula.config", "fix_role_conflicts", [[this.state.board.config_id]]
            );
            this.notif.add(
                _t("%s component(s) set to Information only.", fixed.length),
                { type: "success" }
            );
            await this.load();
        } catch (error) {
            this.notif.add(
                error?.data?.message || error?.message || _t("Could not change them."),
                { type: "danger" }
            );
        }
        this.state.fixing = false;
    }

    async reset(row) {
        try {
            await this.orm.call("hr.formula.config", "reset_value_kind",
                                [[this.state.board.config_id], [row.code]]);
            delete this.state.dirty[row.code];
            await this.load();
        } catch (error) {
            this.notif.add(
                error?.data?.message || error?.message || _t("Could not reset."),
                { type: "danger" }
            );
        }
    }
}
