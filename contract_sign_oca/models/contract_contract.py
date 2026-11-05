# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from io import BytesIO

from pypdf import PdfReader

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.binary import BinaryBytes

SIGN_STATES = [
    ("not_sent", "Not sent"),
    ("sent", "Sent for signature"),
    ("signed", "Signed"),
    ("cancel", "Signature cancelled"),
]
REQUEST_STATE_MAP = {
    "1_draft": "not_sent",
    "0_sent": "sent",
    "2_signed": "signed",
    "3_cancel": "cancel",
}


class ContractContract(models.Model):
    _inherit = "contract.contract"

    sign_request_id = fields.Many2one(
        "sign.oca.request", string="Signature request", copy=False, readonly=True
    )
    sign_state = fields.Selection(
        SIGN_STATES,
        string="Signature",
        compute="_compute_sign_state",
        store=True,
        tracking=True,
    )
    signed_on = fields.Datetime(copy=False, readonly=True)
    signed_attachment_id = fields.Many2one(
        "ir.attachment", string="Signed document", copy=False, readonly=True
    )
    sign_required = fields.Boolean(
        string="Signature required",
        compute="_compute_sign_required",
        store=True,
        readonly=False,
        help="If set, the contract is not invoiced until it is signed.",
    )

    @api.depends("sign_request_id.state")
    def _compute_sign_state(self):
        for contract in self:
            contract.sign_state = REQUEST_STATE_MAP.get(
                contract.sign_request_id.state, "not_sent"
            )

    @api.depends("document_template_id")
    def _compute_sign_required(self):
        for contract in self:
            contract.sign_required = bool(contract.document_template_id.sign_required)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _render_document_pdf(self):
        self.ensure_one()
        pdf, _fmt = self.env["ir.actions.report"]._render_qweb_pdf(
            "contract_document_template.report_contract_document", self.ids
        )
        return pdf

    def _get_sign_signers(self):
        """Return a list of (partner, role, position_x, position_y)."""
        self.ensure_one()
        template = self.document_template_id
        signers = [
            (
                self.partner_id,
                self.env.ref("sign_oca.sign_role_customer"),
                template.sign_partner_position_x,
                template.sign_partner_position_y,
            )
        ]
        if template.sign_company_user_id:
            signers.append(
                (
                    template.sign_company_user_id.partner_id,
                    self.env.ref("contract_sign_oca.sign_role_company"),
                    template.sign_company_position_x,
                    template.sign_company_position_y,
                )
            )
        return signers

    def _prepare_sign_request_vals(self, pdf):
        self.ensure_one()
        template = self.document_template_id
        last_page = len(PdfReader(BytesIO(pdf)).pages)
        signature_field = self.env.ref("sign_oca.sign_field_signature")
        signatory_data = {}
        signer_vals = []
        for item_id, (partner, role, pos_x, pos_y) in enumerate(
            self._get_sign_signers(), start=1
        ):
            signatory_data[str(item_id)] = {
                "id": item_id,
                "tabindex": item_id,
                "field_id": signature_field.id,
                "name": signature_field.name,
                "field_type": "signature",
                "role_id": role.id,
                "page": last_page,
                "position_x": pos_x,
                "position_y": pos_y,
                "width": template.sign_box_width,
                "height": template.sign_box_height,
                "placeholder": partner.name,
                "required": True,
                "value": False,
                "default_value": False,
            }
            signer_vals.append(
                fields.Command.create({"partner_id": partner.id, "role_id": role.id})
            )
        filename = f"{self.name or 'contract'}.pdf".replace("/", "-")
        return {
            "name": self.env._("Contract %(name)s", name=self.name),
            "data": BinaryBytes(pdf, filename),
            "filename": filename,
            "record_ref": f"{self._name},{self.id}",
            "signatory_data": signatory_data,
            "signer_ids": signer_vals,
            "company_id": self.company_id.id,
        }

    def action_send_for_signature(self):
        for contract in self:
            if not contract.document_template_id:
                raise UserError(
                    self.env._(
                        "Set a document template on contract %(name)s first.",
                        name=contract.display_name,
                    )
                )
            if contract.sign_state in ("sent", "signed"):
                raise UserError(
                    self.env._(
                        "Contract %(name)s has already been sent for signature.",
                        name=contract.display_name,
                    )
                )
            if not contract.partner_id.email:
                raise UserError(
                    self.env._(
                        "The customer of %(name)s has no e-mail address.",
                        name=contract.display_name,
                    )
                )
            if not contract.document_html:
                contract.action_generate_document()
            pdf = contract._render_document_pdf()
            request = self.env["sign.oca.request"].create(
                contract._prepare_sign_request_vals(pdf)
            )
            contract.write({"sign_request_id": request.id, "document_locked": True})
            request.action_send(message=contract.document_template_id.sign_message or "")
            contract.message_post(
                body=self.env._(
                    "Contract sent for signature to %(signers)s.",
                    signers=", ".join(request.signer_ids.partner_id.mapped("name")),
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_cancel_signature(self):
        for contract in self.filtered(lambda c: c.sign_state == "sent"):
            contract.sign_request_id.sudo().state = "3_cancel"
            # The document may be regenerated and sent again
            contract.document_locked = False
        return True

    def action_view_sign_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sign.oca.request",
            "res_id": self.sign_request_id.id,
            "view_mode": "form",
        }

    # ------------------------------------------------------------------
    # Signed
    # ------------------------------------------------------------------
    def _on_sign_request_signed(self, request):
        """Called by sign.oca.request when all the signers have signed."""
        signed_on = max(request.signer_ids.mapped("signed_on"), default=False)
        self.write({"signed_on": signed_on or fields.Datetime.now()})
        # Attach the final PDF at the end of the transaction, so that any
        # other module post-processing the signed PDF in _check_signed (e.g.
        # l10n_ad_sign PAdES seal) has already done it, whatever the MRO.
        contracts = self
        self.env.cr.precommit.add(lambda: contracts._attach_signed_document(request))

    def _attach_signed_document(self, request):
        for contract in self.exists():
            attachment = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": f"{contract.name or 'contract'} - signed.pdf".replace(
                            "/", "-"
                        ),
                        "raw": request.data.content,
                        "mimetype": "application/pdf",
                        "res_model": contract._name,
                        "res_id": contract.id,
                    }
                )
            )
            contract.sudo().signed_attachment_id = attachment
            contract.message_post(
                body=self.env._("The contract has been signed by all the parties."),
                attachment_ids=attachment.ids,
                subtype_xmlid="mail.mt_comment",
            )

    # ------------------------------------------------------------------
    # Invoicing: only signed contracts, when required
    # ------------------------------------------------------------------
    @api.model
    def _get_contracts_to_invoice_domain(self, date_ref=None):
        domain = super()._get_contracts_to_invoice_domain(date_ref=date_ref)
        return Domain.AND(
            [
                domain,
                ["|", ("sign_required", "=", False), ("sign_state", "=", "signed")],
            ]
        )

    def _get_portal_pending_signer(self):
        """Pending signer of the contract customer, for the portal button."""
        self.ensure_one()
        if self.sign_state != "sent":
            return self.env["sign.oca.request.signer"]
        commercial = self.partner_id.commercial_partner_id
        return self.sign_request_id.sudo().signer_ids.filtered(
            lambda s: not s.signed_on
            and s.partner_id.commercial_partner_id == commercial
        )[:1]
