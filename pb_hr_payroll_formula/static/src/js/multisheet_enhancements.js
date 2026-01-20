/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Multi-Sheet Wizard Enhancements
 * 1. Adds dual horizontal scrollbar (top and bottom)
 * 2. Removes HTML tooltips from HTML widget fields
 */

// Function to remove title attributes from HTML fields to prevent tooltip
function removeHtmlTooltips() {
    // Find all cells with HTML content in the "Depends On" column
    const htmlCells = document.querySelectorAll(
        'td[data-name="referenced_sheet_names_html"], ' +
        'td[data-name="sheet_name_html"]'
    );

    htmlCells.forEach((cell, index) => {
        // Remove title attribute
        cell.removeAttribute('title');

        // Also remove from any child elements
        const childElements = cell.querySelectorAll('[title]');
        childElements.forEach(child => {
            child.removeAttribute('title');
        });
    });
}

// Add dual scrollbar functionality to list views
function addDualScrollbar() {
    // Try multiple selector patterns to find the table containers
    const selectors = [
        '.o_field_widget[name="available_sheet_ids"] .o_list_renderer',
        '.o_field_widget[name="column_selection_ids"] .o_list_renderer',
        '.o_field_widget[name="component_preview_ids"] .o_list_renderer',
        '.o_field_widget[name="append_order_ids"] .o_list_renderer',
        '.o_field_widget[name="missing_field_ids"] .o_list_renderer',
        '.o_field_widget[name="sheet_line_ids"] .o_list_renderer',
        '.o_field_widget[name="component_line_ids"] .o_list_renderer'
    ];

    let listRenderers = [];
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        if (elements.length > 0) {
            listRenderers = Array.from(elements);
            break;
        }
    }

    if (listRenderers.length === 0) {
        return;
    }

    listRenderers.forEach((renderer, index) => {
        // Skip if already has dual scrollbar
        if (renderer.querySelector('.dual-scrollbar-wrapper') ||
            renderer.parentElement?.querySelector('.dual-scrollbar-wrapper')) {
            return;
        }

        // Get the table element
        const table = renderer.querySelector('table.o_list_table');
        if (!table) {
            return;
        }

        const tableWidth = table.scrollWidth;
        const containerWidth = renderer.clientWidth;

        // Only add scrollbar if table is significantly wider than container
        if (tableWidth <= containerWidth + 10) {
            return;
        }

        // Find the scrollable element (might be the renderer itself or a child)
        let scrollableElement = renderer;
        const rendererStyle = window.getComputedStyle(renderer);
        if (rendererStyle.overflowX !== 'auto' && rendererStyle.overflowX !== 'scroll') {
            // Look for a scrollable child
            const scrollableChild = renderer.querySelector('.o_list_view, [style*="overflow"]');
            if (scrollableChild) {
                scrollableElement = scrollableChild;
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
                break;
            }
            current = current.parentElement;
        }

        if (insertParent && insertBefore) {
            insertParent.insertBefore(topScrollWrapper, insertBefore);
        } else {
            return;
        }

        // Function to sync scrollbar widths
        function syncWidths() {
            const newTableWidth = table.scrollWidth;
            const currentWidth = parseInt(topScrollInner.style.width) || 0;
            if (Math.abs(newTableWidth - currentWidth) > 5) {
                topScrollInner.style.width = newTableWidth + 'px';
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

            // Store cleanup function
            topScrollWrapper._cleanup = () => {
                topScrollWrapper.removeEventListener('scroll', syncScrollTop);
                scrollableElement.removeEventListener('scroll', syncScrollBottom);
                resizeObserver.disconnect();
                mutationObserver.disconnect();
            };
        } catch (e) {
            // Silent fail on observer setup
        }
    });
}

// Add autocomplete dropdown for primary key column selection
function addPrimaryKeyAutocomplete() {
    // Try multiple selectors to find primary key input fields
    const selectors = [
        'input[name="primary_key_column_name"]',
        'td[data-name="primary_key_column_name"] input',
        '.o_field_widget[name="primary_key_column_name"] input',
        'td.o_data_cell[name="primary_key_column_name"] input',
        'input.o_field_widget[name="primary_key_column_name"]'
    ];

    let pkInputs = [];
    for (const selector of selectors) {
        pkInputs = document.querySelectorAll(selector);
        if (pkInputs.length > 0) {
            break;
        }
    }

    // Fallback: Search for any input in the primary_key_column_name column
    if (pkInputs.length === 0) {
        const availableSheetTable = document.querySelector('.o_field_widget[name="available_sheet_ids"] table');
        if (availableSheetTable) {
            // Find all rows
            const rows = availableSheetTable.querySelectorAll('tbody tr');
            // For each row, find inputs (Odoo renders inputs dynamically in editable tree)
        }
    }

    pkInputs.forEach((input, index) => {
        // Skip if already has autocomplete
        if (input.hasAttribute('data-autocomplete-setup')) {
            return;
        }

        // Mark as setup to avoid duplicate processing
        input.setAttribute('data-autocomplete-setup', 'true');

        // Find the row containing this input
        const row = input.closest('tr');
        if (!row) {
            return;
        }

        // Find the available_column_names hidden field in the same row
        const availableColsInput = row.querySelector('input[name="available_column_names"]');
        if (!availableColsInput || !availableColsInput.value) {
            return;
        }

        // Parse available columns JSON
        let availableColumns = [];
        try {
            availableColumns = JSON.parse(availableColsInput.value);
        } catch (e) {
            return;
        }

        if (availableColumns.length === 0) {
            return;
        }

        // Create datalist element for autocomplete
        const datalistId = `pk-columns-${index}-${Date.now()}`;
        let datalist = document.getElementById(datalistId);

        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;

            // Add options for each available column
            availableColumns.forEach(col => {
                const option = document.createElement('option');
                option.value = col;
                datalist.appendChild(option);
            });

            // Insert datalist into DOM
            input.parentElement.appendChild(datalist);
        }

        // Link input to datalist
        input.setAttribute('list', datalistId);
        input.setAttribute('autocomplete', 'off'); // Disable browser autocomplete
        input.setAttribute('placeholder', `Select from: ${availableColumns.slice(0, 2).join(', ')}...`);
    });

    // Also set up click event listener for cells that will trigger inline editing
    setupCellClickListener();
}

// Setup click listener for primary key column cells to add autocomplete when editing starts
function setupCellClickListener() {
    const availableSheetTable = document.querySelector('.o_field_widget[name="available_sheet_ids"] table');
    if (!availableSheetTable) {
        return;
    }

    // Find all cells in the primary_key_column_name column
    const pkCells = availableSheetTable.querySelectorAll('td[name="primary_key_column_name"]');

    pkCells.forEach((cell, index) => {
        // Skip if already has listener
        if (cell.hasAttribute('data-click-listener-setup')) {
            return;
        }

        cell.setAttribute('data-click-listener-setup', 'true');

        // Add click listener
        cell.addEventListener('click', function(event) {
            // Wait a bit for Odoo to render the input field
            setTimeout(() => {
                const input = cell.querySelector('input');
                if (input) {
                    setupAutocompleteForInput(input, index);
                }
            }, 100);
        });
    });
}

// Setup autocomplete for a specific input element
function setupAutocompleteForInput(input, index) {
    // Skip if already has autocomplete
    if (input.hasAttribute('data-autocomplete-setup')) {
        return;
    }

    input.setAttribute('data-autocomplete-setup', 'true');

    // Find the row containing this input
    const row = input.closest('tr');
    if (!row) {
        return;
    }

    // Find the available_column_names hidden field in the same row
    const availableColsInput = row.querySelector('input[name="available_column_names"]');
    if (!availableColsInput || !availableColsInput.value) {
        return;
    }

    // Parse available columns JSON
    let availableColumns = [];
    try {
        availableColumns = JSON.parse(availableColsInput.value);
    } catch (e) {
        return;
    }

    if (availableColumns.length === 0) {
        return;
    }

    // Create datalist element for autocomplete
    const datalistId = `pk-columns-${index}-${Date.now()}`;
    let datalist = document.getElementById(datalistId);

    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = datalistId;

        // Add options for each available column
        availableColumns.forEach(col => {
            const option = document.createElement('option');
            option.value = col;
            datalist.appendChild(option);
        });

        // Insert datalist into DOM
        document.body.appendChild(datalist); // Append to body instead of input.parentElement
    }

    // Link input to datalist
    input.setAttribute('list', datalistId);
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('placeholder', `Select from: ${availableColumns.slice(0, 2).join(', ')}...`);
}

// Main enhancement function
function applyEnhancements() {
    removeHtmlTooltips();
    addDualScrollbar();
    addPrimaryKeyAutocomplete();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(applyEnhancements, 100);
    });
} else {
    // DOM already loaded
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
        let needsAutocompleteSetup = false;

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

                    // Check if we added primary key input fields
                    if (node.matches('input[name="primary_key_column_name"]') ||
                        node.querySelector('input[name="primary_key_column_name"]')) {
                        needsAutocompleteSetup = true;
                    }
                }
            });
        });

        if (needsTooltipRemoval) {
            setTimeout(removeHtmlTooltips, 50);
        }

        if (needsAutocompleteSetup) {
            setTimeout(() => {
                addPrimaryKeyAutocomplete();
                setupCellClickListener(); // Also setup click listeners
            }, 100);
        }

        if (needsUpdate) {
            setTimeout(applyEnhancements, 150);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

startObserving();
