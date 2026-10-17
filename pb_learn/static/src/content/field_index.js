/** @odoo-module **/
/* =============================================================================
   LEARNREV P3 — the field index: every field card of every screen, light.

   One call (`learn.guide.rpc_index`), in the asking language, held for the
   page's life: the Library's search reads it, and the drawer turns it into the
   ⌘K field rows ("Pay role · Field on Component treatment"). The rows carry
   both spellings of every column, so either language finds them.

   Never throws: a failed call is an empty index (the search still finds
   screens, terms, tasks and lessons), and the next ask tries again.
   ========================================================================== */
const CACHE = new Map();

/** "vi" | "en" → the server's language code. */
export function serverLang(lang) {
    return lang === "vi" ? "vi_VN" : "en_US";
}

/** The index in `lang` ("en" | "vi"), fetched once per language. */
export function loadFieldIndex(orm, lang) {
    const key = serverLang(lang);
    if (CACHE.has(key)) {
        return CACHE.get(key);
    }
    const p = Promise.resolve()
        .then(() => orm.call("learn.guide", "rpc_index", [], { context: { lang: key } }))
        .then((rows) => (Array.isArray(rows) ? rows : []))
        .catch(() => {
            CACHE.delete(key);
            return [];
        });
    CACHE.set(key, p);
    return p;
}

/** For the tests: forget what was fetched. */
export function resetFieldIndex() {
    CACHE.clear();
}
