import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Company policies (WDGAP S6-B, E5). The page works without this script; it
 * adds: Ctrl/Cmd + Enter asks; the Ask button locks once pressed and the
 * "Reading the policies…" line shows while the answer is prepared (the words
 * are the template's, this file holds none).
 */
export class PbMePayaiAsk extends Interaction {
    static selector = ".pbpa";
    dynamicContent = {
        "form[data-pbpa-form]": {
            "t-on-submit.withTarget": this.onSubmit,
            "t-on-keydown.withTarget": this.onKey,
        },
    };

    onKey(ev, form) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            form.requestSubmit();
        }
    }

    onSubmit(ev, form) {
        const button = form.querySelector("[data-pbpa-submit]");
        if (button && button.disabled) {
            ev.preventDefault();
            return;
        }
        if (button) {
            button.disabled = true;
        }
        form.classList.add("is-asking");
    }
}

registry.category("public.interactions").add("pb_me_payai.ask", PbMePayaiAsk);
