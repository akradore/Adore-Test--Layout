from odoo import api, fields, models

class account_hp_disbursement(models.Model):
    _name = "account.hp.disbursement"
    _description = 'Account HP Disbursement line'

    release_number = fields.Many2one('account.move','Release Number')
    name = fields.Many2one('res.partner','Partner Name',required=True)
    bill_date = fields.Date("Bill Date",required=True)
    disbursement_amt = fields.Float("Amount",required=True)
    hp_id = fields.Many2one('account.hp')
