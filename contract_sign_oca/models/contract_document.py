# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict
from io import BytesIO

from pypdf import PdfReader

from odoo import api, fields, models
from odoo.exceptions import UserError
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


class ContractDocument(models.Model):
    _inherit = "contract.document"

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
        string="Required to invoice",
        compute="_compute_sign_required",
        store=True,
        readonly=False,
        precompute=True,
        help="The contract is not invoiced until this document is signed.",
    )

    @api.depends("sign_request_id.state")
    def _compute_sign_state(self):
        for document in self:
            document.sign_state = REQUEST_STATE_MAP.get(
                document.sign_request_id.state, "not_sent"
            )

    @api.depends("template_id")
    def _compute_sign_required(self):
        for document in self:
            document.sign_required = bool(document.template_id.sign_required)

    def _check_can_reset(self):
        if any(document.sign_state == "signed" for document in self):
            raise UserError(self.env._("A signed document cannot be reset to draft."))
        return super()._check_can_reset()

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
        template = self.template_id
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
        template = self.template_id
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
        filename = f"{self.name} - {self.title or ''}.pdf".replace("/", "-")
        return {
            "name": self.display_name,
            "data": BinaryBytes(pdf, filename),
            "filename": filename,
            "record_ref": f"{self._name},{self.id}",
            "signatory_data": signatory_data,
            "signer_ids": signer_vals,
            "company_id": self.company_id.id,
        }

    def _check_can_send(self):
        for document in self:
            if document.state == "cancel":
                raise UserError(
                    self.env._(
                        "Document %(name)s is cancelled.", name=document.display_name
                    )
                )
            if document.sign_state in ("sent", "signed"):
                raise UserError(
                    self.env._(
                        "Document %(name)s has already been sent for signature.",
                        name=document.display_name,
                    )
                )
            if not document.partner_id.email:
                raise UserError(
                    self.env._(
                        "The partner of %(name)s has no e-mail address.",
                        name=document.display_name,
                    )
                )

    def action_send_for_signature(self):
        """Send the documents for signature: one signature request per
        document, and one e-mail per signer listing all its documents."""
        self._check_can_send()
        requests = self.env["sign.oca.request"]
        for document in self:
            if document.state == "draft" and not document.document_html:
                document.action_generate()
            pdf = document._render_document_pdf()
            request = (
                self.env["sign.oca.request"]
                .with_context(contract_sign_silent=True)
                .create(document._prepare_sign_request_vals(pdf))
            )
            document.write({"sign_request_id": request.id})
            document.action_issue()
            request.with_context(contract_sign_silent=True).action_send()
            requests |= request
            document.message_post(
                body=self.env._(
                    "Sent for signature to %(signers)s.",
                    signers=", ".join(request.signer_ids.partner_id.mapped("name")),
                ),
                subtype_xmlid="mail.mt_note",
            )
        self._notify_signers(requests)
        for contract in self.contract_id:
            documents = self.filtered(lambda d, c=contract: d.contract_id == c)
            contract.message_post(
                body=self.env._(
                    "Documents sent for signature: %(documents)s.",
                    documents=", ".join(documents.mapped("display_name")),
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _notify_signers(self, requests):
        """One e-mail per signer with the links of all its documents."""
        by_partner = defaultdict(lambda: self.env["sign.oca.request.signer"])
        for signer in requests.signer_ids:
            by_partner[signer.partner_id] |= signer
        messages = [m for m in dict.fromkeys(self.template_id.mapped("sign_message")) if m]
        contracts = self.contract_id
        subject = (
            self.env._("Documents to sign: %(contract)s", contract=contracts[0].name)
            if len(contracts) == 1
            else self.env._("Documents to sign")
        )
        for partner, signers in by_partner.items():
            body = self.env["ir.qweb"]._render(
                "contract_sign_oca.mail_documents_to_sign",
                {
                    "partner": partner,
                    "signers": signers,
                    "messages": messages,
                    "documents": {
                        signer: self.filtered(
                            lambda d, s=signer: d.sign_request_id == s.request_id
                        )
                        for signer in signers
                    },
                },
                minimal_qcontext=True,
            )
            self.env["mail.thread"].message_notify(
                body=body,
                partner_ids=partner.ids,
                subject=subject,
                subtype_id=self.env.ref("mail.mt_comment").id,
                mail_auto_delete=False,
                email_layout_xmlid="mail.mail_notification_light",
            )

    def action_cancel_signature(self):
        for document in self.filtered(lambda d: d.sign_state == "sent"):
            document.sign_request_id.sudo().state = "3_cancel"
            # The document may be regenerated and sent again
            document.state = "draft"
        return True

    def action_cancel(self):
        self.action_cancel_signature()
        return super().action_cancel()

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
        # Record the signed addenda as contract modifications
        for document in self.filtered(
            lambda d: d.document_type == "addendum" and d.contract_id
        ):
            self.env["contract.modification"].with_context(
                skip_modification_mail=True
            ).create(
                {
                    "contract_id": document.contract_id.id,
                    "date": fields.Date.context_today(self, document.signed_on),
                    "description": self.env._(
                        "Addendum %(name)s signed", name=document.display_name
                    ),
                }
            )
        # Attach the final PDF at the end of the transaction, so that any
        # other module post-processing the signed PDF in _check_signed (e.g.
        # l10n_ad_sign PAdES seal) has already done it, whatever the MRO.
        documents = self
        self.env.cr.precommit.add(lambda: documents._attach_signed_document(request))

    def _attach_signed_document(self, request):
        for document in self.exists():
            attachment = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": f"{document.name} - {document.title or ''} - signed.pdf".replace(
                            "/", "-"
                        ),
                        "raw": request.data.content,
                        "mimetype": "application/pdf",
                        "res_model": document._name,
                        "res_id": document.id,
                    }
                )
            )
            document.sudo().signed_attachment_id = attachment
            body = self.env._(
                "%(document)s has been signed by all the parties.",
                document=document.display_name,
            )
            document.message_post(body=body, subtype_xmlid="mail.mt_note")
            (document.contract_id or document.partner_id).message_post(
                body=body,
                attachment_ids=attachment.copy({
                    "res_model": (document.contract_id or document.partner_id)._name,
                    "res_id": (document.contract_id or document.partner_id).id,
                }).ids,
                subtype_xmlid="mail.mt_comment",
            )

    # ------------------------------------------------------------------
    # Portal
    # ------------------------------------------------------------------
    def _get_portal_pending_signer(self):
        """Pending signer of the document partner, for the portal button."""
        self.ensure_one()
        if self.sign_state != "sent":
            return self.env["sign.oca.request.signer"]
        commercial = self.partner_id.commercial_partner_id
        return self.sign_request_id.sudo().signer_ids.filtered(
            lambda s: not s.signed_on
            and s.partner_id.commercial_partner_id == commercial
        )[:1]
