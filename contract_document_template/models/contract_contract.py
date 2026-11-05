# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class ContractContract(models.Model):
    _inherit = "contract.contract"

    document_template_id = fields.Many2one(
        "contract.document.template",
        string="Document template",
        compute="_compute_document_template_id",
        store=True,
        readonly=False,
        tracking=True,
    )
    document_html = fields.Html(
        string="Contract document",
        copy=False,
        sanitize="email_outgoing",
        help="Legal text of this contract. Generated from the document template "
        "and frozen: later changes on the template do not alter it.",
    )
    document_date = fields.Datetime(string="Document generated on", copy=False)
    document_locked = fields.Boolean(
        copy=False,
        help="The document has been issued (e.g. sent for signature) and "
        "cannot be regenerated nor edited anymore.",
    )

    @api.depends("contract_template_id")
    def _compute_document_template_id(self):
        for contract in self:
            if contract.contract_template_id.document_template_id:
                contract.document_template_id = (
                    contract.contract_template_id.document_template_id
                )

    def _check_document_unlocked(self):
        locked = self.filtered("document_locked")
        if locked:
            raise UserError(
                self.env._(
                    "The document of %(contracts)s has already been issued and "
                    "cannot be modified.",
                    contracts=", ".join(locked.mapped("display_name")),
                )
            )

    def action_generate_document(self):
        self._check_document_unlocked()
        for contract in self:
            if not contract.document_template_id:
                raise UserError(
                    self.env._(
                        "Set a document template on contract %(name)s first.",
                        name=contract.display_name,
                    )
                )
            contract.write(
                {
                    "document_html": contract.document_template_id._render_contract_document(
                        contract
                    ),
                    "document_date": fields.Datetime.now(),
                }
            )
        return True

    def action_print_document(self):
        self.ensure_one()
        if not self.document_html:
            self.action_generate_document()
        return self.env.ref(
            "contract_document_template.report_contract_document"
        ).report_action(self)

    def write(self, vals):
        if "document_html" in vals and not self.env.context.get(
            "contract_document_force_write"
        ):
            self._check_document_unlocked()
        return super().write(vals)
