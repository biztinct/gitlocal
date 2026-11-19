/** @odoo-module **/
/**
 * Contracts board › Table (FS-4) — from outside, by `patch` + `t-inherit`.
 *
 * Same rows, filters, views, steps, sort and "Show more" as the cards; a row
 * opens the same contract panel. On the "To check" view the table keeps the
 * review bar and each row keeps its two answers ("Change", "Looks right").
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbContracts } from "@pb_contracts/js/contracts";
import { PbListTable, PbTableTools, fmtDate, useListColumns } from "@pb_filter_kit/js/list_table";
import { TONE, soonChip, withTableFlag } from "@pb_form_studio_lists/js/table_flag";

patch(PbContracts, {
    components: { ...PbContracts.components, PbListTable, PbTableTools },
});

patch(PbContracts.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbfl = useListColumns({
            model: "pb.contracts",
            kit: this.kit,
            onMode: () => this.loadPage(),
        });
        this.orm = withTableFlag(this.orm, "get_contracts_page", () => this.pbfl.table);
    },

    pbflCell(c, col) {
        switch (col.key) {
            case "state":
                return { text: c.state_label, pill: true, tone: TONE[this.stateCls(c.state)] || "slate" };
            case "date_end": {
                const chip = c.state === "open" ? soonChip(c.days_to_expiry) : null;
                return { text: c.date_end ? fmtDate(c.date_end) : _t("No end date"), chip, chipTone: "amber",
                         chipIcon: chip ? "alert" : "", chipTitle: chip ? _t("Ends within 30 days") : "" };
            }
            case "wage":
                return { text: c.wage ? this.money(c.wage, c.currency) : "" };
            case "fillin": {
                const n = this.fillinCount(c);
                return n ? { text: "", chip: this.fillinChip(c), chipTone: "amber", chipIcon: "sparkles",
                             chipTitle: _t("Payobook filled these in from the scheme's usual answers. Open the contract to check or change them.") }
                    : { text: "" };
            }
            default:
                return null;
        }
    },
    pbflOpen(c) {
        this.openContract(c.id);
    },
});
