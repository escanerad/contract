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
RENDER = (
    "odoo.addons.contract_sign_oca.models.contract_document."
    "ContractDocument._render_document_pdf"
)


@tagged("post_install", "-at_install")
class TestContractSign(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_notify_force_send=False))
        cls.partner = cls.env["res.partner"].create(
            {"name": "Client Test SL", "email": "client@example.com"}
        )
        cls.company_user = cls.env.ref("base.user_admin")
        Template = cls.env["contract.document.template"]
        cls.doc_template = Template.create(
            {
                "name": "Support contract",
                "sequence": 1,
                "body": '<p>Contract with <t t-out="object.partner_id.name"/>.</p>',
                "sign_company_user_id": cls.company_user.id,
            }
        )
        cls.dpa_template = Template.create(
            {
                "name": "Data processing agreement",
                "sequence": 2,
                "document_type": "document",
                "body": "<p>DPA.</p>",
            }
        )
        cls.addendum_template = Template.create(
            {
                "name": "Addendum",
                "document_type": "addendum",
                "sign_required": False,
                "body": "<p>Addendum.</p>",
            }
        )
        cls.contract_template = cls.env["contract.template"].create(
            {
                "name": "Support",
                "document_template_ids": [
                    (6, 0, (cls.doc_template | cls.dpa_template).ids)
                ],
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Support 30h", "list_price": 1000}
        )
        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "SUP-001",
                "partner_id": cls.partner.id,
                "contract_template_id": cls.contract_template.id,
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

    def _send(self, records=None):
        with patch(RENDER, return_value=FAKE_PDF):
            (records or self.contract).action_send_for_signature()

    def _sign_all(self, documents):
        for request in documents.sign_request_id:
            for signer in request.signer_ids:
                signer.signed_on = fields.Datetime.now()
            request._check_signed()
        self.env.cr.precommit.run()

    def _docs(self):
        main = self.contract.document_ids.filtered(lambda d: d.document_type == "main")
        dpa = self.contract.document_ids.filtered(lambda d: d.document_type == "document")
        return main, dpa

    def test_required_before_generating(self):
        # The required documents block invoicing even before being created
        self.assertTrue(self.contract.sign_blocked)
        self.assertEqual(self.contract.sign_state, "not_sent")
        self.assertEqual(self.contract.sign_summary, "0 of 2")

    def test_send_all_documents_one_mail(self):
        Message = self.env["mail.message"]
        before = Message.search([("partner_ids", "in", self.partner.ids)])
        self._send()
        main, dpa = self._docs()
        # One signature request per document
        self.assertTrue(main.sign_request_id and dpa.sign_request_id)
        self.assertNotEqual(main.sign_request_id, dpa.sign_request_id)
        self.assertEqual((main.state, dpa.state), ("issued", "issued"))
        self.assertEqual(self.contract.sign_state, "sent")
        self.assertEqual(main.sign_request_id.record_ref, main)
        self.assertEqual(
            set(main.sign_request_id.signer_ids.partner_id.ids),
            {self.partner.id, self.company_user.partner_id.id},
        )
        self.assertEqual(dpa.sign_request_id.signer_ids.partner_id, self.partner)
        items = list(main.sign_request_id.signatory_data.values())
        # Signature boxes on the last page of the PDF
        self.assertTrue(all(item["page"] == 2 for item in items))
        # A single e-mail to the customer, with the links of both documents
        mails = Message.search([("partner_ids", "in", self.partner.ids)]) - before
        to_sign = mails.filtered(lambda m: "Documents to sign" in (m.subject or ""))
        self.assertEqual(len(to_sign), 1)
        for document in main | dpa:
            signer = document.sign_request_id.signer_ids.filtered(
                lambda s: s.partner_id == self.partner
            )
            self.assertIn(signer.access_url, to_sign.body)
        with self.assertRaises(UserError):
            self._send(main)

    def test_signed_one_by_one_and_invoicing(self):
        Contract = self.env["contract.contract"]
        domain = Contract._get_contracts_to_invoice_domain("2026-01-31")
        self.assertNotIn(self.contract, Contract.search(domain))
        self._send()
        main, dpa = self._docs()
        self._sign_all(main)
        self.assertEqual(main.sign_state, "signed")
        self.assertTrue(main.signed_on)
        self.assertEqual(main.signed_attachment_id.raw.content, main.sign_request_id.data.content)
        # The DPA is required too: still blocked
        self.assertTrue(self.contract.sign_blocked)
        self.assertEqual(self.contract.sign_summary, "1 of 2")
        self.assertNotIn(self.contract, Contract.search(domain))
        self._sign_all(dpa)
        self.assertFalse(self.contract.sign_blocked)
        self.assertEqual(self.contract.sign_state, "signed")
        self.assertIn(self.contract, Contract.search(domain))

    def test_addendum_does_not_block(self):
        self._send()
        main, dpa = self._docs()
        self._sign_all(main | dpa)
        addendum = self.env["contract.document"].create(
            {
                "contract_id": self.contract.id,
                "template_id": self.addendum_template.id,
                "parent_id": main.id,
            }
        )
        self.assertFalse(addendum.sign_required)
        self._send(addendum)
        # Sent but not required: the contract is still invoiced
        self.assertFalse(self.contract.sign_blocked)
        self.assertEqual(self.contract.sign_summary, "2 of 3")
        self._sign_all(addendum)
        self.assertEqual(self.contract.sign_summary, "3 of 3")
        # Recorded as a contract modification
        self.assertIn(addendum.name, " ".join(self.contract.modification_ids.mapped("description")))

    def test_not_required_document(self):
        self.contract.document_template_ids = self.doc_template
        self.contract.action_generate_documents()
        main = self.contract.document_ids
        self.assertTrue(self.contract.sign_blocked)
        main.sign_required = False
        self.assertFalse(self.contract.sign_blocked)

    def test_cancel_signature(self):
        self._send()
        main, _dpa = self._docs()
        main.action_cancel_signature()
        self.assertEqual(main.sign_state, "cancel")
        self.assertEqual(main.state, "draft")
        # It can be regenerated and sent again
        main.action_generate()
        self._send(main)
        self.assertEqual(main.sign_state, "sent")

    def test_document_without_contract(self):
        nda = self.env["contract.document"].create(
            {"partner_id": self.partner.id, "template_id": self.dpa_template.id}
        )
        self._send(nda)
        self.assertEqual(nda.sign_state, "sent")
        self._sign_all(nda)
        self.assertEqual(nda.sign_state, "signed")
        self.assertIn(
            "has been signed", self.partner.message_ids[:1].body or ""
        )

    def test_missing_email(self):
        self.partner.email = False
        with self.assertRaises(UserError):
            self._send()

    def test_portal_documents(self):
        self.assertFalse(self.contract._get_portal_documents())
        self._send()
        main, dpa = self._docs()
        items = dict(self.contract._get_portal_documents())
        self.assertEqual(items[main].partner_id, self.partner)
        self._sign_all(main)
        items = dict(self.contract._get_portal_documents())
        self.assertFalse(items[main])
        self.assertTrue(items[dpa])
