# Copyright 2020 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SaleOrder(models.Model):

    _inherit = "sale.order"

    sale_warn_msg = fields.Text(compute="_compute_sale_warn_msg")

    @api.depends('state',
                 'partner_id.commercial_partner_id.sale_warn')
    def _compute_sale_warn_msg(self):
        for rec in self:
            p = rec.partner_id.commercial_partner_id
            if rec.state in ["draft", "sent"] and p.sale_warn == "warning":
                rec.sale_warn_msg = p.sale_warn_msg
                continue
            rec.sale_warn_msg = False
