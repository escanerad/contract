# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup, escape

from odoo import fields, models


class ContractDocumentTemplate(models.Model):
    """Legal text of a contract: an introduction/body plus an ordered list of
    reusable clauses. Rendered with the contract as ``object`` (QWeb), in the
    language of the contract partner, and frozen on the contract."""

    _name = "contract.document.template"
    _inherit = ["mail.render.mixin"]
    _description = "Contract Document Template"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    title = fields.Char(
        translate=True,
        help="Title printed on the document. Placeholders may be used, "
        "e.g. {{ object.name }}. Defaults to the contract name.",
    )
    body = fields.Html(
        render_engine="qweb",
        render_options={"post_process": True},
        translate=True,
        sanitize="email_outgoing",
        help="Introduction / parties / object of the contract. The contract "
        'is available as \'object\', e.g. <t t-out="object.partner_id.name"/>.',
    )
    clause_ids = fields.Many2many(
        "contract.document.clause",
        string="Clauses",
        help="Clauses appended after the body, numbered, in their sequence order.",
    )
    include_line_table = fields.Boolean(
        string="Include price table",
        default=True,
        help="Print the recurring lines of the contract (economic conditions).",
    )
    include_signature_page = fields.Boolean(
        string="Include signature page",
        default=True,
        help="Add a last page with the signature boxes of both parties.",
    )

    def _compute_render_model(self):
        self.render_model = "contract.contract"

    def _get_render_lang(self, contract):
        self.ensure_one()
        lang = False
        if self.lang:
            lang = self._render_lang(contract.ids)[contract.id]
        return lang or contract.partner_id.lang or self.env.lang

    def _render_contract_document(self, contract):
        """Return the full legal text (Markup) of ``contract``."""
        self.ensure_one()
        contract.ensure_one()
        lang = self._get_render_lang(contract)
        template = self.with_context(lang=lang)
        parts = []
        if template.title:
            title = template._render_field(
                "title", contract.ids, engine="inline_template"
            )[contract.id]
            parts.append(Markup("<h2 class='o_contract_doc_title'>%s</h2>") % title)
        if template.body:
            parts.append(template._render_field("body", contract.ids, engine="qweb")[contract.id])
        clauses = template.clause_ids.with_context(lang=lang).sorted(
            lambda c: (c.sequence, c.id)
        )
        for number, clause in enumerate(clauses, start=1):
            parts.append(
                Markup("<h4 class='o_contract_doc_clause'>%s. %s</h4>")
                % (number, escape(clause.name))
            )
            if clause.body:
                parts.append(clause._render_field("body", contract.ids, engine="qweb")[contract.id])
        return Markup("").join(parts)
