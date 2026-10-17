import { registry } from "@web/core/registry";

/**
 * VU Theme loader — applies DRAFT theme tokens for preview.
 *
 * The published theme arrives as a stylesheet (/biz_theme/tokens.css) and needs
 * no JS. This service only handles the preview flow: the Theme Studio writes
 * draft tokens to sessionStorage, so the previewing admin sees them on every
 * page of THIS TAB while other users/tabs are untouched. Inline properties on
 * <html> outrank the published stylesheet by cascade origin — exactly the
 * override order we want (draft > published > compiled defaults).
 */
const STORAGE_KEY = "biz_theme_draft";
const TOKEN_PREFIX = "vu-"; // hard whitelist: only theme custom properties

export function applyDraftTokens(tokens) {
    const style = document.documentElement.style;
    clearDraftTokens();
    const applied = [];
    for (const [key, value] of Object.entries(tokens || {})) {
        if (typeof key !== "string" || !key.startsWith(TOKEN_PREFIX)) {
            continue;
        }
        if (typeof value !== "string" || /[;{}<>@\\]/.test(value)) {
            continue;
        }
        style.setProperty(`--${key}`, value);
        applied.push(key);
    }
    style.setProperty("--vu-draft-active", applied.length ? "1" : "0");
    return applied;
}

export function clearDraftTokens() {
    const style = document.documentElement.style;
    for (let i = style.length - 1; i >= 0; i--) {
        const prop = style.item(i);
        if (prop.startsWith(`--${TOKEN_PREFIX}`)) {
            style.removeProperty(prop);
        }
    }
}

export const themeLoaderService = {
    start() {
        let draft = null;
        try {
            draft = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
        } catch {
            sessionStorage.removeItem(STORAGE_KEY);
        }
        if (draft && typeof draft === "object") {
            applyDraftTokens(draft);
        }
        return {
            preview(tokens) {
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens || {}));
                applyDraftTokens(tokens);
            },
            stopPreview() {
                sessionStorage.removeItem(STORAGE_KEY);
                clearDraftTokens();
            },
            isPreviewing() {
                return !!sessionStorage.getItem(STORAGE_KEY);
            },
            getDraft() {
                try {
                    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
                } catch {
                    return null;
                }
            },
        };
    },
};

registry.category("services").add("biz_theme_loader", themeLoaderService);
