/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Dual Scrollbar for Multi-Sheet Wizard Tables
 * Adds a synchronized horizontal scrollbar at the top of wide tables
 */

// Add dual scrollbar functionality to list views
function addDualScrollbar() {
    console.log('=== DUAL SCROLLBAR: Starting detection ===');

    // Try multiple selector patterns to find the table containers
    const selectors = [
        '.o_form_view .o_field_one2many .o_list_view',
        '.o_field_one2many .o_list_renderer',
        '.o_list_view',
        '.o_field_x2many_list',
        'div.o_field_widget[name="available_sheet_ids"] .o_list_renderer',
        'div.o_field_widget[name="column_selection_ids"] .o_list_renderer',
        'div.o_field_widget[name="component_preview_ids"] .o_list_renderer'
    ];

    let listViews = [];
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        console.log(`Selector "${selector}" found ${elements.length} elements`);
        if (elements.length > 0) {
            listViews = [...elements];
            break;
        }
    }

    if (listViews.length === 0) {
        console.log('No list views found with any selector. Checking entire DOM...');
        // Fallback: find all tables and check if they need scrollbars
        const allTables = document.querySelectorAll('table.o_list_table');
        console.log(`Found ${allTables.length} total list tables in DOM`);

        allTables.forEach((table, index) => {
            console.log(`Table ${index}: scrollWidth=${table.scrollWidth}, clientWidth=${table.clientWidth}`);
            if (table.scrollWidth > table.clientWidth) {
                // Find the scrollable container
                let container = table.parentElement;
                while (container && !container.classList.contains('o_list_view') &&
                       !container.classList.contains('o_list_renderer')) {
                    container = container.parentElement;
                    if (container === document.body) {
                        container = null;
                        break;
                    }
                }
                if (container) {
                    console.log(`Adding container for table ${index}`);
                    listViews.push(container);
                }
            }
        });
    }

    console.log(`Processing ${listViews.length} list view containers`);

    listViews.forEach((listView, index) => {
        console.log(`\n--- Processing list view ${index} ---`);

        // Skip if already has dual scrollbar
        const existingScrollbar = listView.parentElement?.querySelector('.dual-scrollbar-wrapper');
        if (existingScrollbar) {
            console.log('Dual scrollbar already exists, skipping');
            return;
        }

        // Get the table element
        const table = listView.querySelector('table.o_list_table') ||
                     (listView.tagName === 'TABLE' ? listView : null);
        if (!table) {
            console.log('No table found in list view');
            return;
        }

        const tableWidth = table.scrollWidth;
        const containerWidth = listView.clientWidth;
        console.log(`Table dimensions: scrollWidth=${tableWidth}, containerWidth=${containerWidth}`);

        // Only add scrollbar if table is wider than container
        if (tableWidth <= containerWidth) {
            console.log('Table fits in container, no scrollbar needed');
            return;
        }

        console.log(`Adding dual scrollbar for table (width: ${tableWidth}px)`);

        // Create wrapper for top scrollbar
        const topScrollWrapper = document.createElement('div');
        topScrollWrapper.className = 'dual-scrollbar-wrapper';
        topScrollWrapper.style.cssText = `
            overflow-x: auto;
            overflow-y: hidden;
            height: 20px;
            margin-bottom: 10px;
            width: 100%;
            display: block;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
        `;

        // Create inner div that matches table width
        const topScrollInner = document.createElement('div');
        topScrollInner.style.cssText = `
            height: 1px;
            width: ${tableWidth}px;
        `;
        topScrollWrapper.appendChild(topScrollInner);

        // Find the best parent container to insert before
        let parentContainer = listView.parentElement;
        let insertBefore = listView;

        // Try to find the field widget container
        let current = listView;
        while (current && current !== document.body) {
            if (current.classList.contains('o_field_widget') ||
                current.classList.contains('o_field_one2many') ||
                current.classList.contains('o_field_x2many')) {
                parentContainer = current.parentElement;
                insertBefore = current;
                console.log('Found field widget container');
                break;
            }
            current = current.parentElement;
        }

        if (parentContainer) {
            parentContainer.insertBefore(topScrollWrapper, insertBefore);
            console.log('✓ Dual scrollbar added successfully');
        } else {
            console.log('✗ No parent container found');
            return;
        }

        // Function to sync scrollbar widths
        function syncWidths() {
            const newTableWidth = table.scrollWidth;
            if (newTableWidth !== parseInt(topScrollInner.style.width)) {
                topScrollInner.style.width = newTableWidth + 'px';
                console.log(`Synced widths: ${newTableWidth}px`);
            }
        }

        // Sync scroll positions
        function syncScrollTop() {
            listView.scrollLeft = topScrollWrapper.scrollLeft;
        }

        function syncScrollBottom() {
            topScrollWrapper.scrollLeft = listView.scrollLeft;
        }

        // Add event listeners
        topScrollWrapper.addEventListener('scroll', syncScrollTop);
        listView.addEventListener('scroll', syncScrollBottom);

        // Initial sync with multiple delays to ensure table is fully rendered
        setTimeout(syncWidths, 100);
        setTimeout(syncWidths, 300);
        setTimeout(syncWidths, 500);
        setTimeout(syncWidths, 1000);

        // Re-sync on window resize and table mutations
        const resizeObserver = new ResizeObserver(syncWidths);
        resizeObserver.observe(table);

        // Watch for table content changes
        const mutationObserver = new MutationObserver(syncWidths);
        mutationObserver.observe(table, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['style', 'class', 'width']
        });

        // Store cleanup function
        topScrollWrapper._cleanup = () => {
            topScrollWrapper.removeEventListener('scroll', syncScrollTop);
            listView.removeEventListener('scroll', syncScrollBottom);
            resizeObserver.disconnect();
            mutationObserver.disconnect();
        };
    });

    console.log('=== DUAL SCROLLBAR: Detection complete ===\n');
}

// Run when DOM is ready and on relevant mutations
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addDualScrollbar);
} else {
    // DOM already loaded
    addDualScrollbar();
}

// Watch for dynamically added list views
function startObserving() {
    if (!document.body) {
        // Body not ready yet, try again
        setTimeout(startObserving, 100);
        return;
    }

    const observer = new MutationObserver((mutations) => {
        let shouldUpdate = false;

        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1 && (
                    node.matches('.o_list_view') ||
                    node.querySelector('.o_list_view')
                )) {
                    shouldUpdate = true;
                }
            });
        });

        if (shouldUpdate) {
            // Delay to ensure DOM is fully rendered
            setTimeout(addDualScrollbar, 100);
        }
    });

    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log('Dual scrollbar observer started');
}

// Start observing when ready
startObserving();

console.log('Dual scrollbar module loaded');
