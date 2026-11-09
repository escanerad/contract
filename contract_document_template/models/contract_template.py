# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractTemplate(models.Model):
    _inherit = "contract.template"

    document_template_ids = fields.Many2many(
        "contract.document.template",
        "contract_template_document_template_rel",
        "contract_template_id",
        "document_template_id",
        string="Documents",
        domain=[("document_type", "!=", "addendum")],
        help="Documents generated for the contracts created from this template "
        "(e.g. the service contract, the non-disclosure agreement and the data "
        "processing agreement), each one signed separately.",
    )
