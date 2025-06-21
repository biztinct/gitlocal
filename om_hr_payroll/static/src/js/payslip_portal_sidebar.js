odoo.define('om_hr_payroll.PayslipPortalSidebar', function (require) {
    'use strict';
    
    const dom = require('web.dom');
    var publicWidget = require('web.public.widget');
    var PortalSidebar = require('portal.PortalSidebar');
    var utils = require('web.utils');
    
    publicWidget.registry.PayslipPortalSidebar = PortalSidebar.extend({
        selector: '.o_portal_payslip_sidebar', // Changed selector
        events: {
            'click .o_portal_invoice_print': '_onPrintPayslip', // Changed event name
        },
    
        /**
         * @override
         */
        start: function () {
            var def = this._super.apply(this, arguments);
    
            var $payslipHtml = this.$el.find('iframe#payslip_html'); // Changed selector
            var updateIframeSize = this._updateIframeSize.bind(this, $payslipHtml);
    
            $(window).on('resize', updateIframeSize);
    
            var iframeDoc = $payslipHtml[0].contentDocument || $payslipHtml[0].contentWindow.document;
            if (iframeDoc.readyState === 'complete') {
                updateIframeSize();
            } else {
                $payslipHtml.on('load', updateIframeSize);
            }
    
            return def;
        },
    
        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------
    
        /**
         * Called when the iframe is loaded or the window is resized on customer portal.
         * The goal is to expand the iframe height to display the full report without scrollbar.
         *
         * @private
         * @param {object} $el: the iframe
         */
        _updateIframeSize: function ($el) {
//            var $wrapwrap = $el.contents().find('div#wrapwrap');
            // Set it to 0 first to handle the case where scrollHeight is too big for its content.
//            $el.height(0);
//            $el.height($wrapwrap[0].scrollHeight);
//            $el.height(1000);    
            var $body = $el.contents().find('body'); // Target the <body> of the iframe content
            $el.height(0); // Reset height to avoid potential issues
            $el.height($body[0].scrollHeight); // Set the height to the scrollHeight of the body
        


            // scroll to the right place after iframe resize
            if (!utils.isValidAnchor(window.location.hash)) {
                return;
            }
            var $target = $(window.location.hash);
            if (!$target.length) {
                return;
            }
            dom.scrollTo($target[0], {duration: 0});
        },
    
        /**
         * @private
         * @param {MouseEvent} ev
         */
        _onPrintPayslip: function (ev) { // Changed method name
            ev.preventDefault();
            var href = $(ev.currentTarget).attr('href');
            this._printIframeContent(href);
        },
    });
    });