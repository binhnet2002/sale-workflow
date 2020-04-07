# Copyright 2020 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Sale Order Warn Message",
    "summary": """
        Add a popup warning on sale to ensure warning is populated""",
    "version": "11.0.1.0.0",
    "license": "AGPL-3",
    "author": "ForgeFlow, Odoo Community Association (OCA)",
    "website": "www.github.com/OCA/sale-workflow.git",
    "depends": ["sale", "account_invoice_warn_message"],
    "data": ["views/sale_order.xml"],
}
