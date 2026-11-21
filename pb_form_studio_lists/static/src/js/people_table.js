/** @odoo-module **/
/**
 * People list › Table (FS-4) — from outside, by `patch` + `t-inherit`
 * (precedent `pb_agency_staff/static/src/js/agency_staff_patches.js`).
 *
 * The cards stay the default and stay exactly as they are. The table is the
 * same rows (the board's own page call, filters, views, sort and "Show more"),
 * the same click (the side panel, or a tick in select mode) and the same bulk
 * bar; it only draws them as columns the person chooses.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbPeople } from "@pb_people/js/people";
import { PbListTable, PbTableTools, fmtDate, useListColumns } from "@pb_filter_kit/js/list_table";
import { TONE, soonChip, withTableFlag } from "@pb_form_studio_lists/js/table_flag";

patch(PbPeople, {
    components: { ...PbPeople.components, PbListTable, PbTableTools },
});

patch(PbPeople.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbfl = useListColumns({
            model: "pb.people",
            kit: this.kit,
            // a switch to the table needs the page again with its custom cells
            onMode: () => this.loadPage(),
        });
        this.orm = withTableFlag(this.orm, "get_roster_page", () => this.pbfl.table);
    },

    /** Cells the table draws the card's way (badge colour, expiry chip, ready). */
    pbflCell(p, c) {
        switch (c.key) {
            case "state":
                return { text: p.state_label, pill: true, tone: TONE[this.stateCls(p.state)] || "slate" };
            case "date_end": {
                const chip = p.state === "open" ? soonChip(p.days_to_expiry) : null;
                return { text: fmtDate(p.date_end), chip, chipTone: "amber", chipIcon: chip ? "alert" : "",
                         chipTitle: chip ? _t("Ends within 30 days") : "" };
            }
            case "wage":
                return { text: p.wage ? this.money(p.wage, p.currency) : "" };
            case "ready":
                return p.ready
                    ? { text: _t("Ready"), icon: "checkCircle", tone: "green", title: _t("Payroll ready") }
                    : { text: p.bank ? _t("No running contract") : _t("No bank details"),
                        icon: "alert", tone: "amber" };
            case "job":
                return { text: p.job && p.job !== "—" ? p.job : "" };
            default:
                return null;
        }
    },
    /** The table's header tick: everyone shown, or nobody. */
    pbflToggleAll(on) {
        this.state.selected = on ? this.filteredPeople.map((p) => p.id) : [];
    },
});
