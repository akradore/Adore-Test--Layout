from odoo import fields, models, api, _
class Classifications(models.Model):
    
    _name = 'hp.classifications'
    _description = "HP classifications"
    
    name = fields.Char(string="Name",  required=True)
    min = fields.Integer(string="Min Days in Arrears", required=True)
    max = fields.Integer(string="Max Days in Arrears", required=True)