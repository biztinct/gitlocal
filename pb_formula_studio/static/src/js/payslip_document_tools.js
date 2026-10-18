/** @odoo-module **/

// Geometry only: no tenant codes, payroll arithmetic or browser dependencies.
export function documentField(id, label, x, y, w, h) {
    return { id, label, x, y, w, h, binding: 'blank', rule_id: false, meta_key: '', text: '',
        format: 'number', decimals: 0, currency: '', font: 'serif', font_size: 10,
        bold: false, italic: false, align: 'right', color: '#111111', background: '#ffffff',
        cover: true, empty: '—', rate_rule_id: false, rate_operation: 'divide' };
}

function groups(values, gap = 2) {
    const result = [];
    for (const value of values) {
        const last = result[result.length - 1];
        if (last && value - last[last.length - 1] <= gap) last.push(value);
        else result.push([value]);
    }
    return result.map(group => group.reduce((a, b) => a + b, 0) / group.length);
}

export function detectDocumentCells(pixels, width, height, pageWidth, pageHeight, items = [], pageNo = 1) {
    // Long dark rules locate table bands. Vertical rules are measured INSIDE
    // each band, so merged headings and unequal column widths are preserved.
    const dark = (x, y) => {
        const p = (Math.round(y) * width + Math.round(x)) * 4;
        return pixels[p] < 110 && pixels[p + 1] < 110 && pixels[p + 2] < 110;
    };
    const horizontal = [];
    for (let y = 0; y < height; y++) {
        let run = 0, longest = 0;
        for (let x = 0; x < width; x++) {
            run = dark(x, y) ? run + 1 : 0;
            longest = Math.max(longest, run);
        }
        if (longest > width * .30) horizontal.push(y);
    }
    const ys = groups(horizontal, 3);
    const sx = pageWidth / width, sy = pageHeight / height;
    const cells = [], fields = [];
    let section = '';
    for (let band = 0; band < ys.length - 1; band++) {
        const top = ys[band], bottom = ys[band + 1];
        if (bottom - top < 7 || bottom - top > height * .2) continue;
        const xs = [];
        for (let x = 0; x < width; x++) {
            let count = 0, total = 0;
            for (let y = Math.ceil(top) + 2; y <= Math.floor(bottom) - 2; y++) {
                total++;
                if (dark(x, y)) count++;
            }
            if (total && count / total > .82) xs.push(x);
        }
        const boundaries = groups(xs, 3);
        if (boundaries.length < 2 || boundaries.length > 14) continue;
        const row = [];
        for (let col = 0; col < boundaries.length - 1; col++) {
            const left = boundaries[col], right = boundaries[col + 1];
            if (right - left < 10) continue;
            const textItems = items.filter(item => item.x >= left * sx - 1 && item.x < right * sx - 1
                && item.y > top * sy + 1 && item.y < bottom * sy + 1);
            textItems.sort((a, b) => Math.abs(a.y - b.y) < 3 ? a.x - b.x : a.y - b.y);
            const text = textItems.map(item => item.text).join(' ').trim();
            row.push({ x: left * sx, y: top * sy, w: (right - left) * sx,
                h: (bottom - top) * sy, text, items: textItems });
        }
        cells.push(...row);
        if (row.length === 1) {
            section = row[0].text;
            continue;
        }
        // A label/value pair is identified by label-like text followed by a
        // blank, dash or source value. The source value is covered, never used.
        for (let col = 0; col < row.length - 1; col++) {
            const label = row[col], value = row[col + 1];
            if (!/[A-Za-zÀ-ỹ]{2}/.test(label.text)) continue;
            const valueLooksLikeLabel = /[A-Za-zÀ-ỹ]{3}/.test(value.text) && /\b(salary|allowance|insurance|employee|days|thuế|lương)\b/i.test(value.text);
            if (valueLooksLikeLabel) continue;
            const field = documentField(`p${pageNo}-f${fields.length + 1}`, label.text,
                value.x + 1, value.y + 1, value.w - 2, value.h - 2);
            field.section = section;
            field.font_size = Math.min(11, Math.max(7, label.items[0]?.font_size || 10));
            // Sample an empty interior point: retain the green net-pay fill.
            const px = Math.min(width - 1, Math.round((value.x + value.w - 4) / sx));
            const py = Math.min(height - 1, Math.round((value.y + value.h - 3) / sy));
            const p = (py * width + px) * 4;
            if (pixels[p] > 130 && pixels[p + 1] > 130 && pixels[p + 2] > 130) {
                field.background = '#' + [pixels[p], pixels[p + 1], pixels[p + 2]]
                    .map(n => n.toString(16).padStart(2, '0')).join('');
            }
            fields.push(field);
            col++;
        }
    }
    // Replace a dated title as one editable text field with period tokens.
    const titleItems = items.filter(item => /payslip|pay slip|phiếu lương/i.test(item.text)
        && item.y < (cells[0]?.y || pageHeight * .30));
    if (titleItems.length) {
        const anchor = titleItems[0];
        const line = items.filter(item => Math.abs(item.y - anchor.y) < 4).sort((a, b) => a.x - b.x);
        let title = line.map(item => item.text).join(' ').trim();
        if (/20\d{2}/.test(title)) {
            title = title.replace(/(THÁNG\s*)\d{1,2}/i, '$1{{pb_meta:month}}')
                .replace(/\b20\d{2}\b/g, '{{pb_meta:year}}')
                .replace(/\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\b/gi, '{{pb_meta:month_name}}');
            const size = Math.max(...line.map(item => item.font_size || 14));
            const field = documentField(`p${pageNo}-title`, 'Payslip period title', 30,
                anchor.y - size - 1, pageWidth - 60, size * 1.7);
            Object.assign(field, { binding: 'text', text: title, font_size: size,
                bold: true, italic: false, align: 'center' });
            fields.push(field);
        }
    }
    return { fields, cellCount: cells.length };
}

export function documentIssues(document) {
    const issues = [];
    for (const [pageIndex, page] of document.pages.entries()) {
        for (const field of page.fields) {
            if (field.binding === 'blank') issues.push(`Page ${pageIndex + 1}: ${field.label} has no live source`);
            if (field.x < 0 || field.y < 0 || field.x + field.w > page.width + .1 || field.y + field.h > page.height + .1) {
                issues.push(`Page ${pageIndex + 1}: ${field.label} is outside the page`);
            }
        }
    }
    return issues;
}
