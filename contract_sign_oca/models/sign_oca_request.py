# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    def action_send(self, sign_now=False, message=""):
        """With contract_sign_silent the request is sent without its own
        e-mails: contract.document sends a single e-mail per signer with the
        links of all its documents."""
        if not self.env.context.get("contract_sign_silent"):
            return super().action_send(sign_now=sign_now, message=message)
        self.ensure_one()
        if self.state != "1_draft":
            return
        self._set_action_log("validate")
        self.state = "0_sent"
        for signer in self.signer_ids:
            signer._portal_ensure_token()

    def _check_signed(self):
        previous_state = self.state
        result = super()._check_signed()
        if previous_state != "2_signed" and self.state == "2_signed":
            documents = (
                self.env["contract.document"]
                .sudo()
                .search([("sign_request_id", "=", self.id)])
            )
            if documents:
                documents._on_sign_request_signed(self)
        return result
