# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo.tests import HttpCase, tagged

from .test_contract_sign import FAKE_PDF


@tagged("post_install", "-at_install")
class TestPortalDownload(HttpCase):
    def test_download_signed_upload(self):
        partner = self.env["res.partner"].create({"name": "Tenant", "email": "t@example.com"})
        contract = self.env["contract.contract"].create({"name": "LL-1", "partner_id": partner.id})
        document = self.env["contract.document"].create(
            {
                "contract_id": contract.id,
                "source": "upload",
                "title": "Rental contract",
                "uploaded_file": base64.b64encode(FAKE_PDF).decode(),
                "uploaded_filename": "contract.pdf",
                "signed_outside": True,
            }
        )
        token = contract._portal_ensure_token()
        url = f"/my/contracts/{contract.id}/document/{document.id}"
        response = self.url_open(f"{url}?access_token={token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, FAKE_PDF)
        # Without the token: no access
        response = self.url_open(url, allow_redirects=False)
        self.assertNotEqual(response.content, FAKE_PDF)
        # A document not signed is not offered
        document.signed_outside = False
        response = self.url_open(f"{url}?access_token={token}")
        self.assertEqual(response.status_code, 404)
        # The contract page shows the download link
        document.signed_outside = True
        page = self.url_open(f"/my/contracts/{contract.id}?access_token={token}")
        self.assertIn(f"{url}?access_token={token}", page.text)
