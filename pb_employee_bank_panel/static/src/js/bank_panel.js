/** @odoo-module **/
/**
 * FS-9 — the Bank block on the employee side panel (Pay & tax).
 *
 * By `patch()` and template inheritance only (no edit of pb_employee_vault or
 * pb_pay_delivery; precedent `pb_form_studio_people/static/src/js/
 * people_form_patches.js`). The server sends the block inside the panel's
 * own payload (`details.pay`, the group of kind "pb_bank"); this file draws
 * it, opens the waiting change, and runs BL4's existing "Mark as seen".
 *
 * The header chip "This bank account is in another person's name"
 * (pb_pay_delivery) and this block show the same notice: whichever is
 * pressed, the other follows through the bus (`PB_OTHER_NAME_SEEN`), so the
 * panel never says two different things.
 */
import { markup, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { PbOtherNameChip } from "@pb_pay_delivery/js/other_name_chip";

const PEOPLE = "pb.people";
const SEEN = "PB_OTHER_NAME_SEEN";
const INBOX = "pb_approval_config.action_pb_approval_inbox";
const BANK_CHECKS = "pb_bank_ocr.action_pb_bank_ocr";

// Lucide (ISC) paths — never a glyph font, never an emoji.
const PATHS = {
    landmark: '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    circleDashed: '<path d="M10.1 2.182a10 10 0 0 1 3.8 0"/><path d="M13.9 21.818a10 10 0 0 1-3.8 0"/><path d="M17.609 3.721a10 10 0 0 1 2.69 2.7"/><path d="M2.182 13.9a10 10 0 0 1 0-3.8"/><path d="M20.279 17.609a10 10 0 0 1-2.7 2.69"/><path d="M21.818 10.1a10 10 0 0 1 0 3.8"/><path d="M3.721 6.391a10 10 0 0 1 2.7-2.69"/><path d="M6.391 20.279a10 10 0 0 1-2.69-2.7"/>',
    userX: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="17" x2="22" y1="8" y2="13"/><line x1="22" x2="17" y1="8" y2="13"/>',
    eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    arrowUpRight: '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    creditCard: '<rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/>',
};
// One markup object per icon and size: a NEW markup() on every paint
// re-inserts the DOM (ledger: OWL markup flicker).
const CACHE = {};
export function bkIc(name, size = 15) {
    const key = name + ":" + size;
    if (!CACHE[key]) {
        CACHE[key] = markup(
            `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
            `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">` +
            `${PATHS[name] || PATHS.info}</svg>`);
    }
    return CACHE[key];
}

export const STATUS_ICON = { approved: "shieldCheck", waiting: "clock", none: "circleDashed" };

function msgOf(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback;
}

// ===================================================================
//  The side panel
// ===================================================================
patch(Employee360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbBank = useState({ busy: false });
        // the header chip was pressed: the block follows
        useBus(this.env.bus, SEEN, (ev) => {
            const detail = (ev && ev.detail) || {};
            if (detail.from !== "panel" && Number(detail.empId) === Number(this.props.empId)) {
                this.pbBankRefresh();
            }
        });
    },

    bkIc(name, size) { return bkIc(name, size); },
    bkStatusIcon(block) { return bkIc(STATUS_ICON[block.status] || "info", 13); },

    /** The panel's Bank group (kind "pb_bank") on the Pay & tax tab. */
    _pbBankGroup() {
        return this.groups("pay").find((g) => g.kind === "pb_bank") || null;
    },

    async pbBankRefresh() {
        const group = this._pbBankGroup();
        if (!group) { return; }
        try {
            const block = await this.orm.call(PEOPLE, "pb_bank_panel", [Number(this.props.empId)]);
            if (block && !block.error) { group.pb_bank = block; }
        } catch {
            // the block keeps what it showed; the next open reads it again
        }
    },

    async pbBankMarkSeen() {
        if (this.pbBank.busy) { return; }
        this.pbBank.busy = true;
        try {
            await this.orm.call("hr.employee", "pb_other_name_mark_seen", [Number(this.props.empId)]);
            this.env.bus.trigger(SEEN, { empId: Number(this.props.empId), from: "panel" });
            await this.pbBankRefresh();
        } catch (e) {
            this.notif.add(msgOf(e, _t("This could not be marked as seen.")), { type: "danger" });
        } finally {
            this.pbBank.busy = false;
        }
    },

    pbBankOpenWaiting(link) {
        if (!link) { return; }
        this.close();
        if (link.kind === "inbox") {
            this.action.doAction(INBOX, { additionalContext: { pb_focus: link.focus } });
        } else {
            this.action.doAction(BANK_CHECKS);
        }
    },

    pbBankOpenChecks() {
        this.close();
        this.action.doAction(BANK_CHECKS);
    },

    pbBankSeenLine(other) {
        if (other.seen_by && other.seen_on) {
            return _t("Marked as seen by %(who)s on %(date)s. Payment is not changed by this.",
                      { who: other.seen_by, date: other.seen_on });
        }
        return _t("Marked as seen. Payment is not changed by this.");
    },
});

// ===================================================================
//  The header chip follows the block (and tells it when it is pressed)
// ===================================================================
patch(PbOtherNameChip.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, SEEN, (ev) => {
            const detail = (ev && ev.detail) || {};
            if (detail.from === "panel" && Number(detail.empId) === Number(this.props.empId)) {
                this.state.show = false;
            }
        });
    },
    async markSeen() {
        await super.markSeen(...arguments);
        if (!this.state.show) {
            this.env.bus.trigger(SEEN, { empId: Number(this.props.empId), from: "chip" });
        }
    },
});
