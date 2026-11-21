/** @odoo-module **/

/**
 * Formula Grid Top Scrollbar
 *
 * Adds a synchronised horizontal scrollbar above the formula rule grid table.
 * Also adjusts sticky header positioning so headers appear below the scrollbar.
 */

function installTopScroll() {
    // Scope to `.o_pb_fx_grid` (the marker on formula-engine wizard / import /
    // sample-data forms with genuinely wide grids). Without this scope the top
    // scrollbar was injected onto EVERY one2many list app-wide — including the
    // native payslip-lines dialog — which, together with the wide-grid CSS,
    // clipped the first column's text on the left.
    const listRenderers = document.querySelectorAll('.o_pb_fx_grid .o_field_one2many .o_list_renderer');
    if (!listRenderers.length) return false;

    let installed = false;
    for (const listEl of listRenderers) {
        if (listEl.dataset.topScrollInstalled) continue;

        const table = listEl.querySelector('.o_list_table');
        if (!table) continue;

        const thead = table.querySelector('thead');
        if (!thead) continue;

        // Create the top scroll wrapper — placed BEFORE the table, INSIDE the list renderer
        const wrapper = document.createElement('div');
        wrapper.className = 'o_formula_grid_top_scroll_wrapper';
        const inner = document.createElement('div');
        wrapper.appendChild(inner);

        // Insert before the table
        table.parentNode.insertBefore(wrapper, table);

        // Measure scrollbar wrapper height
        const scrollbarHeight = wrapper.offsetHeight || 20;

        // CRITICAL: Push the sticky header <th> elements down by the scrollbar height
        // so they don't overlap with the scrollbar.
        const headerCells = thead.querySelectorAll('th');
        headerCells.forEach(function (th) {
            th.style.setProperty('top', scrollbarHeight + 'px', 'important');
        });

        // Also observe for future header changes (Odoo might re-render the thead)
        const theadObserver = new MutationObserver(function () {
            const ths = thead.querySelectorAll('th');
            ths.forEach(function (th) {
                if (th.style.top !== scrollbarHeight + 'px') {
                    th.style.setProperty('top', scrollbarHeight + 'px', 'important');
                }
            });
        });
        theadObserver.observe(thead, { childList: true, subtree: true });

        function syncWidth() {
            inner.style.width = table.scrollWidth + 'px';
        }
        syncWidth();

        // Synchronise scrolling between top scrollbar and the list renderer
        let syncing = false;
        wrapper.addEventListener('scroll', function () {
            if (!syncing) {
                syncing = true;
                listEl.scrollLeft = wrapper.scrollLeft;
                syncing = false;
            }
        });
        listEl.addEventListener('scroll', function () {
            if (!syncing) {
                syncing = true;
                wrapper.scrollLeft = listEl.scrollLeft;
                syncing = false;
            }
        });

        // Re-sync width when table resizes
        const resizeObserver = new ResizeObserver(function () {
            syncWidth();
        });
        resizeObserver.observe(table);

        listEl.dataset.topScrollInstalled = 'true';
        installed = true;
    }
    return installed;
}

function startObserving() {
    if (!document.body) {
        setTimeout(startObserving, 200);
        return;
    }

    // Poll for list views to appear
    let attempts = 0;
    const maxAttempts = 40;

    function poll() {
        installTopScroll();
        attempts++;
        if (attempts < maxAttempts) {
            setTimeout(poll, 800);
        }
    }
    setTimeout(poll, 500);

    // Watch for DOM changes (new views being loaded)
    const bodyObserver = new MutationObserver(function () {
        const fresh = document.querySelectorAll(
            '.o_pb_fx_grid .o_field_one2many .o_list_renderer:not([data-top-scroll-installed])'
        );
        if (fresh.length) {
            installTopScroll();
        }
    });
    bodyObserver.observe(document.body, { childList: true, subtree: true });

    // Re-check on hash navigation
    window.addEventListener('hashchange', function () {
        setTimeout(installTopScroll, 600);
    });
}

// Safely wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserving);
} else {
    startObserving();
}
