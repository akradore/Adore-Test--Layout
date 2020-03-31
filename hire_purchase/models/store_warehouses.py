from odoo import api, fields, models


class StoreWarehouse(models.Model):
    _name = 'store.warehouse'
    _description = 'Warehouses for stores'

    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse")
    sequence = fields.Integer(string="Sequence", size=32)

    _order = 'sequence'