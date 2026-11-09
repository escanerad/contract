# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""1.x stored one document per contract on contract.contract and one template
per contract template: move them to contract.document and to the documents of
the contract template. The old columns are left in place (and read by
contract_sign_oca's own migration)."""

from odoo import SUPERUSER_ID, api


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if _column_exists(cr, "contract_template", "document_template_id"):
        cr.execute(
            """
            INSERT INTO contract_template_document_template_rel
                (contract_template_id, document_template_id)
            SELECT id, document_template_id FROM contract_template
            WHERE document_template_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
    if not _column_exists(cr, "contract_contract", "document_template_id"):
        return
    cr.execute(
        """
        DELETE FROM contract_contract_document_template_rel;
        INSERT INTO contract_contract_document_template_rel
            (contract_id, document_template_id)
        SELECT id, document_template_id FROM contract_contract
        WHERE document_template_id IS NOT NULL
        """
    )
    cr.execute(
        """
        SELECT id, document_template_id, document_html, document_date,
               document_effective_date, COALESCE(document_locked, false)
        FROM contract_contract
        WHERE document_template_id IS NOT NULL
        """
    )
    Document = env["contract.document"].with_context(
        contract_document_force_write=True, mail_notrack=True
    )
    for cid, tid, html, gen_date, eff_date, locked in cr.fetchall():
        contract = env["contract.contract"].browse(cid)
        document = Document.create(
            {
                "contract_id": cid,
                "template_id": tid,
                "document_type": "main",
                "document_effective_date": eff_date,
            }
        )
        document.write(
            {
                "document_html": html,
                "document_date": gen_date,
                "state": "issued" if locked else "draft",
            }
        )
        if html:
            document.title = (
                document.template_id._render_title(document) or document.template_id.name
            )
        contract.message_post(
            body=env._("Document migrated to %(name)s.", name=document.name),
            subtype_xmlid="mail.mt_note",
        )
