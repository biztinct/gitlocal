/** @odoo-module **/
/**
 * Records Desk: the fields somebody picked follow them to any device (FS-4).
 *
 * The desk keeps its chooser exactly as it is. Only where the choice is kept
 * moves: from this browser's storage (`pb_records.fields.<scheme>` /
 * `pb_records.column_order.<scheme>`) to the saved-view store
 * (`pb.filter.view`, list key `records.<scheme>`, "Just me"). The first time
 * a person opens a scheme with nothing stored yet, the old browser value is
 * read once and stored, so nobody loses their set-up. The browser copy is
 * still written as well, so a desk that cannot reach the store keeps working.
 *
 * Stored shape (the kit's column list): `[{key, on}]` in the grid's column
 * order — `on` marks a picked field; the desk's own identity columns are
 * kept with `on: false` so their place in the order survives too.
 */
import { patch } from "@web/core/utils/patch";
import { PbRecordsDesk } from "@pb_records/js/records_desk";

const SAVE_DELAY = 400;
const screenOf = (configId) => `records.${Number(configId) || 0}`;
const FIELDS_KEY = (configId) => `pb_records.fields.${configId}`;
const ORDER_KEY = (configId) => `pb_records.column_order.${configId}`;

function readLocal(configId) {
    try {
        const picked = JSON.parse(window.localStorage.getItem(FIELDS_KEY(configId)) || "[]");
        const order = JSON.parse(window.localStorage.getItem(ORDER_KEY(configId)) || "[]");
        return {
            picked: Array.isArray(picked) ? picked : [],
            order: Array.isArray(order) ? order : [],
        };
    } catch {
        return { picked: [], order: [] };
    }
}

/** {picked, order} → [{key, on}] */
export function encodeRecordsColumns(picked, order) {
    const pickedSet = new Set((picked || []).map(String));
    const out = [];
    const seen = new Set();
    for (const key of order || []) {
        if (!seen.has(String(key))) {
            seen.add(String(key));
            out.push({ key, on: pickedSet.has(String(key)) });
        }
    }
    for (const key of picked || []) {
        if (!seen.has(String(key))) {
            seen.add(String(key));
            out.push({ key, on: true });
        }
    }
    return out;
}

/** [{key, on}] → {picked, order} */
export function decodeRecordsColumns(cols) {
    const list = Array.isArray(cols) ? cols : [];
    return {
        picked: list.filter((c) => c && c.on).map((c) => c.key),
        order: list.filter((c) => c && c.key !== undefined).map((c) => c.key),
    };
}

patch(PbRecordsDesk.prototype, {
    setup() {
        super.setup(...arguments);
        this._pbflCols = {};
        this._pbflTimers = {};
    },

    async loadFields(preferred) {
        await this._pbflFetch(this.state.configId);
        return super.loadFields(...arguments);
    },

    async _pbflFetch(configId) {
        if (configId in this._pbflCols) {
            return;
        }
        let stored = null;
        try {
            const res = await this.orm.call("pb.filter.view", "pbf_columns_read", [screenOf(configId)]);
            stored = res && res.mine;
        } catch (e) {
            // the store is out of reach: the browser copy serves, as before
            console.warn("pb_form_studio_lists: Records Desk columns not read", e);
            return;
        }
        if (stored && stored.length) {
            this._pbflCols[configId] = decodeRecordsColumns(stored);
            return;
        }
        // one-time: bring the old browser set-up along
        const local = readLocal(configId);
        this._pbflCols[configId] = local;
        if (local.picked.length || local.order.length) {
            this._pbflPush(configId, local);
        }
    },

    _pbflPush(configId, value) {
        const columns = encodeRecordsColumns(value.picked, value.order);
        return this.orm.call("pb.filter.view", "pbf_columns_save", [screenOf(configId)], { columns })
            .catch((e) => console.warn("pb_form_studio_lists: Records Desk columns not saved", e));
    },

    restorePicked() {
        const c = this._pbflCols && this._pbflCols[this.state.configId];
        return c ? [...c.picked] : super.restorePicked(...arguments);
    },

    restoreOrder() {
        const c = this._pbflCols && this._pbflCols[this.state.configId];
        return c ? [...c.order] : super.restoreOrder(...arguments);
    },

    rememberPicked() {
        super.rememberPicked(...arguments);
        const configId = this.state.configId;
        const value = { picked: [...this.state.picked], order: [...(this.grid.columnOrder || [])] };
        this._pbflCols[configId] = value;
        clearTimeout(this._pbflTimers[configId]);
        this._pbflTimers[configId] = setTimeout(() => this._pbflPush(configId, value), SAVE_DELAY);
    },
});
