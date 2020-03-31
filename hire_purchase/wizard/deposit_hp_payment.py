from datetime import datetime

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)
class DepositHpPayment(models.TransientModel):
    _name = 'deposit.hp.payment'
    _description = "Deposit Payment HP"

    payment_type = fields.Selection(string="Payment Type",
                                    selection=[('send', 'Send Money'), ('receive', 'Receive Money'), ('internal','Internal Transfer')])
    partner_id = fields.Many2one("res.partner", string="Partner")
    journal_id = fields.Many2one('account.journal',)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')])
    payment_date = fields.Date(string="Date",)
    amount = fields.Float(string="Amount",)
    memo = fields.Char(string="Memo",)

    @api.model
    def default_get(self,fields):
        res = super(DepositHpPayment,self).default_get(fields)
        if self._context.get('active_model','') == 'account.hp':
            account_hp = self.env['account.hp'].browse(self._context.get('active_id'))
            res['payment_type'] = 'receive'
            res['partner_type'] = 'customer'
            res['partner_id'] = account_hp.partner_id.id
            res['payment_date'] = datetime.today()
            res['amount'] = account_hp.hp_deposit_outstanding or ''
            res['memo'] = account_hp.name or ''
        return res

    def validate_hp_payment(self):
        account_hp = self.env['account.hp'].browse(self._context.get('active_id'))
        if not self.journal_id.id:
            raise ValidationError(_("Please select the journal for payment"))
        try:
            if round(account_hp.hp_deposit_outstanding, 2) == round(self.amount,2):
                if account_hp.reference_checks_done:
                    account_hp.confirm_hp_sale_order()
                else:
                    account_hp.stage_id = self.env.ref('hire_purchase.hp_to_reference_check').id

            invoice = False
            if account_hp.sale_order_id.state == 'done' and len(account_hp.sale_order_id.invoice_ids.ids):
                invoice = [(4, account_hp.sale_order_id.invoice_ids.ids[0], 0)]

            payment_method_id = self.env['account.payment.method'].search(
                [('name', '=', 'Manual'), ('payment_type', '=', 'inbound')], limit=1)
            account_payment_id = self.env['account.payment'].create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': account_hp.partner_id.id,
                'payment_date': self.payment_date,
                'amount': round(self.amount,2),
                'journal_id': self.journal_id.id,
                'payment_method_id': payment_method_id.id,
                'communication': "HP Account Installment Payment: " + account_hp.hp_id,
                'invoice_ids': invoice,
                'hp_id': account_hp.id,
            })

            payment_posted = account_payment_id.post()
            payment_move_lines = self.env['account.move.line'].search([('payment_id','=',account_payment_id.id),('debit','!=',0.0)])
            if len(payment_move_lines):
                payment_move_lines.write({'analytic_account_id': account_hp.id})

            if payment_posted:
                account_hp.hp_deposit_paid += self.amount
            if round(account_hp.hp_deposit_outstanding, 2) == round(self.amount,2) and not account_hp.reference_checks_done:
                    account_hp.message_post(body="<b>Final Payment Accepted, Reference Check is incomplete.</b>")
            return account_payment_id
        except Exception as e:
            raise ValidationError(_("{0}".format(e)))

    def validate_print_hp_payment(self):
        validated_payment = self.validate_hp_payment()
        if validated_payment:
            return self.env.ref("account.action_report_payment_receipt").report_action(validated_payment)