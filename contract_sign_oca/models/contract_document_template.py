# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractDocumentTemplate(models.Model):
    _inherit = "contract.document.template"

    sign_required = fields.Boolean(
        string="Signature required",
        default=True,
        help="Contracts using this template are not invoiced until signed.",
    )
    sign_company_user_id = fields.Many2one(
        "res.users",
        string="Company signer",
        help="Representative who signs on behalf of the company. Leave empty "
        "if only the customer signs.",
    )
    sign_message = fields.Text(
        string="Signature request message",
        translate=True,
        help="Text included in the e-mail sent to the signers.",
    )
    # Positions of the signature boxes on the LAST page (signature page), in
    # percentage of the page, as used by sign_oca.
    sign_partner_position_x = fields.Float(default=54.0)
    sign_partner_position_y = fields.Float(default=30.0)
    sign_company_position_x = fields.Float(default=8.0)
    sign_company_position_y = fields.Float(default=30.0)
    sign_box_width = fields.Float(default=38.0)
    sign_box_height = fields.Float(default=12.0)
