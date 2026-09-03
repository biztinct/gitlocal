/** @odoo-module **/
/**
 * The bar at the top of every page, when the platform has something to say.
 *
 * TWO COMPONENTS, ON PURPOSE.
 *
 *   <PbTenancyBar/>     draws ONE notice, from a prop. It knows nothing about
 *                       where the notice came from and nothing about dismissal.
 *   <PbTenancyBanner/>  the thing mounted in the web client: asks the service
 *                       whether there is a notice this person has not closed,
 *                       and renders the bar if so.
 *
 * The split is what makes the platform owner's composer honest. His live
 * preview is not a drawing of the bar — it IS the bar, the same component with
 * the same styles and the same time-phrase renderer, so the sentence he
 * approves is exactly the sentence the customer reads. A preview that is a
 * separate lookalike is a preview that goes out of date the first time somebody
 * changes a padding.
 *
 * A BAR, NEVER A MODAL. Somebody halfway through entering a pay run must not be
 * interrupted by a box they have to dismiss before they can carry on typing.
 * The bar takes a strip at the top, says its piece, and has an x.
 */
import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { noticeKey } from "./tenancy_service";
import { WebClient } from "@web/webclient/webclient";
import { ic } from "@pb_import_kit/js/import_icons";
import { renderRange } from "./tenancy_range";
import { _t } from "@web/core/l10n/translation";

/** One notice, drawn. No state, no service, no decisions about visibility. */
export class PbTenancyBar extends Component {
    static template = "pb_tenancy.Bar";
    static props = {
        // { kind, title, text, starts_at, ends_at, id }
        notice: { type: Object },
        // Absent in the composer's preview: there is nothing to dismiss there.
        onDismiss: { type: Function, optional: true },
        // "preview" softens the shadow and drops the fixed positioning so the
        // bar can sit inside a card.
        preview: { type: Boolean, optional: true },
        // FLEET P5. The little word in front of the message. A platform notice
        // works its own out from its kind; a bar this database composed about
        // its own standing says what it is about ("Your trial", "Your plan").
        label: { type: String, optional: true },
    };

    ic(name, size = 16) { return ic(name, size); }

    get kind() {
        return this.props.notice.kind === "maintenance" ? "maintenance" : "info";
    }

    get icon() {
        return this.kind === "maintenance" ? "wrench" : "info";
    }

    /** "tonight 22:00–01:00", in this reader's own clock. */
    get range() {
        const n = this.props.notice;
        return renderRange(n.starts_at, n.ends_at);
    }

    get label() {
        if (this.props.label) { return this.props.label; }
        if (this.props.notice.live) { return _t("Happening now"); }
        return this.kind === "maintenance"
            ? _t("Planned update") : _t("From Payobook");
    }

    /**
     * An update that is happening RIGHT NOW cannot be hidden.
     *
     * Every other message on this bar is something the reader may take or
     * leave. This one is the explanation for a pause they are about to sit
     * through, so somebody who closes it is left looking at a fault instead of
     * a notice. It carries `live` and comes down on its own the moment the
     * work is finished — which is a minute or two, not a day.
     */
    get dismissable() {
        return !!this.props.onDismiss && !this.props.notice.live;
    }
}

/**
 * FLEET P5 — the company's own standing, said in one line.
 *
 * TWO THINGS AND NO MORE: a trial that is running out, and an employee limit
 * that is nearly reached. Both are the SAME SHAPE as a platform notice and are
 * drawn by the same bar, but neither of them was sent by anybody — they are
 * composed here, from the answer this database already has, which is why they
 * carry no id and are dismissed for the day rather than for ever.
 *
 * IT NEVER SPEAKS ABOUT A LIMIT THAT IS ALREADY FULL. At that point adding an
 * employee is refused with a sentence of its own, and a bar repeating it at the
 * top of every page for the rest of the month is noise, not help.
 */
export class PbTenancyStandingBar extends Component {
    static template = "pb_tenancy.Standing";
    static components = { PbTenancyBar };
    static props = {};

    setup() {
        this.tenancy = useService("pb_tenancy");
        // Subscribed, not merely fetched (ledger F47): the countdown moves.
        this.state = useState(this.tenancy.state);
    }

    /** The notice to draw, or null. Trial first: it has a deadline on it. */
    get notice() {
        // Reading the signature registers this component against the ONE value
        // that changes when an answer changes, rather than against objects the
        // service rebuilds every minute.
        void this.state.standing_sig;
        if (this.today === this.state.standing_dismissed) { return null; }
        const trial = this.state.trial || {};
        if (trial.phase === "ending" || trial.phase === "ended") {
            return {
                kind: "maintenance",
                title: trial.text || _t("Your Payobook trial is ending."),
                text: _t("Everything you have entered stays exactly where it is. " +
                         "Talk to us and we will move you onto a plan."),
                label: _t("Your trial"),
            };
        }
        const seat = this.state.seat || {};
        if (seat.verdict === "near" && seat.limit) {
            return {
                kind: "info",
                title: _t("You have %(count)s of the %(limit)s employees your plan allows.",
                          { count: seat.count, limit: seat.limit }),
                text: _t("You can add %(left)s more. Ask your Payobook administrator " +
                         "for a larger plan before you run out.", { left: seat.left }),
                label: _t("Your plan"),
            };
        }
        return null;
    }

    get today() { return new Date().toISOString().slice(0, 10); }

    /** A CLICK handler. */
    dismiss() { this.tenancy.dismissStanding(); }
}

/** The one mounted in the web client. */
export class PbTenancyBanner extends Component {
    static template = "pb_tenancy.Banner";
    static components = { PbTenancyBar, PbTenancyStandingBar };
    static props = {};

    setup() {
        this.tenancy = useService("pb_tenancy");
        // `useState` AND NOT `this.tenancy.state`, and the difference is the
        // whole feature. A service's reactive object only re-renders the
        // components that have SUBSCRIBED to it, and `useService` subscribes to
        // nothing — so a banner reading the service object directly renders once
        // at mount and never again. The poll fetched the new notice every
        // minute, the state changed, and the screen sat there (ledger F22).
        this.state = useState(this.tenancy.state);
    }

    /**
     * The notice to show, or null.
     *
     * Read off `this.state` rather than delegating to the service, for the same
     * reason: every property this getter touches has to be touched through the
     * component's own subscription or the render is not re-run when it changes.
     */
    get notice() {
        const n = this.state.notice;
        if (!n || !n.title) { return null; }
        return noticeKey(n) === this.state.dismissed ? null : n;
    }

    /** A CLICK handler. */
    dismiss() { this.tenancy.dismiss(); }
}

// The mount point. `//NavBar` rather than `//ActionContainer`, which two other
// modules on this build already REPLACE with wrappers of their own — a third
// module replacing it would be a race between load orders. NavBar is only
// wrapped in a `t-if="!state.fullscreen"`, so the bar is absent in full-screen
// surfaces, which is right: full screen means "no chrome".
patch(WebClient, {
    components: { ...WebClient.components, PbTenancyBanner },
});
