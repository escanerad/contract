# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractDocumentClause(models.Model):
    """Reusable clause (confidentiality, data protection, SLA, termination...)
    that can be included in several contract document templates."""

    _name = "contract.document.clause"
    _inherit = ["mail.render.mixin"]
    _description = "Contract Document Clause"
    _order = "sequence, id"

    name = fields.Char(string="Title", required=True, translate=True)
    sequence = fields.Integer(default=10)
    numbered = fields.Boolean(
        default=True,
        help="Print the clause with its number. Unnumbered clauses (appendices, "
        "signature notes...) keep their title only and do not count.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    body = fields.Html(
        render_engine="qweb",
        render_options={"post_process": True},
        translate=True,
        sanitize="email_outgoing",
        help="Clause text. The contract is available as 'object', e.g. "
        '<t t-out="object.partner_id.name"/>.',
    )

    def _compute_render_model(self):
        self.render_model = "contract.contract"
