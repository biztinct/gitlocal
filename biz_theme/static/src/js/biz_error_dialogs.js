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
 *
 * Shipped into BOTH web.assets_backend and web.assets_frontend: portal, website
 * and login pages run the same error service and, without this file, fall back
 * to the stock dialog — which carries a vendor-branded title and an ungated
 * traceback expander. Every import below resolves to web/static/src/core/**,
 * which the frontend bundle already contains.
 */

import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { RPCError } from "@web/core/network/rpc";
import { UncaughtPromiseError } from "@web/core/errors/error_service";
import {
    standardErrorDialogProps,
    ErrorDialog as CoreErrorDialog,
    RPCErrorDialog,
    ClientErrorDialog,
    NetworkErrorDialog,
    WarningDialog,
    RedirectWarningDialog,
} from "@web/core/errors/error_dialogs";
import { Component, useState } from "@odoo/owl";

// ---------------------------------------------------------------------------
// Brand scrub. The server labels generic failures with its own vendor name in
// PLAIN (untranslated) literals — odoo/http.py, web/controllers/export.py,
// error_service.js's third-party-script traceback — and the core dialog classes
// re-mint them client-side ("Odoo Error", "Odoo Warning", "Odoo Server Error").
// None of those are reachable by a translation seam, so they are stripped at
// the component level here, language-independently. Brand-neutral by design so
// the reusable base stays portable.
//
// Declared ABOVE the dialog class because BizErrorDialog now sanitises on every
// path — not just in the two fallback handlers at the bottom of this file.
// ---------------------------------------------------------------------------
export const stripOdoo = (s) => (typeof s === "string" ? s.replace(/\bOdoo\s+/g, "").trim() : s);

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
        // No "copy the details" here: that button is now developer-mode only,
        // so promising it to an end user would be an instruction they cannot
        // follow.
        hint: _t("This wasn't you. Try again — if it keeps happening, let your administrator know so support can look into it."),
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

/**
 * Pull "- Group Name" bullets out of an access-error message — but only the
 * ones under an "allowed for the following groups:" marker. Other AccessError
 * formats also use bullets for MODEL names ("records of type:\n- Excel
 * Formula Configuration (hr.formula.config)"); those must never be presented
 * as roles.
 */
export function parseAccessGroups(message) {
    const groups = [];
    let inGroupList = false;
    for (const line of (message || "").split("\n")) {
        if (/groups\s*:\s*$/i.test(line.trim())) {
            inGroupList = true;
            continue;
        }
        const m = /^\s*-\s+(.+?)\s*$/.exec(line);
        if (m && inGroupList) {
            if (m[1].length <= 80) {
                groups.push(m[1]);
            }
        } else if (line.trim()) {
            inGroupList = false;
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
        // Sanitise HERE, not in the handlers: the registry-routed path (every
        // named exception in EXCEPTION_VARIANT, which is how a plain UserError
        // arrives) never passes through bizRpcFallbackHandler/bizDefaultHandler,
        // so a message carrying the vendor name used to reach the user raw.
        this.message = stripOdoo(
            (data && data.arguments && data.arguments.length && data.arguments[0]) ||
                message ||
                ""
        );
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
        // `traceback` is where error_service parks its untranslated
        // "…cannot be accessed by the Odoo framework…" sentence for a
        // third-party script error; scrub every part, not just the message.
        const parts = [
            stripOdoo(this.props.name),
            this.message,
            this.props.exceptionName,
            stripOdoo(this.props.traceback),
        ].filter(Boolean);
        return parts.join("\n\n");
    }

    get hasDetails() {
        // Session/timeout screens carry no useful payload for end users
        return this.variant !== "session" && !!(this.message || this.props.traceback);
    }

    get showTechnicalDetails() {
        // Raw payloads are never surfaced to end users — not on screen and not
        // via the clipboard ("Copy details" is gated on THIS getter too, not on
        // hasDetails). Developers keep the expander in debug mode.
        return this.hasDetails && Boolean(window.odoo && window.odoo.debug);
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

// ---------------------------------------------------------------------------
// Generic (unnamed) error dialogs. An uncaught server/client/network traceback
// that matches no named exception above falls through to Odoo's core
// ErrorDialog family, whose titles are the literal English SOURCE strings
// "Odoo Error / Odoo Server Error / Odoo Client Error / Odoo Network Error".
// web_debranding cannot reach these — source-language terms aren't in the
// translation catalog, so `_t()` returns them verbatim. `stripOdoo` (top of
// file) cleans them at the component level, language-independently.
// ---------------------------------------------------------------------------

// The template renders the INSTANCE `this.title` (the static class titles are
// getters we can't reassign). Normalize it in setup — covers the static
// fallback (ErrorDialog "Odoo Error", Client/Network) for typeless errors...
patch(CoreErrorDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.title = stripOdoo(this.title ?? this.constructor.title);
    },
});

// ...and RPCErrorDialog.inferTitle() sets a DYNAMIC title from the error type
// (_t("Odoo Server Error") for a 500, "Odoo Client Error" for a script error,
// etc.) AFTER super.setup() — so strip it right after it runs too.
patch(RPCErrorDialog.prototype, {
    inferTitle() {
        super.inferTitle(...arguments);
        this.title = stripOdoo(this.title);
    },
});

// ...and WarningDialog, which the registry no longer routes to (BizErrorDialog
// took its exception names over with {force: true}) but which is still
// instantiated DIRECTLY, bypassing the registry entirely, at
// web/static/src/model/relational_model/relational_model.js — with no `title`
// prop, so inferTitle() falls through to the literal "Odoo Warning".
patch(WarningDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.title = stripOdoo(this.title);
        this.message = stripOdoo(this.message);
    },
});

// ...and RedirectWarningDialog, which is NOT taken over: it carries an extra
// action button (`onClick` → action service) that BizErrorDialog has no slot
// for, and on the frontend bundle there is no action service to give it. Left
// registered, title/message scrubbed. Its template shows no traceback, so
// there is nothing technical to suppress.
patch(RedirectWarningDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.title = stripOdoo(this.title);
        this.message = stripOdoo(this.message);
    },
});

// ---------------------------------------------------------------------------
// Fallback routing — an UNMAPPED crash must not dump a traceback at the user.
//
// The registry above only covers exceptions we named. Anything else — a bare
// KeyError from a missing model, an Owl lifecycle error — falls through to
// core's RPCErrorDialog/ErrorDialog, whose template is the "Oops! Something
// went wrong... share the report with your friendly support service" panel
// with the full Python stack and server file paths in it. These two handlers
// send those cases to BizErrorDialog instead, which keeps the raw payload
// behind debug mode and offers "Copy details" for support.
// ---------------------------------------------------------------------------
const errorHandlerRegistry = registry.category("error_handlers");
const errorNotificationRegistry = registry.category("error_notifications");

/**
 * True when this server error already has its own presentation and should be
 * left to core's rpcErrorHandler (sequence 97) — so every specific mapping,
 * ours or a third party's, keeps working exactly as before.
 */
function hasSpecificHandling(originalError) {
    if (originalError.Component) {
        return true;
    }
    const name = originalError.exceptionName;
    if (name && (errorNotificationRegistry.contains(name) || errorDialogRegistry.contains(name))) {
        return true;
    }
    const cls = originalError.data?.context?.exception_class;
    return Boolean(cls && errorDialogRegistry.contains(cls));
}

export function bizRpcFallbackHandler(env, error, originalError) {
    if (!(error instanceof UncaughtPromiseError) || !(originalError instanceof RPCError)) {
        return false;
    }
    if (hasSpecificHandling(originalError)) {
        return false;
    }
    error.unhandledRejectionEvent?.preventDefault();
    env.services.dialog.add(BizErrorDialog, {
        traceback: error.traceback,
        // The server labels generic failures with its own vendor name
        // (odoo/http.py:2589 — a plain literal, not a translated string, so no
        // server-side debranding reaches it). Strip it here.
        message: stripOdoo(originalError.message),
        name: stripOdoo(originalError.name),
        exceptionName: originalError.exceptionName,
        data: originalError.data,
        subType: originalError.subType,
        code: originalError.code,
        type: originalError.type,
        serverHost: error.event?.target?.location.host,
        model: originalError.model,
    });
    return true;
}
// Just ahead of core's rpcErrorHandler (97), and only for cases it would have
// sent to the raw traceback dialog anyway.
errorHandlerRegistry.add("bizRpcFallbackHandler", bizRpcFallbackHandler, { sequence: 96 });

/**
 * Client-side crashes: Owl lifecycle errors, uncaught promises, third-party
 * scripts. Replaces core's defaultHandler outright (same sequence, force) —
 * it is the last handler in the chain and always showed a traceback.
 */
export function bizDefaultHandler(env, error) {
    env.services.dialog.add(BizErrorDialog, {
        traceback: error.traceback,
        message: stripOdoo(error.message),
        name: stripOdoo(error.name),
        serverHost: error.event?.target?.location.host,
    });
    return true;
}
errorHandlerRegistry.add("defaultHandler", bizDefaultHandler, { force: true, sequence: 100 });
