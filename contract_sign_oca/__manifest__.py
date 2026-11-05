# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Contract Online Signature (sign_oca)",
    "summary": "Send the contract document for online signature by the customer "
    "(and the company) with sign_oca; invoice only signed contracts",
    "version": "20.0.1.0.0",
    "category": "Contract Management",
    "license": "AGPL-3",
    "author": "ESCÀNER Serveis TIC, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "depends": ["contract_document_template", "sign_oca"],
    "data": [
        "data/sign_oca_data.xml",
        "views/contract_document_template_views.xml",
        "views/contract_contract_views.xml",
        "views/contract_portal_templates.xml",
    ],
    "development_status": "Alpha",
    "installable": True,
}
