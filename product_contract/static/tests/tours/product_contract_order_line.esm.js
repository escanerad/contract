import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("product_contract_order_line", {
    steps: () => [
        {
            content: "The terms of the contract are in the description of the line",
            trigger: ".o_data_row [name='product_and_description']:contains(2026)",
        },
        {
            content: "The contract configuration button uses an Odoo icon",
            trigger: ".o_contract_configuration_button[data-icon='autorenew']",
            run: "click",
        },
        {
            content: "It opens the contract configurator",
            trigger: ".modal .o_form_view",
        },
    ],
});
