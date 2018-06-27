# -*- coding: utf-8 -*-
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade

table_renames = [
    ('sale_order_line_group', 'procurement_group'),
]


def put_default_get_shipped(cr):
    # if the SO is not done it will be recomputed
    cr.execute("""
        UPDATE sale_order SET shipped = false; 
        UPDATE sale_order SET shipped = true where state='done';
    """)


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    openupgrade.rename_tables(env.cr, table_renames)
    put_default_get_shipped(env.cr)
