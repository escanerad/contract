# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup, escape

from odoo import fields, models

DOCUMENT_TYPES = [
    ("main", "Contract"),
    ("document", "Separate document"),
    ("addendum", "Addendum"),
]


class ContractDocumentTemplate(models.Model):
    """Legal text of a contract document: an introduction/body plus an ordered
    list of reusable clauses. Rendered with the document (contract.document) as
    ``object`` (QWeb), in the language of the partner, and frozen on the
    document. ``object.partner_id``, ``object.company_id``,
    ``object.contract_id``, ``object.contract_line_ids`` and
    ``object.document_effective_date`` are available."""

    _name = "contract.document.template"
    _inherit = ["mail.render.mixin"]
    _description = "Contract Document Template"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(
        default=10, help="Order of the template in a contract and as an annex."
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    document_type = fields.Selection(
        DOCUMENT_TYPES,
        string="Type",
        default="main",
        required=True,
        help="Contract: main document of the contract. Separate document: signed "
        "on its own (non-disclosure agreement, data processing agreement...). "
        "Addendum: amends a previous document.",
    )
    title = fields.Char(
        translate=True,
        help="Title printed on the document. Placeholders may be used, "
        "e.g. {{ object.name }}. Defaults to the template name.",
    )
    body = fields.Html(
        render_engine="qweb",
        render_options={"post_process": True},
        translate=True,
        sanitize="email_outgoing",
        help="Introduction / parties / object of the document. The document "
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
        help="Other document templates appended to this one as annexes, in the "
        "same PDF and signed with it. Each annex starts on a new page, is titled "
        "'Annex N' and numbers its own clauses; its price table, signature page "
        "and own annexes are not printed. To sign it separately, add it to the "
        "contract template as another document instead.",
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
        self.render_model = "contract.document"

    def _get_render_lang(self, document):
        self.ensure_one()
        lang = False
        if self.lang:
            lang = self._render_lang(document.ids)[document.id]
        return lang or document.partner_id.lang or self.env.lang

    def _render_contract_document(self, document):
        """Return the full legal text (Markup) of ``document``
        (contract.document)."""
        self.ensure_one()
        document.ensure_one()
        lang = self._get_render_lang(document)
        template = self.with_context(lang=lang)
        parts = []
        title = template._render_title(document)
        if title:
            parts.append(Markup("<h2 class='o_contract_doc_title'>%s</h2>") % title)
        parts += template._render_body_and_clauses(document)
        annexes = template.annex_ids.with_context(lang=lang).sorted(
            lambda a: (a.sequence, a.id)
        ) - template
        for number, annex in enumerate(annexes, start=1):
            annex_title = annex._render_title(document) or annex.name
            parts.append(Markup("<div style='page-break-before: always;'></div>"))
            parts.append(
                Markup("<h2 class='o_contract_doc_annex_title'>%s</h2>")
                % self.env._("Annex %(number)s. %(title)s", number=number, title=annex_title)
            )
            parts += annex._render_body_and_clauses(document)
        return Markup("").join(parts)

    def _render_title(self, document):
        self.ensure_one()
        if not self.title:
            return ""
        return self._render_field("title", document.ids, engine="inline_template")[
            document.id
        ]

    def _render_body_and_clauses(self, document):
        """Body and clauses of this template, the numbered clauses from 1."""
        self.ensure_one()
        parts = []
        if self.body:
            parts.append(self._render_field("body", document.ids, engine="qweb")[document.id])
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
                parts.append(clause._render_field("body", document.ids, engine="qweb")[document.id])
        return parts
