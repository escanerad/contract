# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Client Test SL"})
        cls.clause_conf = cls.env["contract.document.clause"].create(
            {
                "name": "Confidentiality",
                "sequence": 20,
                "body": '<p>Both parties, including <t t-out="object.partner_id.name"/>,'
                " keep the information confidential.</p>",
            }
        )
        cls.clause_object = cls.env["contract.document.clause"].create(
            {
                "name": "Object",
                "sequence": 10,
                "body": "<p>IT support services.</p>",
            }
        )
        cls.doc_template = cls.env["contract.document.template"].create(
            {
                "name": "Support contract",
                "title": "Contract {{ object.name }}",
                "body": '<p>Between <t t-out="object.company_id.name"/> and '
                '<t t-out="object.partner_id.name"/>.</p>',
                "clause_ids": [(6, 0, (cls.clause_conf | cls.clause_object).ids)],
            }
        )
        cls.contract_template = cls.env["contract.template"].create(
            {"name": "Support 30h", "document_template_id": cls.doc_template.id}
        )
        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "SUP-001",
                "partner_id": cls.partner.id,
                "contract_template_id": cls.contract_template.id,
            }
        )

    def test_template_from_contract_template(self):
        self.assertEqual(self.contract.document_template_id, self.doc_template)

    def test_generate_document(self):
        self.contract.action_generate_document()
        html = str(self.contract.document_html)
        self.assertIn("Contract SUP-001", html)
        self.assertIn("Client Test SL", html)
        self.assertIn(self.contract.company_id.name, html)
        # Clauses numbered in sequence order, not in creation order
        self.assertLess(html.index("1. Object"), html.index("2. Confidentiality"))
        self.assertIn("including Client Test SL", html)
        self.assertTrue(self.contract.document_date)

    def test_document_frozen(self):
        self.contract.action_generate_document()
        frozen = self.contract.document_html
        self.clause_object.body = "<p>Changed text.</p>"
        # Changing the template does not change the issued document
        self.assertEqual(self.contract.document_html, frozen)
        self.contract.document_locked = True
        with self.assertRaises(UserError):
            self.contract.action_generate_document()
        with self.assertRaises(UserError):
            self.contract.document_html = "<p>Tampered</p>"

    def test_effective_date_in_document(self):
        self.clause_object.body = (
            '<p>Effects from <t t-if="object.document_effective_date" '
            't-out="object.document_effective_date.isoformat()"/>'
            '<t t-else="">signature</t>.</p>'
        )
        self.contract.action_generate_document()
        self.assertIn("Effects from signature.", str(self.contract.document_html))
        self.contract.document_effective_date = "2024-01-01"
        self.contract.action_generate_document()
        self.assertIn("Effects from 2024-01-01.", str(self.contract.document_html))
        # The generation date stays the real one
        self.assertGreater(self.contract.document_date.date().isoformat(), "2024-01-01")

    def test_annexes_and_unnumbered_clauses(self):
        Clause = self.env["contract.document.clause"]
        annex = self.env["contract.document.template"].create({
            "name": "DPA",
            "title": "Data processing agreement",
            "body": "<p>Processor terms.</p>",
            "clause_ids": [(6, 0, (
                Clause.create({"name": "Instructions", "sequence": 1})
                | Clause.create({"name": "Security", "sequence": 2})
                | Clause.create({"name": "Appendix I", "sequence": 3, "numbered": False})
            ).ids)],
        })
        self.doc_template.annex_ids = annex
        self.contract.action_generate_document()
        html = str(self.contract.document_html)
        # Main clauses, then the annex on a new page with its own numbering
        self.assertLess(html.index("2. Confidentiality"), html.index("Annex 1. Data processing agreement"))
        annex_part = html[html.index("Annex 1."):]
        self.assertIn("page-break-before", html[: html.index("Annex 1.")][-200:])
        self.assertIn("1. Instructions", annex_part)
        self.assertIn("2. Security", annex_part)
        self.assertIn(">Appendix I<", annex_part)
        self.assertNotIn("3. Appendix", annex_part)
        # The annex alone is still a complete document
        alone = annex._render_contract_document(self.contract)
        self.assertIn("Data processing agreement", alone)
        self.assertNotIn("Annex", alone)

    def test_generate_without_template(self):
        self.contract.document_template_id = False
        with self.assertRaises(UserError):
            self.contract.action_generate_document()

    def test_report_html(self):
        self.contract.action_generate_document()
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "contract_document_template.report_contract_document", self.contract.ids
        )
        html = html.decode()
        self.assertIn("Client Test SL", html)
        self.assertIn("o_contract_sign_box_partner", html)
