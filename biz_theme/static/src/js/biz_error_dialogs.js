/** @odoo-module **/
/**
 * biz_theme — friendly error-dialog family.
 *
 * Replaces the stock WarningDialog / Error504Dialog / SessionExpiredDialog for
 * the well-known exception types via the "error_dialogs" registry
 * ({force: true} — no core patch). One component, six calm variants:
 *
 *   access    — AccessError / AccessDenied  (role chips parsed from message)
 *   attention — UserError / ValidationError (user-actionable message)
 *   missing   — MissingError / MissingActionError
 *   timeout   — 504 / interrupted operation
 *   session   — SessionExpiredException / Forbidden (sign-in again)
 *   crash     — fallback for anything else routed here
 *
 * Uncaught traceback dialogs (web.ErrorDialog / RPCErrorDialog) are restyled
 * by biz_error_dialogs.scss — the stack stays behind "technical details".
 */

import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardErrorDialogProps } from "@web/core/errors/error_dialogs";
import { Component, useState } from "@odoo/owl";

const VARIANTS = {
    access: {
        icon: "shield",
        title: _t("You don't have access to this yet"),
        hint: _t("This area is limited to certain roles. If you need it for your work, ask your administrator to extend your access."),
    },
    attention: {
        icon: "alert",
        title: _t("Something needs your attention"),
        hint: "",
    },
    missing: {
        icon: "ghost",
        title: _t("This record no longer exists"),
        hint: _t("It may have been deleted or merged by someone else. Refresh to see the latest data."),
    },
    timeout: {
        icon: "clock",
        title: _t("This is taking longer than expected"),
        hint: _t("The operation was interrupted because it ran too long. It may still finish in the background — wait a moment, then check before retrying."),
    },
    session: {
        icon: "moon",
        title: _t("Your session ended"),
        hint: _t("You were signed out, probably after a period of inactivity. Sign in again to pick up where you left off."),
    },
    crash: {
        icon: "wrench",
        title: _t("Something went wrong on our side"),
        hint: _t("This wasn't you. Try again — if it keeps happening, copy the details and share them with support."),
    },
};

const EXCEPTION_VARIANT = {
    "odoo.exceptions.AccessDenied": "access",
    "odoo.exceptions.AccessError": "access",
    "odoo.exceptions.UserError": "attention",
    "odoo.exceptions.ValidationError": "attention",
    "odoo.addons.base.models.ir_actions.ServerActionWithWarningsError": "attention",
    "odoo.exceptions.MissingError": "missing",
    "odoo.addons.web.controllers.action.MissingActionError": "missing",
    "odoo.http.SessionExpiredException": "session",
    "werkzeug.exceptions.Forbidden": "session",
};

/** Pull "- Group Name" bullet lines out of an access-error message. */
export function parseAccessGroups(message) {
    const groups = [];
    for (const line of (message || "").split("\n")) {
        const m = /^\s*-\s+(.+?)\s*$/.exec(line);
        if (m && m[1].length <= 80) {
            groups.push(m[1]);
        }
    }
    return groups;
}

export class BizErrorDialog extends Component {
    static template = "biz_theme.BizErrorDialog";
    static components = { Dialog };
    static props = {
        ...standardErrorDialogProps,
        title: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ showDetails: false, copied: false });
        const { data, message } = this.props;
        this.message =
            (data && data.arguments && data.arguments.length && data.arguments[0]) ||
            message ||
            "";
        this.variant = this.inferVariant();
        this.meta = VARIANTS[this.variant];
        this.groups = this.variant === "access" ? parseAccessGroups(this.message) : [];
        // For access errors the raw message is server-speak; show it only in
        // the details section. Attention/missing variants surface it directly.
        this.bodyMessage = this.variant === "attention" ? this.message : "";
    }

    inferVariant() {
        if (this.props.exceptionName && EXCEPTION_VARIANT[this.props.exceptionName]) {
            return EXCEPTION_VARIANT[this.props.exceptionName];
        }
        if (String(this.props.code) === "504") {
            return "timeout";
        }
        return "crash";
    }

    get technicalDetails() {
        const parts = [
            this.props.name,
            this.message,
            this.props.exceptionName,
            this.props.traceback,
        ].filter(Boolean);
        return parts.join("\n\n");
    }

    get hasDetails() {
        // Session/timeout screens carry no useful payload for end users
        return this.variant !== "session" && !!(this.message || this.props.traceback);
    }

    toggleDetails() {
        this.state.showDetails = !this.state.showDetails;
    }

    copyDetails() {
        browser.navigator.clipboard.writeText(this.technicalDetails);
        this.state.copied = true;
        browser.setTimeout(() => {
            this.state.copied = false;
        }, 1400);
    }

    onPrimaryClick() {
        if (this.variant === "session" || this.variant === "missing") {
            browser.location.reload();
            return;
        }
        this.props.close();
    }

    get primaryLabel() {
        switch (this.variant) {
            case "session":
                return _t("Sign in again");
            case "missing":
                return _t("OK, refresh my view");
            case "access":
                return _t("OK, take me back");
            default:
                return _t("OK");
        }
    }
}

const errorDialogRegistry = registry.category("error_dialogs");
for (const exceptionName of Object.keys(EXCEPTION_VARIANT)) {
    errorDialogRegistry.add(exceptionName, BizErrorDialog, { force: true });
}
errorDialogRegistry.add("504", BizErrorDialog, { force: true });
