# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractTemplate(models.Model):
    _inherit = "contract.template"

    document_template_id = fields.Many2one(
        "contract.document.template",
        string="Document template",
        help="Legal text used by the contracts created from this template.",
    )
