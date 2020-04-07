# Copyright 2020 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestSaleOrderWarnMessage(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warn_msg_parent = "This customer has a warn from parent"
        self.parent = self.env["res.partner"].create(
            {
                "name": "Customer with a warn",
                "email": "customer@warn.com",
                "sale_warn": "warning",
                "sale_warn_msg": self.warn_msg_parent,
            }
        )
        self.warn_msg = "This customer has a warn"
        self.partner = self.env["res.partner"].create(
            {
                "name": "Customer with a warn",
                "email": "customer@warn.com",
                "sale_warn": "warning",
                "sale_warn_msg": self.warn_msg,
            }
        )

    def test_compute_sale_warn_msg(self):
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref("product.product_product_4").id,
                            "product_uom_qty": 1,
                            "price_unit": 42,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(sale.sale_warn_msg, self.warn_msg)

    def test_compute_sale_warn_msg_parent(self):
        self.partner.update({"parent_id": self.parent.id})
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref("product.product_product_4").id,
                            "product_uom_qty": 1,
                            "price_unit": 42,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(sale.sale_warn_msg, self.warn_msg_parent)
