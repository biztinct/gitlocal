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
        '.o_field_widget[name="missing_field_ids"] .o_list_renderer',
        '.o_field_widget[name="sheet_line_ids"] .o_list_renderer',
        '.o_field_widget[name="component_line_ids"] .o_list_renderer'
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
        console.log('No list renderers found for multisheet wizard selectors.');
        return;
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

// Add autocomplete dropdown for primary key column selection
function addPrimaryKeyAutocomplete() {
    console.log('\n=== PRIMARY KEY AUTOCOMPLETE: Starting setup ===');

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
        console.log(`Selector "${selector}" found ${pkInputs.length} elements`);
        if (pkInputs.length > 0) {
            break;
        }
    }

    // Fallback: Search for any input in the primary_key_column_name column
    if (pkInputs.length === 0) {
        console.log('No inputs found with standard selectors. Searching in table rows...');
        const availableSheetTable = document.querySelector('.o_field_widget[name="available_sheet_ids"] table');
        if (availableSheetTable) {
            // Find all rows
            const rows = availableSheetTable.querySelectorAll('tbody tr');
            console.log(`Found ${rows.length} table rows to search`);

            // For each row, find inputs (Odoo renders inputs dynamically in editable tree)
            rows.forEach((row, idx) => {
                const inputs = row.querySelectorAll('input[type="text"]');
                console.log(`Row ${idx}: Found ${inputs.length} text inputs`);
                inputs.forEach((inp, i) => {
                    console.log(`  Input ${i}: name="${inp.name}", id="${inp.id}", class="${inp.className}"`);
                });
            });
        }
    }

    console.log(`Total primary key input fields found: ${pkInputs.length}`);

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
            console.log(`Input ${index}: No parent row found`);
            return;
        }

        // Find the available_column_names hidden field in the same row
        const availableColsInput = row.querySelector('input[name="available_column_names"]');
        if (!availableColsInput || !availableColsInput.value) {
            console.log(`Input ${index}: No available columns data found`);
            return;
        }

        // Parse available columns JSON
        let availableColumns = [];
        try {
            availableColumns = JSON.parse(availableColsInput.value);
            console.log(`Input ${index}: Found ${availableColumns.length} available columns:`, availableColumns);
        } catch (e) {
            console.warn(`Input ${index}: Failed to parse available columns:`, e);
            return;
        }

        if (availableColumns.length === 0) {
            console.log(`Input ${index}: No columns available for this sheet`);
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

        console.log(`✓ Input ${index}: Autocomplete setup complete with ${availableColumns.length} options`);
    });

    console.log('=== PRIMARY KEY AUTOCOMPLETE: Setup complete ===\n');

    // Also set up click event listener for cells that will trigger inline editing
    setupCellClickListener();
}

// Setup click listener for primary key column cells to add autocomplete when editing starts
function setupCellClickListener() {
    console.log('Setting up click listeners for primary key column cells...');

    const availableSheetTable = document.querySelector('.o_field_widget[name="available_sheet_ids"] table');
    if (!availableSheetTable) {
        console.log('Table not found, will retry later');
        return;
    }

    // Find all cells in the primary_key_column_name column
    const pkCells = availableSheetTable.querySelectorAll('td[name="primary_key_column_name"]');
    console.log(`Found ${pkCells.length} primary key column cells`);

    pkCells.forEach((cell, index) => {
        // Skip if already has listener
        if (cell.hasAttribute('data-click-listener-setup')) {
            return;
        }

        cell.setAttribute('data-click-listener-setup', 'true');

        // Add click listener
        cell.addEventListener('click', function(event) {
            console.log(`Cell ${index} clicked, waiting for input to appear...`);

            // Wait a bit for Odoo to render the input field
            setTimeout(() => {
                const input = cell.querySelector('input');
                if (input) {
                    console.log(`Input appeared in cell ${index}, setting up autocomplete`);
                    setupAutocompleteForInput(input, index);
                } else {
                    console.log(`No input found in cell ${index} after click`);
                }
            }, 100);
        });

        console.log(`✓ Click listener added to cell ${index}`);
    });
}

// Setup autocomplete for a specific input element
function setupAutocompleteForInput(input, index) {
    // Skip if already has autocomplete
    if (input.hasAttribute('data-autocomplete-setup')) {
        console.log(`Input ${index} already has autocomplete`);
        return;
    }

    input.setAttribute('data-autocomplete-setup', 'true');

    // Find the row containing this input
    const row = input.closest('tr');
    if (!row) {
        console.log(`Input ${index}: No parent row found`);
        return;
    }

    // Find the available_column_names hidden field in the same row
    const availableColsInput = row.querySelector('input[name="available_column_names"]');
    if (!availableColsInput || !availableColsInput.value) {
        console.log(`Input ${index}: No available columns data found`);
        return;
    }

    // Parse available columns JSON
    let availableColumns = [];
    try {
        availableColumns = JSON.parse(availableColsInput.value);
        console.log(`Input ${index}: Found ${availableColumns.length} available columns:`, availableColumns);
    } catch (e) {
        console.warn(`Input ${index}: Failed to parse available columns:`, e);
        return;
    }

    if (availableColumns.length === 0) {
        console.log(`Input ${index}: No columns available for this sheet`);
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

    console.log(`✓ Input ${index}: Autocomplete setup complete with ${availableColumns.length} options`);
}

// Main enhancement function
function applyEnhancements() {
    console.log('\n=== APPLYING MULTISHEET ENHANCEMENTS ===');
    removeHtmlTooltips();
    addDualScrollbar();
    addPrimaryKeyAutocomplete();
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

    console.log('✓ MutationObserver started for dynamic content');
}

startObserving();

console.log('=== MULTISHEET ENHANCEMENTS MODULE INITIALIZED ===\n');
