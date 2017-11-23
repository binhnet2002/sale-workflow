# -*- coding: utf-8 -*-

from openerp import api, fields, models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ['sale.order', 'tier.validation']
    _state_to = 'sale'