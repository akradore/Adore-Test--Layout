import logging
from odoo import api, fields, models

_logger = logging.getLogger("Hp Charges")

class HpCharges(models.Model):
    _name = 'hp.charges'
    _description = "HP Charges"
    _rec_name = 'description'

    date = fields.Date(string="Date", )
    hp_account_id = fields.Many2one(comodel_name="account.hp", string="HP Account", )
    description = fields.Char(string="Description",)
    amount = fields.Float(string="Charge Amount", )
    company_id = fields.Many2one("res.company", string="Company")
    product_id = fields.Many2one('product.product', string='Finance Product')
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner",)

    @api.model
    def create(self,values):
        try:
            res = super(HpCharges,self).create(values)
            journal = self.env['account.journal'].search(
                [('code', '=', 'INV'), ('type', '=', 'sale'), ('company_id', '=', values.get('company_id', False))])
            invoice_type = 'out_invoice'
            amount = res.amount
            if values.get('amount') < 0:
                invoice_type = 'out_refund'
                amount = amount * (-1)
            journal_entry = self.env['account.move'].create({
                'invoice_date':res.date,
                'journal_id':journal.id,
                'ref':res.description,
                'type':invoice_type,
                'sale_type':'hire_purchase',
                'partner_id':res.partner_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': res.product_id.id,
                    'price_unit': amount,
                    'account_id': res.product_id.property_account_income_id.id,
                    'quantity': 1.0,
                    'name': res.product_id.name
                })]
            })
            _logger.info("Journal Entry {0} created for HP Charges {1}".format(journal_entry.ref,res.description))
            journal_entry.mapped('line_ids').write({'acc_hp_id':res.hp_account_id.id})
            journal_entry.post()
        except Exception as e:
            _logger.info("Something went wrong while creating HP Charges:{0}".format(e))
        return res
