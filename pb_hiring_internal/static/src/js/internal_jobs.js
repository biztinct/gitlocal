import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Jobs inside the company (WDGAP S6-B). Every page works without this
 * script; it only adds:
 *  - the Apply button is locked once pressed, so a double click never
 *    applies twice (the server refuses a second application anyway);
 *  - withdrawing asks once, with the sentence the template holds (this file
 *    holds no words);
 *  - the one-off `done` / `error` keys leave the address bar once shown.
 */
export class PbHiringInternalJobs extends Interaction {
    static selector = ".pbhi";
    dynamicContent = {
        "form[data-pbhi-form]": { "t-on-submit.withTarget": this.onApply },
        "form[data-pbhi-confirm]": { "t-on-submit.withTarget": this.onWithdraw },
    };

    start() {
        const url = new URL(window.location.href);
        if (url.searchParams.has("done") || url.searchParams.has("error")) {
            url.searchParams.delete("done");
            url.searchParams.delete("error");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
    }

    onApply(ev, form) {
        const button = form.querySelector("[data-pbhi-submit]");
        if (!button) {
            return;
        }
        if (button.disabled) {
            ev.preventDefault();
            return;
        }
        button.disabled = true;
        button.classList.add("is-busy");
    }

    onWithdraw(ev, form) {
        const words = form.querySelector("[data-pbhi-ask]");
        const question = words ? words.textContent.trim() : "";
        if (question && !window.confirm(question)) {
            ev.preventDefault();
        }
    }
}

registry.category("public.interactions").add("pb_hiring_internal.jobs", PbHiringInternalJobs);
