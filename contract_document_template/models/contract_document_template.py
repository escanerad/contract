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
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, help="Order of the template when used as an annex.")
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
    annex_ids = fields.Many2many(
        "contract.document.template",
        "contract_document_template_annex_rel",
        "template_id",
        "annex_id",
        string="Annexes",
        help="Other document templates appended to this one as annexes (e.g. the "
        "data processing agreement of a service contract). Each annex starts on a "
        "new page, is titled 'Annex N' and numbers its own clauses; its price "
        "table, signature page and own annexes are not printed.",
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
        title = template._render_title(contract)
        if title:
            parts.append(Markup("<h2 class='o_contract_doc_title'>%s</h2>") % title)
        parts += template._render_body_and_clauses(contract)
        annexes = template.annex_ids.with_context(lang=lang).sorted(
            lambda a: (a.sequence, a.id)
        ) - template
        for number, annex in enumerate(annexes, start=1):
            annex_title = annex._render_title(contract) or annex.name
            parts.append(Markup("<div style='page-break-before: always;'></div>"))
            parts.append(
                Markup("<h2 class='o_contract_doc_annex_title'>%s</h2>")
                % self.env._("Annex %(number)s. %(title)s", number=number, title=annex_title)
            )
            parts += annex._render_body_and_clauses(contract)
        return Markup("").join(parts)

    def _render_title(self, contract):
        self.ensure_one()
        if not self.title:
            return ""
        return self._render_field("title", contract.ids, engine="inline_template")[contract.id]

    def _render_body_and_clauses(self, contract):
        """Body and clauses of this template, the numbered clauses from 1."""
        self.ensure_one()
        parts = []
        if self.body:
            parts.append(self._render_field("body", contract.ids, engine="qweb")[contract.id])
        clauses = self.clause_ids.with_context(lang=self.env.lang).sorted(
            lambda c: (c.sequence, c.id)
        )
        number = 0
        for clause in clauses:
            if clause.numbered:
                number += 1
                heading = Markup("%s. %s") % (number, clause.name)
            else:
                heading = escape(clause.name)
            parts.append(Markup("<h4 class='o_contract_doc_clause'>%s</h4>") % heading)
            if clause.body:
                parts.append(clause._render_field("body", contract.ids, engine="qweb")[contract.id])
        return parts
