# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError

from .contract_document_template import DOCUMENT_TYPES

# Fields of an issued document that cannot change anymore: it is what the
# parties received / signed.
FROZEN_FIELDS = {
    "template_id",
    "document_html",
    "document_effective_date",
    "partner_id",
    "contract_id",
    "parent_id",
}
NAME_PREFIX = {"document": "D", "addendum": "A"}


class ContractDocument(models.Model):
    """A legal document of a contract (the contract itself, a separate
    agreement such as an NDA or a data processing agreement, an addendum...).
    Each document has its own text, frozen once issued, and its own
    signature. A document may also belong to a partner only (e.g. an NDA
    signed before any contract)."""

    _name = "contract.document"
    _inherit = ["mail.thread"]
    _description = "Contract Document"
    _order = "contract_id, sequence, id"

    name = fields.Char(
        string="Reference", required=True, readonly=True, copy=False, default="/"
    )
    title = fields.Char(
        compute="_compute_title", store=True, readonly=False, copy=False
    )
    sequence = fields.Integer(default=10)
    template_id = fields.Many2one(
        "contract.document.template",
        string="Template",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    document_type = fields.Selection(
        DOCUMENT_TYPES,
        string="Type",
        compute="_compute_document_type",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    contract_id = fields.Many2one(
        "contract.contract", index=True, ondelete="restrict", tracking=True
    )
    partner_id = fields.Many2one(
        "res.partner",
        compute="_compute_partner_id",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
        index=True,
        tracking=True,
    )
    commercial_partner_id = fields.Many2one(
        related="partner_id.commercial_partner_id", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company",
        compute="_compute_company_id",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id")
    contract_line_ids = fields.Many2many(
        "contract.line",
        compute="_compute_contract_line_ids",
        help="Lines of the contract, for the templates (object.contract_line_ids).",
    )
    parent_id = fields.Many2one(
        "contract.document",
        string="Modifies",
        domain="[('contract_id', '=', contract_id), ('id', '!=', id), "
        "('state', '!=', 'cancel')]",
        help="Document amended by this addendum.",
    )
    addendum_ids = fields.One2many("contract.document", "parent_id", string="Addenda")
    document_html = fields.Html(
        string="Document",
        copy=False,
        sanitize="email_outgoing",
        help="Legal text, generated from the template and frozen: later changes "
        "on the template do not alter it.",
    )
    document_date = fields.Datetime(string="Generated on", copy=False, readonly=True)
    document_effective_date = fields.Date(
        string="Effective from",
        copy=False,
        tracking=True,
        help="Date from which the document takes effect, when it differs from its "
        "signature (e.g. it also covers a service already being provided). "
        "Templates use it as object.document_effective_date; it does not change "
        "the signature date.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("issued", "Issued"), ("cancel", "Cancelled")],
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        help="Issued: sent to the other party (e.g. for signature); its text cannot "
        "be changed anymore. Changes are made with an addendum.",
    )

    @api.depends("template_id")
    def _compute_document_type(self):
        for document in self:
            document.document_type = document.template_id.document_type or "main"

    @api.depends("contract_id")
    def _compute_partner_id(self):
        for document in self:
            if document.contract_id:
                document.partner_id = document.contract_id.partner_id

    @api.depends("contract_id")
    def _compute_company_id(self):
        for document in self:
            document.company_id = (
                document.contract_id.company_id
                or document.company_id
                or self.env.company
            )

    @api.depends("contract_id.currency_id", "company_id")
    def _compute_currency_id(self):
        for document in self:
            document.currency_id = (
                document.contract_id.currency_id or document.company_id.currency_id
            )

    @api.depends("contract_id.contract_line_ids")
    def _compute_contract_line_ids(self):
        for document in self:
            document.contract_line_ids = document.contract_id.contract_line_ids

    @api.depends("template_id")
    def _compute_title(self):
        for document in self:
            if document.state == "draft" or not document.title:
                document.title = document.template_id.name

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        for document in documents.filtered(lambda d: d.name == "/"):
            document.name = document._get_next_name()
        return documents

    def _get_next_name(self):
        """Main document: the contract reference. Other documents of a
        contract: <contract>/D1, D2... and addenda <contract>/A1, A2...
        Documents without contract: sequence."""
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            return self.env["ir.sequence"].with_company(
                self.company_id
            ).next_by_code("contract.document") or "/"
        if self.document_type == "main":
            mains = contract.document_ids.filtered(
                lambda d: d.document_type == "main" and d != self
            )
            return contract.name if not mains else f"{contract.name}/{len(mains) + 1}"
        same_type = contract.document_ids.filtered(
            lambda d: d.document_type == self.document_type and d != self
        )
        return f"{contract.name}/{NAME_PREFIX[self.document_type]}{len(same_type) + 1}"

    def write(self, vals):
        if FROZEN_FIELDS & set(vals) and not self.env.context.get(
            "contract_document_force_write"
        ):
            self._check_draft()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(document.state != "draft" for document in self):
            raise UserError(
                self.env._(
                    "Only draft documents can be deleted; cancel the issued ones "
                    "instead, they are part of the contract record."
                )
            )

    def _check_draft(self):
        issued = self.filtered(lambda d: d.state != "draft")
        if issued:
            raise UserError(
                self.env._(
                    "Document %(documents)s has already been issued and cannot be "
                    "modified: make an addendum instead.",
                    documents=", ".join(issued.mapped("display_name")),
                )
            )

    @api.depends("name", "title")
    def _compute_display_name(self):
        for document in self:
            document.display_name = (
                f"{document.name} - {document.title}"
                if document.title and document.title != document.name
                else document.name
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_generate(self):
        self._check_draft()
        for document in self:
            template = document.template_id
            document.write(
                {
                    "document_html": template._render_contract_document(document),
                    "title": template._render_title(document) or template.name,
                    "document_date": fields.Datetime.now(),
                }
            )
        return True

    def action_issue(self):
        """Freeze the document: it has been sent to the other party."""
        for document in self.filtered(lambda d: d.state == "draft"):
            if not document.document_html:
                document.action_generate()
        self.filtered(lambda d: d.state == "draft").state = "issued"
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_reset_draft(self):
        """Only a cancelled document never signed may go back to draft."""
        self.filtered(lambda d: d.state == "cancel")._check_can_reset()
        self.filtered(lambda d: d.state == "cancel").state = "draft"
        return True

    def _check_can_reset(self):
        return True

    def action_print(self):
        self.ensure_one()
        if not self.document_html and self.state == "draft":
            self.action_generate()
        return self.env.ref(
            "contract_document_template.report_contract_document"
        ).report_action(self)

    def action_new_addendum(self):
        """Open a new addendum amending this document."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contract.document",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_contract_id": self.contract_id.id,
                "default_partner_id": self.partner_id.id,
                "default_company_id": self.company_id.id,
                "default_parent_id": self.id,
                "default_document_type": "addendum",
            },
        }
