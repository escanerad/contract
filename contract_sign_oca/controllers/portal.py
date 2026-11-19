# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalContractDocument(CustomerPortal):
    @http.route(
        ["/my/contracts/<int:contract_id>/document/<int:document_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_contract_signed_document(self, contract_id, document_id, access_token=None, **kw):
        """Signed file of a document listed on the portal contract page, with
        the same access as the contract."""
        try:
            contract_sudo = self._document_check_access(
                "contract.contract", contract_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")
        documents = [item[0] for item in contract_sudo._get_portal_documents()]
        document = next((d for d in documents if d.id == document_id), None)
        if not document or not document.signed_attachment_id:
            raise request.not_found()
        return (
            request.env["ir.binary"]
            ._get_stream_from(document.signed_attachment_id.sudo())
            .get_response(as_attachment=True)
        )
