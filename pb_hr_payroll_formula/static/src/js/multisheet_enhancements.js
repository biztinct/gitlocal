/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Multi-Sheet Wizard Enhancements
 * 1. Adds dual horizontal scrollbar (top and bottom)
 * 2. Removes HTML tooltips from HTML widget fields
 */

console.log('=== MULTISHEET ENHANCEMENTS MODULE LOADED ===');

// Function to remove title attributes from HTML fields to prevent tooltip
function removeHtmlTooltips() {
    console.log('Removing HTML tooltips...');

    // Find all cells with HTML content in the "Depends On" column
    const htmlCells = document.querySelectorAll(
        'td[data-name="referenced_sheet_names_html"], ' +
        'td[data-name="sheet_name_html"]'
    );

    console.log(`Found ${htmlCells.length} HTML cells to process`);

    htmlCells.forEach((cell, index) => {
        // Remove title attribute
        cell.removeAttribute('title');

        // Also remove from any child elements
        const childElements = cell.querySelectorAll('[title]');
        childElements.forEach(child => {
            child.removeAttribute('title');
        });

        console.log(`Processed cell ${index}: removed title attributes`);
    });
}

// Add dual scrollbar functionality to list views
function addDualScrollbar() {
    console.log('\n=== DUAL SCROLLBAR: Starting detection ===');

    // Try multiple selector patterns to find the table containers
    const selectors = [
        '.o_field_widget[name="available_sheet_ids"] .o_list_renderer',
        '.o_field_widget[name="column_selection_ids"] .o_list_renderer',
        '.o_field_widget[name="component_preview_ids"] .o_list_renderer',
        '.o_field_widget[name="append_order_ids"] .o_list_renderer',
        '.o_form_view .o_field_one2many .o_list_renderer',
        '.o_field_one2many .o_list_renderer',
        '.o_list_renderer'
    ];

    let listRenderers = [];
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        console.log(`Selector "${selector}" found ${elements.length} elements`);
        if (elements.length > 0) {
            listRenderers = Array.from(elements);
            console.log(`Using selector: ${selector}`);
            break;
        }
    }

    if (listRenderers.length === 0) {
        console.log('No list renderers found with selectors. Trying fallback...');
        // Fallback: find all wide tables
        const allTables = document.querySelectorAll('table.o_list_table');
        console.log(`Found ${allTables.length} total list tables in DOM`);

        allTables.forEach((table, index) => {
            const scrollWidth = table.scrollWidth;
            const clientWidth = table.clientWidth;
            console.log(`Table ${index}: scrollWidth=${scrollWidth}, clientWidth=${clientWidth}`);

            if (scrollWidth > clientWidth + 10) { // 10px threshold
                // Find the renderer/container
                let container = table.closest('.o_list_renderer') ||
                               table.closest('.o_list_view') ||
                               table.parentElement;
                if (container && container !== document.body) {
                    console.log(`Adding wide table ${index} to process list`);
                    listRenderers.push(container);
                }
            }
        });
    }

    console.log(`Processing ${listRenderers.length} list renderer containers\n`);

    listRenderers.forEach((renderer, index) => {
        console.log(`--- Processing renderer ${index} ---`);

        // Skip if already has dual scrollbar
        if (renderer.querySelector('.dual-scrollbar-wrapper') ||
            renderer.parentElement?.querySelector('.dual-scrollbar-wrapper')) {
            console.log('Dual scrollbar already exists, skipping');
            return;
        }

        // Get the table element
        const table = renderer.querySelector('table.o_list_table');
        if (!table) {
            console.log('No table found in renderer');
            return;
        }

        const tableWidth = table.scrollWidth;
        const containerWidth = renderer.clientWidth;
        console.log(`Table dimensions: scrollWidth=${tableWidth}px, containerWidth=${containerWidth}px`);

        // Only add scrollbar if table is significantly wider than container
        if (tableWidth <= containerWidth + 10) {
            console.log('Table fits in container, no scrollbar needed');
            return;
        }

        console.log(`✓ Table needs scrollbar (${tableWidth}px > ${containerWidth}px)`);

        // Find the scrollable element (might be the renderer itself or a child)
        let scrollableElement = renderer;
        const rendererStyle = window.getComputedStyle(renderer);
        if (rendererStyle.overflowX !== 'auto' && rendererStyle.overflowX !== 'scroll') {
            // Look for a scrollable child
            const scrollableChild = renderer.querySelector('.o_list_view, [style*="overflow"]');
            if (scrollableChild) {
                scrollableElement = scrollableChild;
                console.log('Using scrollable child element');
            }
        }

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

        // Find the best place to insert the scrollbar
        // We want it above the table, inside the field widget
        let insertParent = renderer.parentElement;
        let insertBefore = renderer;

        // Try to find the field widget container
        let current = renderer;
        while (current && current !== document.body) {
            if (current.classList.contains('o_field_widget')) {
                insertParent = current;
                insertBefore = current.firstElementChild;
                console.log('Found field widget container for insertion');
                break;
            }
            current = current.parentElement;
        }

        if (insertParent && insertBefore) {
            insertParent.insertBefore(topScrollWrapper, insertBefore);
            console.log('✓ Dual scrollbar DOM element inserted');
        } else {
            console.log('✗ Could not find insertion point');
            return;
        }

        // Function to sync scrollbar widths
        function syncWidths() {
            const newTableWidth = table.scrollWidth;
            const currentWidth = parseInt(topScrollInner.style.width) || 0;
            if (Math.abs(newTableWidth - currentWidth) > 5) {
                topScrollInner.style.width = newTableWidth + 'px';
                console.log(`Synced widths: ${newTableWidth}px`);
            }
        }

        // Sync scroll positions
        function syncScrollTop() {
            const scrollLeft = topScrollWrapper.scrollLeft;
            if (scrollableElement.scrollLeft !== scrollLeft) {
                scrollableElement.scrollLeft = scrollLeft;
            }
        }

        function syncScrollBottom() {
            const scrollLeft = scrollableElement.scrollLeft;
            if (topScrollWrapper.scrollLeft !== scrollLeft) {
                topScrollWrapper.scrollLeft = scrollLeft;
            }
        }

        // Add event listeners
        topScrollWrapper.addEventListener('scroll', syncScrollTop);
        scrollableElement.addEventListener('scroll', syncScrollBottom);

        console.log('✓ Scroll event listeners attached');

        // Initial sync with delays
        setTimeout(syncWidths, 50);
        setTimeout(syncWidths, 200);
        setTimeout(syncWidths, 500);
        setTimeout(syncWidths, 1000);

        // Re-sync on window resize and table mutations
        try {
            const resizeObserver = new ResizeObserver(() => {
                syncWidths();
            });
            resizeObserver.observe(table);

            const mutationObserver = new MutationObserver(() => {
                syncWidths();
            });
            mutationObserver.observe(table, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['style', 'class']
            });

            console.log('✓ Observers attached');

            // Store cleanup function
            topScrollWrapper._cleanup = () => {
                topScrollWrapper.removeEventListener('scroll', syncScrollTop);
                scrollableElement.removeEventListener('scroll', syncScrollBottom);
                resizeObserver.disconnect();
                mutationObserver.disconnect();
            };
        } catch (e) {
            console.error('Error setting up observers:', e);
        }

        console.log('✓ Dual scrollbar setup complete for renderer ' + index);
    });

    console.log('=== DUAL SCROLLBAR: Detection complete ===\n');
}

// Main enhancement function
function applyEnhancements() {
    console.log('\n=== APPLYING MULTISHEET ENHANCEMENTS ===');
    removeHtmlTooltips();
    addDualScrollbar();
    console.log('=== ENHANCEMENTS APPLIED ===\n');
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM Content Loaded - applying enhancements');
        setTimeout(applyEnhancements, 100);
    });
} else {
    // DOM already loaded
    console.log('DOM already loaded - applying enhancements');
    setTimeout(applyEnhancements, 100);
}

// Watch for dynamically added content
function startObserving() {
    if (!document.body) {
        setTimeout(startObserving, 100);
        return;
    }

    const observer = new MutationObserver((mutations) => {
        let needsUpdate = false;
        let needsTooltipRemoval = false;

        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) {
                    // Check if we added a list view
                    if (node.matches('.o_list_renderer, .o_list_view') ||
                        node.querySelector('.o_list_renderer, .o_list_view')) {
                        needsUpdate = true;
                    }

                    // Check if we added HTML field cells
                    if (node.matches('td[data-name="referenced_sheet_names_html"], td[data-name="sheet_name_html"]') ||
                        node.querySelector('td[data-name="referenced_sheet_names_html"], td[data-name="sheet_name_html"]')) {
                        needsTooltipRemoval = true;
                    }
                }
            });
        });

        if (needsTooltipRemoval) {
            setTimeout(removeHtmlTooltips, 50);
        }

        if (needsUpdate) {
            setTimeout(applyEnhancements, 150);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log('✓ MutationObserver started for dynamic content');
}

startObserving();

console.log('=== MULTISHEET ENHANCEMENTS MODULE INITIALIZED ===\n');
