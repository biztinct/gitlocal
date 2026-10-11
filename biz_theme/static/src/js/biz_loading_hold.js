/** @odoo-module **/
// Part of biz_theme — reusable Odoo 19 backend theme. License LGPL-3.
// =============================================================================
// The loading indicator holds for one beat between two bursts of requests.
// -----------------------------------------------------------------------------
// Opening a screen is two bursts: the web client's own reads, then — a few
// milliseconds after the last of those answers — the screen's reads. The stock
// indicator hides the moment nothing is pending and shows again 250ms into
// the second burst, so every screen looked as if it loaded twice. Here the
// indicator stays up for a short grace period after the last answer; a request
// that starts inside that period keeps it up without the 250ms rearm, so the
// two bursts read as the one load they are.
//
// It also gives the top line its finish: when the indicator finally hides,
// `body.biz-load-done` stays for half a second so the line (scss/biz_loading.scss)
// can run to the edge and fade instead of vanishing mid-way.
// (Same mechanism as the health19 build's loading_indicator_hold.js.)
// =============================================================================

import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";
import { LoadingIndicator } from "@web/webclient/loading_indicator/loading_indicator";

export const HOLD_MS = 350;
export const DONE_CLASS = "biz-load-done";
const DONE_MS = 500;
let doneTimer = null;

function markDone() {
    browser.clearTimeout(doneTimer);
    document.body.classList.add(DONE_CLASS);
    doneTimer = browser.setTimeout(() => {
        document.body.classList.remove(DONE_CLASS);
    }, DONE_MS);
}

patch(LoadingIndicator.prototype, {
    requestCall(ev) {
        const { detail } = ev;
        if (!detail.settings.silent) {
            browser.clearTimeout(doneTimer);
            document.body.classList.remove(DONE_CLASS);
        }
        if (!detail.settings.silent && this.hideTimer) {
            // still shown from the previous burst: keep it, no rearm
            browser.clearTimeout(this.hideTimer);
            this.hideTimer = null;
            this.rpcIds.add(detail.data.id);
            this.state.count++;
            return;
        }
        return super.requestCall(ev);
    },

    responseCall(ev) {
        const { detail } = ev;
        if (detail.settings.silent) {
            return;
        }
        this.rpcIds.delete(detail.data.id);
        this.state.count = this.rpcIds.size;
        if (this.state.count !== 0) {
            return;
        }
        browser.clearTimeout(this.startShowTimer);
        if (!this.state.show) {
            return;
        }
        browser.clearTimeout(this.hideTimer);
        this.hideTimer = browser.setTimeout(() => {
            this.hideTimer = null;
            if (this.state.count === 0) {
                this.state.show = false;
                markDone();
            }
        }, HOLD_MS);
    },
});
