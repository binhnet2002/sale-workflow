# Copyright 2018 ACSONE SA/NV
# Copyright 2019 Eficent and IT Consulting Services, S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, _
from datetime import date, timedelta
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    blanket_order_id = fields.Many2one(
        'sale.blanket.order', string='Origin blanket order',
        related='order_line.blanket_order_line.order_id',
        readonly=True)

    @api.constrains('partner_id')
    def check_partner_id(self):
        if self.partner_id:
            if self.order_line:
                for line in self.order_line:
                    if line.blanket_order_line:
                        if line.blanket_order_line.partner_id != \
                                self.partner_id:
                            raise ValidationError(_(
                                'The customer must be equal to the '
                                'blanket order lines customer'))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    blanket_order_line = fields.Many2one(
        'sale.blanket.order.line',
        string='Blanket Order line',
        copy=False)

    @api.onchange('product_id', 'order_id.partner_id')
    def onchange_product_id(self):
        # If product has changed remove the relation with blanket order line
        if self.product_id:
            eligible_bo_lines = self.get_eligible_bo_lines()
            if eligible_bo_lines:
                if not self.blanket_order_line or \
                        self.blanket_order_line.product_id != self.product_id:
                    self.blanket_order_line = \
                        self.get_assigned_bo_line(eligible_bo_lines)
            return {'domain': {'blanket_order_line': [
                ('id', 'in', eligible_bo_lines.ids)]}}

    @api.onchange('blanket_order_line')
    def onchange_blanket_order_line(self):
        if self.blanket_order_line and \
                self.blanket_order_line.product_uom != self.product_uom:
            self.product_uom = self.blanket_order_line.product_uom
        if self.blanket_order_line and \
                self.blanket_order_line.price_unit != self.price_unit:
            self.price_unit = self.blanket_order_line.price_unit

    def get_assigned_bo_line(self, bo_lines):
        # We get the blanket order line with enough quantity and closest
        # scheduled date
        assigned_bo_line = False
        today = date.today()
        date_delta = timedelta(days=365)
        for line in bo_lines:
            date_schedule = fields.Date.from_string(line.date_schedule)
            if self.product_uom_qty >= 0:
                if line.remaining_qty > self.product_uom_qty:
                    if date_schedule and date_schedule - today < date_delta:
                        assigned_bo_line = line
                        date_delta = date_schedule - today
        if not assigned_bo_line:
            assigned_bo_line = bo_lines[0]
        return assigned_bo_line

    def get_eligible_bo_lines_domain(self):
        return [
            ('product_id', '=', self.product_id.id),
            ('order_id.partner_id', '=', self.order_id.partner_id.id),
            ('remaining_qty', '>', 0.0),
            ('order_id.state', '=', 'open')]

    def get_eligible_bo_lines(self):
        domain = self.get_eligible_bo_lines_domain()
        return self.env['sale.blanket.order.line'].search(domain)

    @api.constrains('product_id')
    def check_product_id(self):
        if self.blanket_order_line and \
                self.product_id != self.blanket_order_line.product_id:
            raise ValidationError(_(
                'The product in the blanket order and in the '
                'sales order must match'))
