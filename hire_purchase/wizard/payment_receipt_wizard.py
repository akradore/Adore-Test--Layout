from datetime import datetime, timedelta
import time
from odoo.tools.float_utils import float_is_zero, float_compare
import odoo.addons.decimal_precision as dp
from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError
import threading
from odoo.exceptions import Warning
from datetime import date
from odoo.tools.translate import _
from odoo.exceptions import except_orm, Warning, RedirectWarning
import json


class PaymentReceiptWizard(models.TransientModel):
    _name = 'payment.receipt.wizard'
    _description = "Payment Receipt Wizard"
    release_ids = fields.Many2many('account.move',required=True)
    hp_id = fields.Many2one('account.hp','HP')
    release_ids_domain = fields.Char('Domain')
    
    ##for payment report reciept .................
    def get_max_Date(self):
        max_date = max([i.date for i in self.release_ids])
        final_date = ''
        if max_date:
            final_date = datetime.strptime(str(max_date), "%Y-%m-%d").strftime('%m/%d/%Y')
        return final_date
    
    @api.model
    def default_get(self, fields_list):
        res = super(PaymentReceiptWizard, self).default_get(fields_list)
        res.update({'hp_id':self._context.get('active_id')})
        loan_obj = self.env['account.hp'].browse(self._context.get('active_id'))
        res.update({'release_ids_domain':[('id','in',[i.release_number.id for i in loan_obj.repayment_details])]})
        if res.get('release_ids_domain'):
            res.update({'release_ids_domain':res.get('release_ids_domain')})
        return res

    def print_payment_receipt(self):
        datas = {}
        if self._context.get('active_id'):
            loan_obj = self.env['account.hp'].browse(self._context.get('active_id'))
            datas.update({'loan_obj':loan_obj})
        return self.env.ref('hire_purchase.payment_receipt_id').report_action(self)
    
    def get_data(self):
        move_lines = self.env['account.move.line'].search([('credit','>',0),('move_id','in',[i.id for i in self.release_ids]),('acc_hp_id','=',self.hp_id.id)])
        data_to_return = {'move_lines':move_lines,'sum':round(sum([i.credit for i in move_lines]))}
        lang_code = self.env.context.get('lang') or 'en_US'
        lang = self.env['res.lang']
        lang_id = lang._lang_get(lang_code)
        date_format = lang_id.date_format
        data_to_return.update({'date_format':date_format})
        return data_to_return
    