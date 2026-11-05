# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    def _check_signed(self):
        previous_state = self.state
        result = super()._check_signed()
        if previous_state != "2_signed" and self.state == "2_signed":
            contracts = (
                self.env["contract.contract"]
                .sudo()
                .search([("sign_request_id", "=", self.id)])
            )
            if contracts:
                contracts._on_sign_request_signed(self)
        return result
