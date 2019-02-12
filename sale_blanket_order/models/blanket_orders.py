# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

import odoo.addons.decimal_precision as dp


class BlanketOrder(models.Model):
    _name = 'sale.blanket.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Blanket Order'

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.model
    def _default_company(self):
        return self.env.user.company_id

    name = fields.Char(
        default='Draft',
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Partner', readonly=True,
        states={'draft': [('readonly', False)]})
    line_ids = fields.One2many(
        'sale.blanket.order.line', 'order_id', string='Order lines',
        copy=True)
    line_count = fields.Integer(
        string='Sale Blanket Order Line count',
        compute='_compute_line_count',
        readonly=True
    )
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', required=True, readonly=True,
        states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one(
        'res.currency', related='pricelist_id.currency_id', readonly=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms', readonly=True,
        states={'draft': [('readonly', False)]})
    confirmed = fields.Boolean()
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('done', 'Done'),
        ('expired', 'Expired'),
    ], compute='_compute_state', store=True, copy=False)
    validity_date = fields.Date(
        readonly=True,
        states={'draft': [('readonly', False)]})
    client_order_ref = fields.Char(
        string='Customer Reference', copy=False, readonly=True,
        states={'draft': [('readonly', False)]})
    note = fields.Text(
        readonly=True,
        states={'draft': [('readonly', False)]})
    user_id = fields.Many2one(
        'res.users', string='Salesperson', readonly=True,
        states={'draft': [('readonly', False)]})
    team_id = fields.Many2one(
        'crm.team', string='Sales Team', change_default=True,
        default=_get_default_team, readonly=True,
        states={'draft': [('readonly', False)]})
    company_id = fields.Many2one(
        'res.company', string='Company', default=_default_company,
        readonly=True,
        states={'draft': [('readonly', False)]})
    sale_count = fields.Integer(compute='_compute_sale_count')

    # Fields use to filter in tree view
    original_qty = fields.Float(
        string='Original quantity', compute='_compute_original_qty',
        search='_search_original_qty', default=0.0)
    ordered_qty = fields.Float(
        string='Ordered quantity', compute='_compute_ordered_qty',
        search='_search_ordered_qty', default=0.0)
    invoiced_qty = fields.Float(
        string='Invoiced quantity', compute='_compute_invoiced_qty',
        search='_search_invoiced_qty', default=0.0)
    remaining_qty = fields.Float(
        string='Remaining quantity', compute='_compute_remaining_qty',
        search='_search_remaining_qty', default=0.0)
    delivered_qty = fields.Float(
        string='Delivered quantity', compute='_compute_delivered_qty',
        search='_search_delivered_qty', default=0.0)

    @api.multi
    def _get_sale_orders(self):
        return self.mapped('line_ids.sale_lines.order_id')

    @api.depends('line_ids')
    def _compute_line_count(self):
        self.line_count = len(self.mapped('line_ids'))

    @api.multi
    def _compute_sale_count(self):
        for blanket_order in self:
            blanket_order.sale_count = len(blanket_order._get_sale_orders())

    @api.multi
    @api.depends(
        'line_ids.remaining_qty',
        'validity_date',
        'confirmed',
    )
    def _compute_state(self):
        today = fields.Date.today()
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for order in self:
            if not order.confirmed:
                order.state = 'draft'
            elif order.validity_date <= today:
                order.state = 'expired'
            elif float_is_zero(sum(order.line_ids.mapped('remaining_qty')),
                               precision_digits=precision):
                order.state = 'done'
            else:
                order.state = 'open'

    def _compute_original_qty(self):
        for bo in self:
            bo.original_qty = sum(bo.mapped('order_id.original_qty'))

    def _compute_ordered_qty(self):
        for bo in self:
            bo.ordered_qty = sum(bo.mapped('order_id.ordered_qty'))

    def _compute_invoiced_qty(self):
        for bo in self:
            bo.invoiced_qty = sum(bo.mapped('order_id.invoiced_qty'))

    def _compute_delivered_qty(self):
        for bo in self:
            bo.delivered_qty = sum(bo.mapped('order_id.delivered_qty'))

    def _compute_remaining_qty(self):
        for bo in self:
            bo.remaining_qty = sum(bo.mapped('order_id.remaining_qty'))

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment term
        """
        if not self.partner_id:
            self.payment_term_id = False
            return

        values = {
            'pricelist_id': (self.partner_id.property_product_pricelist and
                             self.partner_id.property_product_pricelist.id or
                             False),
            'payment_term_id': (self.partner_id.property_payment_term_id and
                                self.partner_id.property_payment_term_id.id or
                                False),
        }

        if self.partner_id.user_id:
            values['user_id'] = self.partner_id.user_id.id
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        self.update(values)

    @api.multi
    def copy_data(self, default=None):
        if default is None:
            default = {}
        default.update(self.default_get(['name', 'confirmed']))
        return super(BlanketOrder, self).copy_data(default)

    @api.multi
    def _validate(self):
        try:
            today = fields.Date.today()
            for order in self:
                assert order.validity_date, _("Validity date is mandatory")
                assert order.validity_date > today, \
                    _("Validity date must be in the future")
                assert order.partner_id, _("Partner is mandatory")
                assert len(order.line_ids) > 0, _("Must have some lines")
                order.line_ids._validate()
        except AssertionError as e:
            raise UserError(e)

    @api.multi
    def set_to_draft(self):
        for order in self:
            order.write({'state': 'draft'})
        return True

    @api.multi
    def action_confirm(self):
        self._validate()
        for order in self:
            sequence_obj = self.env['ir.sequence']
            if order.company_id:
                sequence_obj = sequence_obj.with_context(
                    force_company=order.company_id.id)
            name = sequence_obj.next_by_code('sale.blanket.order')
            order.write({'confirmed': True, 'name': name})
        return True

    @api.multi
    def action_cancel(self):
        for order in self:
            order.write({'state': 'expired'})
        return True

    @api.multi
    def action_view_sale_orders(self):
        sale_orders = self._get_sale_orders()
        action = self.env.ref('sale.action_orders').read()[0]
        if len(sale_orders) > 0:
            action['domain'] = [('id', 'in', sale_orders.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_sale_blanket_order_line(self):
        action = self.env.ref(
            'sale_blanket_order'
            '.act_open_sale_blanket_order_lines_view_tree').read()[0]
        lines = self.mapped('line_ids')
        if len(lines) > 0:
            action['domain'] = [('id', 'in', lines.ids)]
        return action

    @api.model
    def expire_orders(self):
        today = fields.Date.today()
        expired_orders = self.search([
            ('state', '=', 'open'),
            ('validity_date', '<=', today),
        ])
        expired_orders.modified(['validity_date'])
        expired_orders.recompute()

    @api.model
    def _search_original_qty(self, operator, value):
        bo_line_obj = self.env['sale.blanket.order.line']
        res = []
        bo_lines = bo_line_obj.search(
            [('original_qty', operator, value)])
        order_ids = bo_lines.mapped('order_id')
        res.append(('id', 'in', order_ids.ids))
        return res

    @api.model
    def _search_ordered_qty(self, operator, value):
        bo_line_obj = self.env['sale.blanket.order.line']
        res = []
        bo_lines = bo_line_obj.search(
            [('ordered_qty', operator, value)])
        order_ids = bo_lines.mapped('order_id')
        res.append(('id', 'in', order_ids.ids))
        return res

    @api.model
    def _search_invoiced_qty(self, operator, value):
        bo_line_obj = self.env['sale.blanket.order.line']
        res = []
        bo_lines = bo_line_obj.search(
            [('invoiced_qty', operator, value)])
        order_ids = bo_lines.mapped('order_id')
        res.append(('id', 'in', order_ids.ids))
        return res

    @api.model
    def _search_delivered_qty(self, operator, value):
        bo_line_obj = self.env['sale.blanket.order.line']
        res = []
        bo_lines = bo_line_obj.search(
            [('delivered_qty', operator, value)])
        order_ids = bo_lines.mapped('order_id')
        res.append(('id', 'in', order_ids.ids))
        return res

    @api.model
    def _search_remaining_qty(self, operator, value):
        bo_line_obj = self.env['sale.blanket.order.line']
        res = []
        bo_lines = bo_line_obj.search(
            [('remaining_qty', operator, value)])
        order_ids = bo_lines.mapped('order_id')
        res.append(('id', 'in', order_ids.ids))
        return res


class BlanketOrderLine(models.Model):
    _name = 'sale.blanket.order.line'
    _description = 'Blanket Order Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Description', track_visibility='onchange')
    sequence = fields.Integer()
    order_id = fields.Many2one(
        'sale.blanket.order', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Product', required=True)
    product_uom = fields.Many2one(
        'product.uom', string='Unit of Measure', required=True)
    price_unit = fields.Float(string='Price', required=True)
    date_schedule = fields.Date(string='Scheduled Date')
    original_qty = fields.Float(
        string='Original quantity', required=True, default=1,
        digits=dp.get_precision('Product Unit of Measure'))
    ordered_qty = fields.Float(
        string='Ordered quantity', compute='_compute_quantities',
        store=True)
    invoiced_qty = fields.Float(
        string='Invoiced quantity', compute='_compute_quantities',
        store=True)
    remaining_qty = fields.Float(
        string='Remaining quantity', compute='_compute_quantities',
        store=True)
    delivered_qty = fields.Float(
        string='Delivered quantity', compute='_compute_quantities',
        store=True)
    sale_lines = fields.One2many(
        'sale.order.line', 'blanket_order_line', string='Sale order lines')
    company_id = fields.Many2one(
        'res.company', related='order_id.company_id', store=True,
        readonly=True)
    partner_id = fields.Many2one(
        related='order_id.partner_id',
        string='Customer',
        readonly=True)
    user_id = fields.Many2one(
        related='order_id.user_id', string='Responsible',
        readonly=True)
    payment_term_id = fields.Many2one(
        related='order_id.payment_term_id', string='Payment Terms',
        readonly=True)
    pricelist_id = fields.Many2one(
        related='order_id.pricelist_id', string='Pricelist',
        readonly=True)

    def name_get(self):
        """Return special label when showing fields in chart update wizard."""
        result = []
        if self.env.context.get('from_sale_order'):
            for record in self:
                res = "[%s] - Date Scheduled: %s (remaining: %s)" % (
                    record.order_id.name,
                    record.date_schedule,
                    str(record.remaining_qty))
                result.append((record.id, res))
            return result
        return super(BlanketOrderLine, self).name_get()

    def _get_real_price_currency(self, product, rule_id, qty, uom,
                                 pricelist_id):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :param float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming
                   from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sale order"""
        # Copied and adapted from the sale module
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id\
               .discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist'\
                    and pricelist_item.base_pricelist_id\
                    and pricelist_item.base_pricelist_id\
                        .discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id\
                        .with_context(uom=uom.id).get_product_price_rule(
                            product, qty, self.order_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist'\
               and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = (product_currency or
                            (product.company_id and
                             product.company_id.currency_id) or
                            self.env.user.company_id.currency_id)
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(
                    product_currency, currency_id)

        product_uom = product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0

        return product[field_name] * uom_factor * cur_factor, currency_id.id

    @api.multi
    def _get_display_price(self, product):
        # Copied and adapted from the sale module
        self.ensure_one()
        pricelist = self.order_id.pricelist_id
        partner = self.order_id.partner_id
        if self.order_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=pricelist.id).price
        final_price, rule_id = pricelist.get_product_price_rule(
            self.product_id, self.original_qty or 1.0, partner)
        context_partner = dict(self.env.context, partner_id=partner.id,
                               date=fields.Date.today())
        base_price, currency_id = self.with_context(context_partner)\
            ._get_real_price_currency(
                self.product_id, rule_id, self.original_qty, self.product_uom,
                pricelist.id)
        if currency_id != pricelist.currency_id.id:
            currency = self.env['res.currency'].browse(currency_id)
            base_price = currency.with_context(context_partner).compute(
                base_price, pricelist.currency_id)
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

    @api.multi
    @api.onchange('product_id', 'original_qty')
    def onchange_product(self):
        if self.product_id:
            name = self.product_id.name
            self.product_uom = self.product_id.uom_id.id
            if self.order_id.pricelist_id and self.order_id.partner_id:
                self.price_unit = self._get_display_price(self.product_id)
            if self.product_id.code:
                name = '[%s] %s' % (name, self.product_id.code)
            if self.product_id.description_purchase:
                name += '\n' + self.product_id.description_purchase
            self.name = name

    @api.multi
    @api.depends(
        'sale_lines.order_id.state',
        'sale_lines.blanket_order_line',
        'sale_lines.product_uom_qty',
        'sale_lines.qty_delivered',
        'sale_lines.qty_invoiced',
        'original_qty',
    )
    def _compute_quantities(self):
        for line in self:
            sale_lines = line.sale_lines
            line.ordered_qty = sum(l.product_uom_qty for l in sale_lines if
                                   l.order_id.state != 'cancel' and
                                   l.product_id == line.product_id)
            line.invoiced_qty = sum(l.qty_invoiced for l in sale_lines if
                                    l.order_id.state != 'cancel' and
                                    l.product_id == line.product_id)
            line.delivered_qty = sum(l.qty_delivered for l in sale_lines if
                                     l.order_id.state != 'cancel' and
                                     l.product_id == line.product_id)
            line.remaining_qty = line.original_qty - line.ordered_qty

    @api.multi
    def _validate(self):
        try:
            for line in self:
                assert line.price_unit > 0.0, \
                    _("Price must be greater than zero")
                assert line.original_qty > 0.0, \
                    _("Quantity must be greater than zero")
        except AssertionError as e:
            raise UserError(e)
