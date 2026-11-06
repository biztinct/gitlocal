/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { PbSidebar } from "@pb_sidebar/js/pb_sidebar";

patch(WebClient, {
    components: {
        ...WebClient.components,
        PbSidebar,
    },
});
