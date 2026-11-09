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
        Clause = cls.env["contract.document.clause"]
        Template = cls.env["contract.document.template"]
        cls.clause_conf = Clause.create(
            {
                "name": "Confidentiality",
                "sequence": 20,
                "body": '<p>Both parties, including <t t-out="object.partner_id.name"/>,'
                " keep the information confidential.</p>",
            }
        )
        cls.clause_object = Clause.create(
            {"name": "Object", "sequence": 10, "body": "<p>IT support services.</p>"}
        )
        cls.doc_template = Template.create(
            {
                "name": "Support contract",
                "sequence": 1,
                "title": "Contract {{ object.name }}",
                "body": '<p>Between <t t-out="object.company_id.name"/> and '
                '<t t-out="object.partner_id.name"/>.</p>',
                "clause_ids": [(6, 0, (cls.clause_conf | cls.clause_object).ids)],
            }
        )
        cls.nda_template = Template.create(
            {
                "name": "Non-disclosure agreement",
                "sequence": 2,
                "document_type": "document",
                "body": '<p>NDA with <t t-out="object.partner_id.name"/>.</p>',
            }
        )
        cls.addendum_template = Template.create(
            {
                "name": "Addendum",
                "document_type": "addendum",
                "body": '<p>Amends <t t-out="object.parent_id.name"/>.</p>',
            }
        )
        cls.contract_template = cls.env["contract.template"].create(
            {
                "name": "Support 30h",
                "document_template_ids": [
                    (6, 0, (cls.doc_template | cls.nda_template).ids)
                ],
            }
        )
        cls.contract = cls.env["contract.contract"].create(
            {
                "name": "SUP-001",
                "partner_id": cls.partner.id,
                "contract_template_id": cls.contract_template.id,
            }
        )

    def _main(self):
        return self.contract.document_ids.filtered(lambda d: d.document_type == "main")

    def test_generate_documents(self):
        self.contract.action_generate_documents()
        main, nda = self.contract.document_ids.sorted("sequence")
        self.assertEqual(main.template_id, self.doc_template)
        self.assertEqual((main.name, nda.name), ("SUP-001", "SUP-001/D1"))
        self.assertEqual(nda.document_type, "document")
        self.assertEqual(main.partner_id, self.partner)
        html = str(main.document_html)
        self.assertIn("Contract SUP-001", html)
        self.assertEqual(main.title, "Contract SUP-001")
        self.assertIn("Client Test SL", html)
        self.assertIn(self.contract.company_id.name, html)
        # Clauses numbered in sequence order, not in creation order
        self.assertLess(html.index("1. Object"), html.index("2. Confidentiality"))
        self.assertIn("including Client Test SL", html)
        self.assertTrue(main.document_date)
        self.assertIn("NDA with Client Test SL", str(nda.document_html))
        # Generating again does not duplicate the documents
        self.contract.action_generate_documents()
        self.assertEqual(len(self.contract.document_ids), 2)

    def test_document_frozen(self):
        self.contract.action_generate_documents()
        main = self._main()
        frozen = main.document_html
        self.clause_object.body = "<p>Changed text.</p>"
        # Changing the template does not change the generated document
        self.assertEqual(main.document_html, frozen)
        main.action_issue()
        self.assertEqual(main.state, "issued")
        with self.assertRaises(UserError):
            main.action_generate()
        with self.assertRaises(UserError):
            main.document_html = "<p>Tampered</p>"
        with self.assertRaises(UserError):
            main.unlink()
        # Regenerating the contract documents leaves the issued one untouched
        self.contract.action_generate_documents()
        self.assertEqual(main.document_html, frozen)

    def test_addendum(self):
        self.contract.action_generate_documents()
        main = self._main()
        main.action_issue()
        action = main.action_new_addendum()
        addendum = (
            self.env["contract.document"]
            .with_context(**action["context"])
            .create({"template_id": self.addendum_template.id})
        )
        self.assertEqual(addendum.document_type, "addendum")
        self.assertEqual(addendum.contract_id, self.contract)
        self.assertEqual(addendum.name, "SUP-001/A1")
        self.assertEqual(main.addendum_ids, addendum)
        addendum.action_generate()
        self.assertIn("Amends SUP-001", str(addendum.document_html))

    def test_document_without_contract(self):
        nda = self.env["contract.document"].create(
            {"partner_id": self.partner.id, "template_id": self.nda_template.id}
        )
        self.assertTrue(nda.name.startswith("DOC/"))
        nda.action_generate()
        self.assertIn("NDA with Client Test SL", str(nda.document_html))
        self.assertEqual(self.partner.contract_document_count, 1)

    def test_effective_date_in_document(self):
        self.clause_object.body = (
            '<p>Effects from <t t-if="object.document_effective_date" '
            't-out="object.document_effective_date.isoformat()"/>'
            '<t t-else="">signature</t>.</p>'
        )
        self.contract.action_generate_documents()
        main = self._main()
        self.assertIn("Effects from signature.", str(main.document_html))
        main.document_effective_date = "2024-01-01"
        main.action_generate()
        self.assertIn("Effects from 2024-01-01.", str(main.document_html))
        # The generation date stays the real one
        self.assertGreater(main.document_date.date().isoformat(), "2024-01-01")

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
        self.contract.action_generate_documents()
        main = self._main()
        html = str(main.document_html)
        # Main clauses, then the annex on a new page with its own numbering
        self.assertLess(html.index("2. Confidentiality"), html.index("Annex 1. Data processing agreement"))
        annex_part = html[html.index("Annex 1."):]
        self.assertIn("page-break-before", html[: html.index("Annex 1.")][-200:])
        self.assertIn("1. Instructions", annex_part)
        self.assertIn("2. Security", annex_part)
        self.assertIn(">Appendix I<", annex_part)
        self.assertNotIn("3. Appendix", annex_part)
        # The annex alone is still a complete document
        alone = annex._render_contract_document(main)
        self.assertIn("Data processing agreement", alone)
        self.assertNotIn("Annex", alone)

    def test_generate_without_documents(self):
        contract = self.env["contract.contract"].create(
            {"name": "NO-DOC", "partner_id": self.partner.id}
        )
        with self.assertRaises(UserError):
            contract.action_generate_documents()

    def test_cancel_and_regenerate(self):
        self.contract.action_generate_documents()
        main = self._main()
        main.action_issue()
        main.action_cancel()
        # A cancelled document is replaced by a new one
        self.contract.action_generate_documents()
        mains = self.contract.document_ids.filtered(
            lambda d: d.document_type == "main" and d.state == "draft"
        )
        self.assertEqual(len(mains), 1)
        self.assertEqual(mains.name, "SUP-001/2")

    def test_report_html(self):
        self.contract.action_generate_documents()
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "contract_document_template.report_contract_document",
            self.contract.document_ids.ids,
        )
        html = html.decode()
        self.assertIn("Client Test SL", html)
        self.assertIn("o_contract_sign_box_partner", html)
        self.assertIn("NDA with Client Test SL", html)
