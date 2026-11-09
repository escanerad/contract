# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Contract Online Signature (sign_oca)",
    "summary": "Send each contract document (contract, separate agreements, "
    "addenda) for online signature with sign_oca; invoice only when the "
    "required documents are signed",
    "version": "20.0.2.0.0",
    "category": "Contract Management",
    "license": "AGPL-3",
    "author": "ESCÀNER Serveis TIC, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "depends": ["contract_document_template", "sign_oca"],
    "data": [
        "data/sign_oca_data.xml",
        "data/mail_templates.xml",
        "views/contract_document_template_views.xml",
        "views/contract_document_views.xml",
        "views/contract_contract_views.xml",
        "views/contract_portal_templates.xml",
    ],
    "development_status": "Alpha",
    "installable": True,
}
