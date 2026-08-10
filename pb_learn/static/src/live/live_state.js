/** @odoo-module **/
/* =============================================================================
   Where a running live mission lives.

   WHY THIS IS NOT INSIDE A COMPONENT
   ----------------------------------
   A fixture mission runs inside the Journey client action, over a replica the
   Journey draws. A LIVE mission runs over the product, so the very first step
   navigates away from the Journey — and the Journey component unmounts, taking
   any state it held with it. The panel therefore mounts beside the Coach in the
   web-client shell, and the two surfaces need one place to agree about what is
   running.

   Persisted to localStorage, for the same reason the mission exists: a prospect
   who reloads the page mid-payroll should come back to the step they were on,
   not to the top of a mission they have half finished. Only the key and the
   step index are stored — the content is re-read from the bundle, so a content
   change never resurrects a stale sentence.
   ========================================================================== */

const KEY = "pbLearnLive";

function read() {
    try {
        const raw = window.localStorage.getItem(KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        // A locked-down profile must not break the runner; it just cannot resume.
        return null;
    }
}

function persist(value) {
    try {
        if (value) {
            window.localStorage.setItem(KEY, JSON.stringify(value));
        } else {
            window.localStorage.removeItem(KEY);
        }
    } catch {
        // Same: not being able to remember is survivable, throwing is not.
    }
}

export const LiveState = {
    /** {mission, step, acked: [stepKey], minimised} — or null when nothing runs. */
    current: read(),
    listeners: new Set(),

    subscribe(fn) {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    },

    _emit() {
        persist(this.current);
        for (const fn of this.listeners) {
            fn(this.current);
        }
    },

    start(missionKey) {
        this.current = { mission: missionKey, step: 0, acked: [], minimised: false };
        this._emit();
    },

    /** Leaving is always allowed and never destroys anything: the run the
     *  learner has already driven is real and stays exactly where it is. */
    stop() {
        this.current = null;
        this._emit();
    },

    setStep(index) {
        if (!this.current) {
            return;
        }
        this.current.step = index;
        this._emit();
    },

    ack(stepKey) {
        if (!this.current || this.current.acked.includes(stepKey)) {
            return;
        }
        this.current.acked.push(stepKey);
        this._emit();
    },

    isAcked(stepKey) {
        return !!this.current && this.current.acked.includes(stepKey);
    },

    setMinimised(value) {
        if (!this.current) {
            return;
        }
        this.current.minimised = !!value;
        this._emit();
    },
};
