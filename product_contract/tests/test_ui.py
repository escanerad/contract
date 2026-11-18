# Copyright 2026 ESCÀNER Serveis TIC - Albert Pons Domenjó
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestProductContractUi(HttpCase):
    def test_contract_on_the_order_line(self):
        product = self.env["product.product"].create(
            {
                "name": "Synthetic yearly service",
                "type": "service",
                "is_contract": True,
                "recurring_rule_type": "yearly",
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.env["res.partner"].create({"name": "Synthetic customer"}).id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "date_start": "2026-01-01",
                            "date_end": "2026-12-31",
                        },
                    )
                ],
            }
        )
        self.start_tour(
            f"/odoo/action-sale.action_quotations_with_onboarding/{order.id}",
            "product_contract_order_line",
            login="admin",
        )
