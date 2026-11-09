# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_document_count = fields.Integer(
        compute="_compute_contract_document_count", string="Contract documents"
    )

    def _compute_contract_document_count(self):
        data = self.env["contract.document"]._read_group(
            [("commercial_partner_id", "in", self.commercial_partner_id.ids)],
            ["commercial_partner_id"],
            ["__count"],
        )
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.contract_document_count = counts.get(
                partner.commercial_partner_id.id, 0
            )

    def action_view_contract_documents(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "contract_document_template.contract_document_action"
        )
        action["domain"] = [
            ("commercial_partner_id", "=", self.commercial_partner_id.id)
        ]
        action["context"] = {"default_partner_id": self.id}
        return action
