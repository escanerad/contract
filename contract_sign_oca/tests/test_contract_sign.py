# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from io import BytesIO
from unittest.mock import patch

from pypdf import PdfWriter

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _fake_pdf(pages=2):
    """Blank A4 PDF, so that tests do not depend on wkhtmltopdf."""
    writer = PdfWriter()
    for _i in range(pages):
        writer.add_blank_page(width=595, height=842)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


FAKE_PDF = _fake_pdf()


@tagged("post_install", "-at_install")
class TestContractSign(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Client Test SL", "email": "client@example.com"}
        )
        cls.company_user = cls.env.ref("base.user_admin")
        cls.doc_template = cls.env["contract.document.template"].create(
            {
                "name": "Support contract",
                "body": '<p>Contract with <t t-out="object.partner_id.name"/>.</p>',
                "sign_company_user_id": cls.company_user.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Support 30h", "list_price": 1000}
        )
        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "SUP-001",
                "partner_id": cls.partner.id,
                "document_template_id": cls.doc_template.id,
                "contract_line_ids": [
                    fields.Command.create(
                        {
                            "product_id": cls.product.id,
                            "name": "Support #START# - #END#",
                            "quantity": 1,
                            "price_unit": 1000,
                            "recurring_rule_type": "monthly",
                            "recurring_interval": 1,
                            "date_start": "2026-01-01",
                            "recurring_next_date": "2026-01-01",
                        }
                    )
                ],
            }
        )

    def _send(self):
        with patch(
            "odoo.addons.contract_sign_oca.models.contract_contract."
            "ContractContract._render_document_pdf",
            return_value=FAKE_PDF,
        ):
            self.contract.action_send_for_signature()
        return self.contract.sign_request_id

    def _sign_all(self, request):
        for signer in request.signer_ids:
            signer.signed_on = fields.Datetime.now()
        request._check_signed()
        self.env.cr.precommit.run()

    def test_sign_required_from_template(self):
        self.assertTrue(self.contract.sign_required)
        self.assertEqual(self.contract.sign_state, "not_sent")

    def test_send_for_signature(self):
        request = self._send()
        self.assertTrue(request)
        self.assertEqual(self.contract.sign_state, "sent")
        self.assertTrue(self.contract.document_locked)
        self.assertTrue(self.contract.document_html)
        self.assertEqual(request.record_ref, self.contract)
        self.assertEqual(
            set(request.signer_ids.partner_id.ids),
            {self.partner.id, self.company_user.partner_id.id},
        )
        items = list(request.signatory_data.values())
        self.assertEqual(len(items), 2)
        # Signature boxes on the last page of the PDF
        self.assertTrue(all(item["page"] == 2 for item in items))
        self.assertTrue(all(item["field_type"] == "signature" for item in items))
        with self.assertRaises(UserError):
            self._send()

    def test_signed(self):
        request = self._send()
        self._sign_all(request)
        self.assertEqual(self.contract.sign_state, "signed")
        self.assertTrue(self.contract.signed_on)
        self.assertTrue(self.contract.signed_attachment_id)
        # Odoo 20: binary values are BinaryValue objects; compare the bytes
        self.assertEqual(
            self.contract.signed_attachment_id.raw.content, request.data.content
        )

    def test_cancel_signature(self):
        self._send()
        self.contract.action_cancel_signature()
        self.assertEqual(self.contract.sign_state, "cancel")
        self.assertFalse(self.contract.document_locked)
        # It can be sent again
        self._send()
        self.assertEqual(self.contract.sign_state, "sent")

    def test_invoice_only_signed(self):
        contracts = self.env["contract.contract"]
        domain = contracts._get_contracts_to_invoice_domain("2026-01-31")
        self.assertNotIn(self.contract, contracts.search(domain))
        self.contract.sign_required = False
        self.assertIn(self.contract, contracts.search(domain))
        self.contract.sign_required = True
        request = self._send()
        self._sign_all(request)
        self.assertIn(self.contract, contracts.search(domain))

    def test_missing_email(self):
        self.partner.email = False
        with self.assertRaises(UserError):
            self._send()

    def test_portal_pending_signer(self):
        self.assertFalse(self.contract._get_portal_pending_signer())
        request = self._send()
        signer = self.contract._get_portal_pending_signer()
        self.assertEqual(signer.partner_id, self.partner)
        self._sign_all(request)
        self.assertFalse(self.contract._get_portal_pending_signer())
