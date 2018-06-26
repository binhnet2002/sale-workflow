# -*- coding: utf-8 -*-
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade

table_renames = [
    ('sale_order_line_group', 'procurement_group'),
]


def find_procurements(env):
    groups = env['procurement.group'].search([('order', '!=', False)])
    for group in groups:
        procurements = env['procurement.order'].search(
            [('sale_line_id', 'in', group.order.order_line)])
        procurements.write({'group_id': group.id})


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    openupgrade.rename_tables(env.cr, table_renames)
    find_procurements(env)
