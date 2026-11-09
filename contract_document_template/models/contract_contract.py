# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class ContractContract(models.Model):
    _inherit = "contract.contract"

    document_ids = fields.One2many(
        "contract.document", "contract_id", string="Documents", copy=False
    )
    document_count = fields.Integer(compute="_compute_document_count")
    # contract.contract inherits contract.template: own relation table
    document_template_ids = fields.Many2many(
        "contract.document.template",
        "contract_contract_document_template_rel",
        "contract_id",
        "document_template_id",
        string="Documents to generate",
        compute="_compute_document_template_ids",
        store=True,
        readonly=False,
        domain=[("document_type", "!=", "addendum")],
        help="Documents of this contract, by default those of its contract "
        "template. Each one is generated and signed separately.",
    )

    @api.depends("contract_template_id")
    def _compute_document_template_ids(self):
        for contract in self:
            if contract.contract_template_id.document_template_ids:
                contract.document_template_ids = (
                    contract.contract_template_id.document_template_ids
                )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for contract in self:
            contract.document_count = len(contract.document_ids)

    def _get_missing_document_templates(self):
        """Documents to generate without a (non cancelled) document on the
        contract yet."""
        self.ensure_one()
        existing = self.document_ids.filtered(lambda d: d.state != "cancel").template_id
        return self.document_template_ids - existing

    def action_generate_documents(self):
        """Create the documents of the contract template not created yet and
        (re)generate the text of the draft ones."""
        for contract in self:
            missing = contract._get_missing_document_templates()
            if not missing and not contract.document_ids:
                raise UserError(
                    self.env._(
                        "Contract %(name)s has no documents: add them on the "
                        "Documents tab or set documents on its contract template.",
                        name=contract.display_name,
                    )
                )
            self.env["contract.document"].create(
                [
                    {
                        "contract_id": contract.id,
                        "template_id": template.id,
                        "sequence": template.sequence,
                    }
                    for template in missing.sorted(lambda t: (t.sequence, t.id))
                ]
            )
            contract.document_ids.filtered(lambda d: d.state == "draft").action_generate()
        return True

    def action_view_documents(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "contract_document_template.contract_document_action"
        )
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {
            "default_contract_id": self.id,
            "default_partner_id": self.partner_id.id,
            "default_company_id": self.company_id.id,
        }
        return action
