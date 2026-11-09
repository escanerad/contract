# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""1.x signed the single document of the contract: move the signature data
to the main document created by contract_document_template's migration."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'contract_contract' AND column_name = 'sign_request_id'"
    )
    if not cr.fetchone():
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        SELECT id, sign_request_id, signed_on, signed_attachment_id, sign_required
        FROM contract_contract
        WHERE sign_request_id IS NOT NULL OR sign_required IS NOT NULL
        """
    )
    for cid, request_id, signed_on, attachment_id, required in cr.fetchall():
        document = env["contract.document"].search(
            [("contract_id", "=", cid), ("document_type", "=", "main")], limit=1
        )
        if not document:
            continue
        document.with_context(contract_document_force_write=True).write(
            {
                "sign_request_id": request_id,
                "signed_on": signed_on,
                "signed_attachment_id": attachment_id,
                "sign_required": bool(required),
            }
        )
        if request_id:
            env["sign.oca.request"].browse(request_id).record_ref = (
                f"contract.document,{document.id}"
            )
    env["contract.contract"].search([])._compute_sign_state()
