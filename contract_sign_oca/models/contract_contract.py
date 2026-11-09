# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

CONTRACT_SIGN_STATES = [
    ("not_sent", "Not sent"),
    ("sent", "Pending signature"),
    ("signed", "Signed"),
]


class ContractContract(models.Model):
    _inherit = "contract.contract"

    sign_state = fields.Selection(
        CONTRACT_SIGN_STATES,
        string="Signature",
        compute="_compute_sign_state",
        store=True,
        help="Signature of the documents required to invoice the contract.",
    )
    sign_blocked = fields.Boolean(
        string="Pending required signatures",
        compute="_compute_sign_state",
        store=True,
        help="A document required to invoice the contract is not signed yet: "
        "the contract is not invoiced.",
    )
    sign_summary = fields.Char(string="Signed documents", compute="_compute_sign_state", store=True)

    @api.depends(
        "document_ids.sign_state",
        "document_ids.sign_required",
        "document_ids.state",
        "document_template_ids.sign_required",
    )
    def _compute_sign_state(self):
        for contract in self:
            documents = contract.document_ids.filtered(lambda d: d.state != "cancel")
            required = documents.filtered("sign_required")
            # Required documents not even created yet also block
            missing = contract.document_template_ids.filtered("sign_required") - (
                documents.template_id
            )
            to_sign = documents.filtered(
                lambda d: d.sign_required or d.sign_state in ("sent", "signed")
            )
            signed = to_sign.filtered(lambda d: d.sign_state == "signed")
            contract.sign_blocked = bool(
                missing or required.filtered(lambda d: d.sign_state != "signed")
            )
            if not to_sign and not missing:
                contract.sign_state = False
                contract.sign_summary = False
                continue
            if not contract.sign_blocked and signed:
                contract.sign_state = "signed"
            elif any(d.sign_state == "sent" for d in to_sign):
                contract.sign_state = "sent"
            else:
                contract.sign_state = "not_sent"
            contract.sign_summary = self.env._(
                "%(signed)s of %(total)s",
                signed=len(signed),
                total=len(to_sign) + len(missing),
            )

    def action_send_for_signature(self):
        """Send all the documents of the contract not signed nor sent yet."""
        for contract in self:
            contract.action_generate_documents()
            documents = contract.document_ids.filtered(
                lambda d: d.state != "cancel" and d.sign_state in ("not_sent", "cancel")
            )
            if not documents:
                raise UserError(
                    self.env._(
                        "Contract %(name)s has no documents to send for signature.",
                        name=contract.display_name,
                    )
                )
            documents.action_send_for_signature()
        return True

    # ------------------------------------------------------------------
    # Invoicing: not until the required documents are signed
    # ------------------------------------------------------------------
    @api.model
    def _get_contracts_to_invoice_domain(self, date_ref=None):
        domain = super()._get_contracts_to_invoice_domain(date_ref=date_ref)
        return Domain.AND([domain, [("sign_blocked", "=", False)]])

    def _get_portal_documents(self):
        """(document, pending signer of the customer) of the contract, for the
        portal."""
        self.ensure_one()
        documents = self.sudo().document_ids.filtered(
            lambda d: d.state != "cancel" and d.sign_state in ("sent", "signed")
        )
        return [(document, document._get_portal_pending_signer()) for document in documents]
