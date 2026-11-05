# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Contract Document Templates",
    "summary": "Legal document templates and reusable clauses for contracts, "
    "rendered with the contract data and frozen once issued",
    "version": "20.0.1.0.0",
    "category": "Contract Management",
    "license": "AGPL-3",
    "author": "ESCÀNER Serveis TIC, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/contract",
    "depends": ["contract", "mail"],
    "data": [
        "security/ir.access.csv",
        "report/contract_document_report.xml",
        "views/contract_document_clause_views.xml",
        "views/contract_document_template_views.xml",
        "views/contract_template_views.xml",
        "views/contract_contract_views.xml",
    ],
    "development_status": "Alpha",
    "installable": True,
}
