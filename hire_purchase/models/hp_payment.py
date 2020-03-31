from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError, Warning
from dateutil.relativedelta import relativedelta
from datetime import date
import datetime
from pickle import INST


class HPPaymentDetails(models.Model):
    _name = 'payment.details'
    _description = "Payment Details"
    
    name = fields.Char("Payment type")
    pay_date = fields.Date("Date")
    move_id = fields.Many2one('account.move')
    line_id = fields.Many2one('account.hp.installment')
    prin_amt = fields.Float("Principal Amount")
    int_amt = fields.Float("Interest Amount")
    fees_amt = fields.Float("Fees Amount")
    base_fee_paid = fields.Float("Base Fee Paid")
    base_fee_tax_paid = fields.Float("Base Fee Tax Paid")
    late_fee_amt = fields.Float("Late Fee Amount")
    base_late_fee_amt = fields.Float("Base Paid Late Fee")
    base_late_fee_amt_tx = fields.Float("Late Fee Amount Tax")
    state = fields.Selection([('draft','Draft'),('cancel','Cancel')], string="State")


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    hp_id = fields.Many2one('account.hp', string='HP Account')


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    store_id = fields.Many2one("stores", string="Store")

class HPPayment(models.Model):
    _name = 'hp.payment'
    _description = "Hp Account Payment"
    
    name = fields.Char(readonly=True, copy=False) # The name is attributed upon post()
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ('bank', 'cash'))])
    amount = fields.Monetary(string='Payment Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True, copy=False)
    hp_id = fields.Many2one('account.hp', "HP Ref.")
    late_fee = fields.Float(string='Late Fees')
    is_late_fee = fields.Boolean("Is Late Fee")
    
    @api.model
    def default_get(self, fields):
        rec = super(HPPayment, self).default_get(fields)
        if not self._context:
            return rec
        active_id = self._context.get('active_id')
        hp_id = self.env[self._context.get('active_model')].browse(active_id)
        rec['hp_id'] = hp_id.id
        current_date = datetime.date.today()
        total = 0.0
        for line in hp_id.installment_id:
            if line.state != 'paid' and line.date:
                date_object = (line.date+relativedelta(days = hp_id.grace_period))
                if current_date >= date_object:
                    rec['is_late_fee'] = True
                total += line.late_fee
        rec['late_fee'] = total
        return rec
    
    @api.onchange('journal_id')
    def _onchange_disburse_journal(self):
        if self.journal_id:
            active_id = self._context.get('active_id')
            acc_hp = self.env['account.hp'].browse(active_id)
            self.currency_id = self.journal_id.currency_id or acc_hp.company_id.currency_id

    def action_validate_hp_payment(self):
        """ Posts a payment of hp installment.
        """
        if self.amount == 0.0:
            raise UserError(_("Please Enter Installment Amount."))
        if any(len(record.hp_id) != 1 for record in self):
            raise UserError(_("This method should only be called to process a single HP Account's payment."))
        # Create Payment
        payment_method_id = self.env['account.payment.method'].search([('name', '=', 'Manual'), ('payment_type', '=', 'inbound')], limit=1)
        if not payment_method_id:
            raise ValidationError(_("No Payment Method Found: 'Manual'."))
        account_payment_id = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.hp_id.partner_id.id,
            'payment_date': self.payment_date,
            'amount': self.amount,
            'journal_id': self.journal_id.id,
            'payment_method_id': payment_method_id.id,
            'communication': "HP Account Installment Payment: " + self.hp_id.hp_id,
            'hp_id': self.hp_id.id,
        })
        account_payment_id.post()
        payment_move_lines = self.env['account.move.line'].search([('payment_id','=',account_payment_id.id),('debit','!=',0.0)])
        if len(payment_move_lines):
            payment_move_lines.write({'analytic_account_id':self.hp_id.id})

        receivable_line = account_payment_id.mapped('move_line_ids').filtered('credit').id
        invoice_id = self.hp_id.sale_order_id.invoice_ids.filtered(lambda x:x.type == 'out_invoice' and x.amount_residual != 0.0)
        payment__amount_left = self.reconcile_installment_lines(payment=account_payment_id,receivable_line=receivable_line,invoice_id=invoice_id)

    def reconcile_installment_lines(self,payment=False,receivable_line=False,invoice_id=False):
        if payment and receivable_line:
            components_sequence = self.hp_id._get_component_sequence()
            open_instalments = self.hp_id.installment_id.filtered(lambda x:x.state in ['open','partial_paid']).sorted(lambda x:x.id)
            payment_amount = payment.amount
            orignal_payment = payment.amount
            for instalment in open_instalments:
                journal_entries = self.env['account.move.line'].search([('acc_hp_id','=',self.hp_id.id),('hp_instalment_id','=',instalment.id)])
                journal_entries = journal_entries.mapped('move_id').filtered(lambda x:x.amount_residual != 0.0)
                journal_entries = journal_entries.sorted(lambda x:components_sequence.index(x.ref.split('-')[0]))
                unreconcilled_enteries = [x for x in journal_entries]
                reconciled_amount = 0.0
                for index,move in enumerate(journal_entries):
                    if payment_amount <= 0:
                        break
                    move.js_assign_outstanding_line(receivable_line)
                    reconciled_amount = move.amount_total - move.amount_residual
                    if move.amount_residual ==  0.0 or reconciled_amount == payment_amount:
                        unreconcilled_enteries.pop()
                    payment_amount-=round(reconciled_amount,2)

                if payment_amount > 0.0 and invoice_id.id:
                    before_amount_residual = invoice_id.amount_residual
                    invoice_id.js_assign_outstanding_line(receivable_line)
                    reconciled_amount = before_amount_residual - invoice_id.amount_residual
                    payment_amount -= round(reconciled_amount,2)

                if orignal_payment != payment:
                    if len(unreconcilled_enteries) and len(unreconcilled_enteries) < len(journal_entries):
                        instalment.state = 'partial_paid'
                    elif not len(unreconcilled_enteries) and not(reconciled_amount >= instalment.capital):
                        instalment.state = 'partial_paid'
                    elif (not len(unreconcilled_enteries) and reconciled_amount >= instalment.capital):
                        instalment.state = 'paid'

                if payment_amount == 0.0:
                    break

            return payment_amount
        # lst = []
        # move_line_id = account_payment_id.move_line_ids.filtered(lambda l:l.partner_id.property_account_receivable_id.id == l.account_id.id)
        # lst.append(move_line_id.id)
        # move_line_ids = self.env['account.move.line'].search([('acc_hp_id','=',account_payment_id.hp_id.id),
        #                                                     ('move_id.has_reconciled_entries','=',False),
        #                                                      ('account_id','=',account_payment_id.partner_id.property_account_receivable_id.id)
        #                                                       ])
        # data_dict =  [{'id': None, 'type': None, 'mv_line_ids': lst, 'new_mv_line_dicts': []}]
        # obj = self.env['account.reconciliation.widget']
        # obj.process_move_lines(data_dict)

        # list_mv_line = []
        # if self.amount:
        #     list_mv_line.append((0, 0, {'account_id': self.hp_id.partner_id.property_account_receivable_id.id,
        #                                 'name': self.hp_id.hp_id,
        #                                 'debit': 0.00,
        #                                 'credit': self.amount,
        #                                 'partner_id': self.hp_id.partner_id.id,
        #                                 'analytic_account_id': self.hp_id.anal_acc.id,
        #                                 'acc_hp_id': self.hp_id.id,
        #                                 }))
        #     list_mv_line.append((0, 0, {'account_id': self.journal_id.default_debit_account_id.id,
        #                                 'name': self.hp_id.hp_id,
        #                                 'debit': self.amount,
        #                                 'credit': 0.00,
        #                                 'partner_id': self.hp_id.partner_id.id,
        #                                 'analytic_account_id': self.hp_id.anal_acc.id,
        #                                 'acc_hp_id': self.hp_id.id,
        #                                 }))
        #     move_id = self.env['account.move'].create({
        #         'journal_id': self.journal_id.id,
        #         'name': "Hp Account Installment For: " + self.hp_id.hp_id,
        #         'line_ids': list_mv_line,
        #         'sale_type': self.hp_id.sale_order_id.sale_type,
        #         'store_id': self.hp_id.store_id.id
        #     })
        #     move_id.post()

        # if self.amount == 0.0:
        #     raise UserError(_("Please Enter Installment Amount."))
        # if any(len(record.hp_id) != 1 for record in self):
        #     raise UserError(_("This method should only be called to process a single hp's payment."))
        # move_id = self.post()
        # for line in move_id.line_ids:
        #     self.hp_id.write({'move_id':[(4,line.id)]})
        # payment_id = self.env['account.hp.repayment'].create({
        #      'name' : self.hp_id.partner_id.id,
        #      'pay_date' : self.payment_date,
        #      'amt' : self.amount,
        #      'hp_id' : self.hp_id.id,
        #      'release_number': move_id.id,
        #      'is_button_visible':True
        #     })
        # self.hp_id.write({'repayment_details':[(4,payment_id.id)]})
        # return move_id

    ##calculate taxes for non included .......................
    def get_interest_vals(self, tx_tot, account):
        if tx_tot:
            taxes_vals = {}
            taxes_vals.update({'partner_id':self.hp_id.partner_id.id,'account_id':account.id, 'debit':0.0, 'credit':tx_tot})
            return taxes_vals
    
    def get_fees_vals(self, type_line):
        
        fees = {}
        if type_line.product_amt:
            fees.update({'partner_id':self.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':type_line.product_amt})
        return fees
    
    ## total calculatin of tax for fee calculation in installment ................
    def get_tax_total(self, tx_ids, amount):
        tax_amt = 0.0
        for tx in tx_ids:
            tax = round(amount - ((amount * 100) / (100 + tx.amount)),2)
            tax_amt = tax_amt + tax
        return tax_amt
    
    ## get value without taxess .............
    def get_tax_value(self, tax_ids, amount):
        amt = 0.0
        for tx in tax_ids:
            tax = 100
            tax = tax + tx.amount
            amt = (amount * 100) / tax
        return amt

    # def post(self):
    #     list_mv_line = []
    #     if self.late_fee > 0.0:
    #         self.amount = self.amount - self.late_fee
    #     amount = 0.0
    #     move_lines_dr = {}
    #     sequence_dict = {}
    #     total_sequnce = []
    #     amount_currency = False
    #     today = datetime.datetime.today().date()
    #
    #     if not self.hp_id.company_id.currency_id:
    #         raise UserError('Please Define Company Currency')
    #     company_curren = self.hp_id.company_id.currency_id
    #
    #     if not self.currency_id:
    #         raise UserError('Please Define Company Currency')
    #     currency_id = self.currency_id
    #
    #     name_des = "Hp Account Installment For: "
    #     move_vals = {}
    #     if self.hp_id.hp_type:
    #         for type_line in self.hp_id.hp_type.hp_component_ids:
    #             if type_line.type == 'principal':
    #                 if not type_line.gl_code:
    #                     raise UserError(_('Please Configure GLCode For Principal Amount'))
    #                 sequence_dict.update({type_line.sequence:type_line.type})
    #                 total_sequnce.append(type_line.sequence)
    #             if type_line.type == 'int_rate':
    #                 if not type_line.gl_code:
    #                     raise UserError(_('Please Configure GLCode For Interest Amount'))
    #                 sequence_dict.update({type_line.sequence:type_line.type})
    #                 total_sequnce.append(type_line.sequence)
    #             if type_line.type == 'fees':
    #                 sequence_dict.update({type_line.sequence:type_line.type})
    #                 total_sequnce.append(type_line.sequence)
    #
    #     move_vals.update({'name':'/','ref':name_des + self.hp_id.hp_id,\
    #                           'date':self.payment_date,'journal_id':self.journal_id.id,\
    #                           })
    #     if currency_id.id != company_curren.id:
    #         amount_currency = self.amount
    #         amount = company_curren.with_context(date=self.payment_date).compute(self.amount, currency_id)
    #         move_lines_dr.update({'debit':amount,
    #                               'amount_currency': amount_currency,
    #                               'currency_id': currency_id.id
    #                               })
    #     if not amount_currency:
    #         move_lines_dr.update({'debit': self.amount,})
    #     move_lines_dr.update({'account_id':self.journal_id.default_debit_account_id.id,
    #                           'name':name_des+ self.hp_id.hp_id,
    #                           'credit':0.0,
    #                           'partner_id':self.hp_id.partner_id.id,
    #                           })
    #     list_mv_line.append((0, 0, move_lines_dr))
    #
    #     seq_id = self.hp_id.hp_type.hp_component_ids.ids
    #     search_ids = self.env['hp.component.line'].search([('id','in', seq_id)],  order='sequence')
    #     break_loop = False
    #     affected_line_list = []
    #     for installment_line in self.hp_id.installment_id:
    #         if break_loop:
    #             break
    #         for type_line in search_ids:
    #             move_lines_cr_capital = {}
    #             move_lines_cr_int = {}
    #             move_line_cr_int_tx = {}
    #             is_paid_capital = False
    #             is_paid_int = False
    #             is_paid_fee = False
    #             if installment_line.outstanding_prin or installment_line.outstanding_int or installment_line.outstanding_fees:
    #                 ## this for principal amount ....................
    #                 if installment_line not in affected_line_list:
    #                     affected_line_list.append(installment_line)
    #                 if type_line.type == 'principal':
    #                     if installment_line.outstanding_prin > 0.0 and  self.amount >= installment_line.outstanding_prin:
    #                         self.amount = self.amount - installment_line.outstanding_prin
    #                         if currency_id.id != company_curren.id:
    #                             amount_currency = installment_line.outstanding_prin
    #                             amount = company_curren.with_context(date=self.payment_date).compute(installment_line.outstanding_prin, currency_id)
    #                         else:
    #                             amount_currency = False
    #                         if not amount_currency:
    #                             move_lines_cr_capital.update({
    #                                     'account_id':type_line.gl_code.id,
    #                                     'name':name_des+ self.hp_id.hp_id,
    #                                     'credit':installment_line.outstanding_prin,
    #                                     'debit':0.0,
    #                                     'partner_id':self.hp_id.partner_id.id,
    #                                     })
    #                             installment_line.with_context({'prin':installment_line.outstanding_prin}).onchange_principle()
    #                         else:
    #                             move_lines_cr_capital.update({
    #                                     'account_id':type_line.gl_code.id,
    #                                     'name':name_des+ self.hp_id.hp_id,
    #                                     'credit':amount,
    #                                     'debit':0.0,
    #                                     'partner_id':self.hp_id.partner_id.id,
    #                                     'amount_currency':-amount_currency,
    #                                     'currency_id':currency_id.id
    #                                     })
    #                             installment_line.with_context({'prin':amount}).onchange_principle()
    #                         list_mv_line.append((0, 0,move_lines_cr_capital))
    #                         installment_line.write({'outstanding_prin':0.0,'due_principal':0.0,'paid_prin':installment_line.outstanding_prin})
    #                         is_paid_capital = True
    #
    #                         if not self.amount:
    #                             if not self.late_fee:
    #                                 break_loop = True
    #                             break
    #                     else:
    #                         if self.amount <= installment_line.outstanding_prin:
    #                             self.amount = round(self.amount,2)
    #                             if currency_id.id != company_curren.id:
    #                                 amount_currency = self.amount
    #                                 amount = company_curren.with_context(date=self.payment_date).compute(self.amount, currency_id)
    #                             else:
    #                                 amount_currency = False
    #                             if not amount_currency:
    #                                 move_lines_cr_capital.update({
    #                                     'account_id':type_line.gl_code.id,
    #                                     'name':name_des+ self.hp_id.hp_id,
    #                                     'credit':self.amount,
    #                                     'debit':0.0,
    #                                     'partner_id':self.hp_id.partner_id.id,
    #                                     })
    #                                 installment_line.with_context({'prin':self.amount}).onchange_principle()
    #                             else:
    #                                 move_lines_cr_capital.update({
    #                                     'account_id':type_line.gl_code.id,
    #                                     'name':name_des+ self.hp_id.hp_id,
    #                                     'credit':amount,
    #                                     'debit':0.0,
    #                                     'partner_id':self.hp_id.partner_id.id,
    #                                     'amount_currency':-amount_currency,
    #                                     'currency_id':currency_id.id
    #                                     })
    #                                 installment_line.with_context({'prin':amount}).onchange_principle()
    #                             self.amount = installment_line.outstanding_prin - self.amount
    #                             if installment_line.date <= today:
    #                                 installment_line.write({'outstanding_prin':self.amount,'due_principal':self.amount, 'paid_prin': installment_line.outstanding_prin -self.amount})
    #                             else:
    #                                 installment_line.write({'outstanding_prin':self.amount,'due_principal':0.0, 'paid_prin':installment_line.outstanding_prin - self.amount})
    #                             list_mv_line.append((0, 0, move_lines_cr_capital))
    #                             self.amount = 0.0
    #                             if not self.late_fee:
    #                                 break_loop = True
    #                             break
    #                         if is_paid_capital and is_paid_fee and is_paid_int:
    #                             installment_line.write({'state':'paid'})
    #
    #                 ## next for interest amount ..............
    #                 if type_line.type == 'int_rate':
    #                     if installment_line.outstanding_int > 0.0 and self.amount >= installment_line.outstanding_int:
    #                         if type_line.tax_id:
    #                             tx_tot_int = self.get_tax_total(type_line.tax_id, installment_line.outstanding_int)
    #                             new_amt = round(installment_line.outstanding_int - tx_tot_int, 2)
    #                             if currency_id.id != company_curren.id:
    #                                 amount_currency = new_amt
    #                                 amount = company_curren.with_context(date=self.payment_date).compute(new_amt, currency_id)
    #                             else:
    #                                 amount_currency = False
    #                             if not amount_currency:
    #                                 move_lines_cr_int.update({
    #                                         'account_id':type_line.gl_code.id,
    #                                         'name':name_des+ self.hp_id.hp_id,
    #                                         'credit':new_amt,
    #                                         'debit':0.0,
    #                                         'partner_id':self.hp_id.partner_id.id,
    #                                         })
    #                                 installment_line.with_context({'int':new_amt}).onchange_interest()
    #                             else:
    #                                 move_lines_cr_int.update({
    #                                         'account_id':type_line.gl_code.id,
    #                                         'name':name_des+ self.hp_id.hp_id,
    #                                         'credit':amount,
    #                                         'debit':0.0,
    #                                         'partner_id':self.hp_id.partner_id.id,
    #                                         'amount_currency':-amount_currency,
    #                                         'currency_id':currency_id.id
    #                                         })
    #                                 installment_line.with_context({'int':amount}).onchange_interest()
    #
    #                             list_mv_line.append((0, 0, move_lines_cr_int))
    #                             if tx_tot_int:
    #                                 if currency_id.id != company_curren.id:
    #                                     amount_currency = tx_tot_int
    #                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_tot_int, currency_id)
    #                                 else:
    #                                     amount_currency = False
    #                                 if not amount_currency:
    #                                     for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                         move_line_cr_int_tx.update({
    #                                                 'account_id':tax.account_id.id,
    #                                                 'name':name_des+ self.hp_id.hp_id,
    #                                                 'credit':tx_tot_int*(tax.factor_percent/100),
    #                                                 'debit':0.0,
    #                                                 'partner_id':self.hp_id.partner_id.id,
    #                                             })
    #                                         list_mv_line.append((0, 0, move_line_cr_int_tx))
    #                                     installment_line.with_context({'int': tx_tot_int}).onchange_interest()
    #                                 else:
    #                                     for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                         move_line_cr_int_tx.update({
    #                                                 'account_id':tax.account_id.id,
    #                                                 'name':name_des+ self.hp_id.hp_id,
    #                                                 'credit':amount*(tax.factor_percent/100),
    #                                                 'debit':0.0,
    #                                                 'partner_id':self.hp_id.partner_id.id,
    #                                                 'amount_currency':-amount_currency,
    #                                                 'currency_id':currency_id.id
    #                                             })
    #                                         list_mv_line.append((0, 0, move_line_cr_int_tx))
    #                                     installment_line.with_context({'int': amount}).onchange_interest()
    #
    #                         else:
    #                             if currency_id.id != company_curren.id:
    #                                     amount_currency = installment_line.outstanding_int
    #                                     amount = company_curren.with_context(date=self.payment_date).compute(installment_line.outstanding_int, currency_id)
    #                             else:
    #                                 amount_currency = False
    #                             if not amount_currency:
    #                                 move_lines_cr_int.update({
    #                                         'account_id':type_line.gl_code.id,
    #                                         'name':name_des+ self.hp_id.hp_id,
    #                                         'credit':installment_line.outstanding_int,
    #                                         'debit':0.0,
    #                                         'partner_id':self.hp_id.partner_id.id,
    #                                         })
    #                                 installment_line.with_context({'int':installment_line.outstanding_int}).onchange_interest()
    #                             else:
    #                                 move_lines_cr_int.update({
    #                                         'account_id':type_line.gl_code.id,
    #                                         'name':name_des+ self.hp_id.hp_id,
    #                                         'credit':amount,
    #                                         'debit':0.0,
    #                                         'partner_id':self.hp_id.partner_id.id,
    #                                         'amount_currency':-amount_currency,
    #                                         'currency_id':currency_id.id
    #                                         })
    #                                 installment_line.with_context({'int':amount}).onchange_interest()
    #
    #                             list_mv_line.append((0, 0, move_lines_cr_int))
    #
    #                         self.amount = self.amount - installment_line.outstanding_int
    #                         installment_line.write({'outstanding_int':0.0,'due_interest':0.0,'paid_int':installment_line.outstanding_int})
    #                         is_paid_int = True
    #
    #                         if not self.amount:
    #                             if not self.late_fee:
    #                                 break_loop = True
    #                             break
    #
    #                     else:
    #                         if self.amount <= installment_line.outstanding_int:
    #                             self.amount = round(self.amount, 2)
    #                             if type_line.tax_id:
    #                                 tx_tot_int = self.get_tax_total(type_line.tax_id, self.amount)
    #                                 new_amt = self.amount - tx_tot_int
    #
    #                                 if currency_id.id != company_curren.id:
    #                                     amount_currency = new_amt
    #                                     amount = company_curren.with_context(date=self.payment_date).compute(new_amt, currency_id)
    #                                 else:
    #                                     amount_currency = False
    #                                 if not amount_currency:
    #                                     move_lines_cr_int.update({
    #                                             'account_id':type_line.gl_code.id,
    #                                             'name':name_des+ self.hp_id.hp_id,
    #                                             'credit':new_amt,
    #                                             'debit':0.0,
    #                                             'partner_id':self.hp_id.partner_id.id,
    #                                             })
    #                                     installment_line.with_context({'int':new_amt}).onchange_interest()
    #                                 else:
    #                                     move_lines_cr_int.update({
    #                                             'account_id':type_line.gl_code.id,
    #                                             'name':name_des+ self.hp_id.hp_id,
    #                                             'credit':amount,
    #                                             'debit':0.0,
    #                                             'partner_id':self.hp_id.partner_id.id,
    #                                             'amount_currency':-amount_currency,
    #                                             'currency_id':currency_id.id
    #                                             })
    #                                     installment_line.with_context({'int':amount}).onchange_interest()
    #
    #                                 list_mv_line.append((0, 0, move_lines_cr_int))
    #                                 if tx_tot_int:
    #                                     if currency_id.id != company_curren.id:
    #                                         amount_currency = tx_tot_int
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(tx_tot_int, currency_id)
    #                                     else:
    #                                         amount_currency = False
    #                                     if not amount_currency:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             move_line_cr_int_tx.update({
    #                                                     'account_id':tax.account_id.id,
    #                                                     'name':name_des+ self.hp_id.hp_id,
    #                                                     'credit':tx_tot_int*(tax.factor_percent/100),
    #                                                     'debit':0.0,
    #                                                     'partner_id':self.hp_id.partner_id.id,
    #                                                     })
    #                                             list_mv_line.append((0, 0, move_line_cr_int_tx))
    #                                         installment_line.with_context({'int':tx_tot_int}).onchange_interest()
    #                                     else:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             move_line_cr_int_tx.update({
    #                                                     'account_id':tax.account_id.id,
    #                                                     'name':name_des+ self.hp_id.hp_id,
    #                                                     'credit':amount*(tax.factor_percent/100),
    #                                                     'debit':0.0,
    #                                                     'partner_id':self.hp_id.partner_id.id,
    #                                                     'amount_currency':-amount_currency,
    #                                                     'currency_id':currency_id.id
    #                                                     })
    #                                             list_mv_line.append((0, 0, move_line_cr_int_tx))
    #                                         installment_line.with_context({'int':amount}).onchange_interest()
    #
    #                             else:
    #                                 if currency_id.id != company_curren.id:
    #                                         amount_currency = self.amount
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(self.amount, currency_id)
    #                                 else:
    #                                     amount_currency = False
    #                                 if not amount_currency:
    #                                     move_lines_cr_int.update({
    #                                             'account_id':type_line.gl_code.id,
    #                                             'name':name_des+ self.hp_id.hp_id,
    #                                             'credit':self.amount,
    #                                             'debit':0.0,
    #                                             'partner_id':self.hp_id.partner_id.id,
    #                                             })
    #                                     installment_line.with_context({'int':self.amount}).onchange_interest()
    #                                 else:
    #                                     move_lines_cr_int.update({
    #                                             'account_id':type_line.gl_code.id,
    #                                             'name':name_des+ self.hp_id.hp_id,
    #                                             'credit':amount,
    #                                             'debit':0.0,
    #                                             'partner_id':self.hp_id.partner_id.id,
    #                                             'amount_currency':-amount_currency,
    #                                             'currency_id':currency_id.id
    #                                             })
    #                                     installment_line.with_context({'int':amount}).onchange_interest()
    #                                 list_mv_line.append((0, 0, move_lines_cr_int))
    #
    #                             self.amount = installment_line.outstanding_int - self.amount
    #                             # if datetime.datetime.strptime(installment_line.date, "%Y-%m-%d").date() <= today:
    #                             if installment_line.date <= today:
    #                                 installment_line.write({'outstanding_int':self.amount,'due_interest':self.amount, 'paid_int':installment_line.outstanding_int - self.amount})
    #                             else:
    #                                 installment_line.write({'outstanding_int':self.amount,'due_interest': 0.0, 'paid_int':installment_line.outstanding_int - self.amount})
    #                             self.amount = 0.0
    #                             if not self.late_fee:
    #                                 break_loop = True
    #                             break
    #                         if is_paid_capital and is_paid_fee and is_paid_int:
    #                             installment_line.write({'state':'paid'})
    #                 ##next for fees calculation ............
    #                 if type_line.type == 'fees':
    #                     if not type_line.gl_code:
    #                         raise UserError(_('Please Configure GLCode For fees Amount'))
    #                     for fees_line in installment_line.fee_lines:
    #                         fees_dict = {}
    #                         interest_dict = {}
    #                         if fees_line.product_id.id == type_line.product_id.id and fees_line.is_paid == False:
    #                             fees_line_base = round(fees_line.base - fees_line.base_paid, 2)
    #                             fees_line_tax = round(fees_line.tax - fees_line.tax_paid, 2)
    #                             if fees_line_base > 0.0 and self.amount >= fees_line_base + fees_line_tax:
    #                                 total_paid_amount = 0
    #                                 if type_line.tax_id:
    #                                     rm_tx = self.get_tax_value(type_line.tax_id, fees_line_base)
    #                                     fees_line_tax = fees_line_base - rm_tx
    #                                     fees_line_base = fees_line_base - fees_line_tax
    #                                 if fees_line_base:
    #                                     base_amt = fees_line_base
    #                                     if currency_id.id != company_curren.id:
    #                                         amount_currency = base_amt
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(base_amt, currency_id)
    #                                     else:
    #                                         amount_currency = False
    #                                     if not amount_currency:
    #                                         fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':base_amt})
    #                                     else:
    #                                         fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,\
    #                                                           'debit':0.0, 'credit':amount, 'amount_currency':-amount_currency,
    #                                                           'currency_id':currency_id.id })
    #                                     installment_line.with_context({'fee':fees_dict.get('credit')}).onchange_fees()
    #
    #                                     total_paid_amount = total_paid_amount + base_amt
    #                                 if type_line.tax_id:
    #                                     tx_tot = fees_line_tax
    #                                     fee_credit = 0.0
    #                                     if currency_id.id != company_curren.id:
    #                                         amount_currency = tx_tot
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(tx_tot, currency_id)
    #                                     else:
    #                                         amount_currency = False
    #                                     if not amount_currency:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             interest_dict = self.get_interest_vals(tx_tot*(tax.factor_percent/100), tax.account_id)
    #                                             fee_credit += interest_dict.get('credit')
    #                                             list_mv_line.append((0, 0, interest_dict))
    #                                     else:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             interest_dict.update({'partner_id':self.hp_id.partner_id.id,\
    #                                                                   'account_id':tax.account_id,\
    #                                                                   'debit':0.0, 'credit':amount*(tax.factor_percent/100), 'amount_currency':-amount_currency,'currency_id':currency_id.id})
    #                                             fee_credit += interest_dict.get('credit')
    #                                             list_mv_line.append((0, 0, interest_dict))
    #                                     if fee_credit:
    #                                         installment_line.with_context({'fee':fee_credit}).onchange_fees()
    #                                     total_paid_amount = total_paid_amount + tx_tot
    #                                     installment_line.paid_fees_tx = tx_tot
    #                                 fees_line.write({'base_paid':base_amt + fees_line.base_paid + fees_line_tax, 'is_paid':True})
    #                                 if fees_dict:
    #                                     list_mv_line.append((0, 0, fees_dict))
    #                                 if fees_line_tax:
    #                                     self.amount = round(self.amount - (fees_line_base + fees_line_tax), 2)
    #                                 else:
    #                                     self.amount = round(self.amount - fees_line_base, 2)
    #
    #                                 installment_line.paid_fees = base_amt
    #                                 installment_line.outstanding_fees = installment_line.outstanding_fees - total_paid_amount
    #                                 if installment_line.date <= today:
    #                                     installment_line.due_fees = installment_line.outstanding_fees
    #                                 if not self.amount:
    #                                     if not self.late_fee:
    #                                         break_loop = True
    #                                     break
    #                             else:
    #                                 if self.amount >= fees_line_base:
    #                                     total_paid_amount = 0
    #                                     if fees_line.tax:
    #                                         tx_cal_amt = self.get_tax_total(type_line.tax_id, self.amount)
    #                                         fees_line_base = self.amount - tx_cal_amt
    #
    #                                     base_amt = fees_line_base
    #                                     base_paid = False
    #                                     tax_paid = False
    #                                     if fees_line_base:
    #                                         if currency_id.id != company_curren.id:
    #                                             amount_currency = fees_line_base
    #                                             amount = company_curren.with_context(date=self.payment_date).compute(fees_line_base, currency_id)
    #                                         else:
    #                                             amount_currency = False
    #                                         if not amount_currency:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':fees_line_base})
    #                                         else:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,\
    #                                                               'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                               'currency_id':currency_id.id})
    #                                         installment_line.with_context({'fee':fees_dict.get('credit')}).onchange_fees()
    #                                         list_mv_line.append((0, 0, fees_dict))
    #                                         base_paid = True
    #                                         installment_line.outstanding_fees = installment_line.outstanding_fees - fees_line_base
    #                                         installment_line.paid_fees = fees_line_base
    #                                         if installment_line.date <= today:
    #                                             installment_line.due_fees = installment_line.outstanding_fees
    #                                         else:
    #                                             installment_line.due_fees = 0.0
    #                                         fees_line.write({'base_paid':fees_line_base  + fees_line.base_paid})
    #                                         self.amount = round(self.amount,2)
    #                                         rem = self.amount - fees_line_base
    #                                         self.amount = rem
    #                                     if self.amount >=fees_line_tax:
    #                                         ## new changes done hereesssssss for payment calculation ......
    #                                         tx_amt = 0.0
    #                                         if type_line.tax_id:
    #                                             tx_cal_amt = self.get_tax_total(type_line.tax_id, fees_line_tax)
    #                                             tx_amt = self.amount - tx_cal_amt
    #                                             if tx_amt:
    #                                                 fees_dict_tx = {}
    #                                                 fees_line_tax = fees_line_tax - tx_amt
    #                                                 if currency_id.id != company_curren.id:
    #                                                     amount_currency = tx_amt
    #                                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                                 else:
    #                                                     amount_currency = False
    #                                                 if type_line.tax_id:
    #                                                     gl_acc = type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax')[0].account_id.id
    #                                                 else:
    #                                                     gl_acc = type_line.gl_code.id
    #                                                 if not amount_currency:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,'debit':0.0, 'credit':tx_amt})
    #                                                 else:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,\
    #                                                                       'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                       'currency_id':currency_id.id})
    #                                                 installment_line.with_context({'fee':fees_dict_tx.get('credit')}).onchange_fees()
    #                                                 list_mv_line.append((0, 0, fees_dict_tx))
    #                                                 installment_line.outstanding_fees = installment_line.outstanding_fees - tx_amt
    #                                                 fees_line.write({'tax_paid':tx_amt  + fees_line.tax_paid})
    #                                                 installment_line.paid_fees_tx = tx_amt
    #                                                 if installment_line.date <= today:
    #                                                     installment_line.due_fees = installment_line.outstanding_fees
    #                                                 else:
    #                                                     installment_line.due_fees = 0.0
    #                                                 tax_paid = True
    #                                                 self.amount = round(self.amount,2)
    #                                                 rem = self.amount - tx_amt
    #                                                 self.amount = rem
    #                                     else:
    #                                         tx_amt = 0.0
    #                                         if type_line.tax_id:
    #                                             tx_amt = self.amount
    #                                             if tx_amt:
    #                                                 fees_dict_tx = {}
    #                                                 fees_line_tax = fees_line_tax - tx_amt
    #                                                 if currency_id.id != company_curren.id:
    #                                                     amount_currency = tx_amt
    #                                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                                 else:
    #                                                     amount_currency = False
    #                                                 if type_line.tax_id:
    #                                                     gl_acc = type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax')[0].account_id.id
    #                                                 else:
    #                                                     gl_acc = type_line.gl_code.id
    #                                                 if not amount_currency:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,'debit':0.0, 'credit':tx_amt})
    #                                                 else:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,\
    #                                                                       'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                       'currency_id':currency_id.id})
    #                                                 installment_line.with_context({'fee':fees_dict_tx.get('credit')}).onchange_fees()
    #                                                 list_mv_line.append((0, 0, fees_dict_tx))
    #                                                 fees_line.write({'tax_paid':tx_amt  + fees_line.tax_paid})
    #                                                 installment_line.outstanding_fees = installment_line.outstanding_fees - tx_amt
    #                                                 installment_line.paid_fees_tx = tx_amt
    #                                                 if installment_line.date <= today:
    #                                                     installment_line.due_fees = installment_line.outstanding_fees
    #                                                 else:
    #                                                     installment_line.due_fees = 0.0
    #                                                 if not fees_line_tax:
    #                                                     tax_paid = True
    #                                                 self.amount = 0.0
    #
    #                                     if not fees_line_base:
    #                                         base_paid = True
    #                                     if base_paid and tax_paid: fees_line.is_paid = True
    #                                     if not self.amount:
    #                                         if not self.late_fee:
    #                                             break_loop = True
    #                                         break
    #                                 else:
    #                                     rem_fr_tx_amt = 0.0
    #                                     tx_cal_amt = 0.0
    #                                     if self.amount > 0.0:
    #                                         if type_line.tax_id:
    #                                             tx_amt = self.get_tax_value(type_line.tax_id, self.amount)
    #                                             tx_cal_amt = self.amount - tx_amt
    #                                             self.amount = self.amount - tx_cal_amt
    #                                         else:
    #                                             self.amount = round(self.amount, 2)
    #                                         if currency_id.id != company_curren.id:
    #                                             amount_currency = self.amount
    #                                             amount = company_curren.with_context(date=self.payment_date).compute(self.amount, currency_id)
    #                                         else:
    #                                             amount_currency = False
    #                                         gl_acc = type_line.gl_code.id
    #                                         if not amount_currency:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,'debit':0.0, 'credit':self.amount})
    #                                         else:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,\
    #                                                               'account_id':gl_acc,'debit':0.0,\
    #                                                                'credit':amount,'amount_currency':-amount_currency,\
    #                                                                'currency_id':currency_id.id})
    #                                         installment_line.with_context({'fee':fees_dict.get('credit')}).onchange_fees()
    #
    #                                         installment_line.outstanding_fees = installment_line.outstanding_fees - self.amount
    #                                         installment_line.paid_fees = self.amount
    #                                         if installment_line.date <= today:
    #                                             installment_line.due_fees = installment_line.outstanding_fees
    #                                         else:
    #                                             installment_line.due_fees = 0.0
    #                                         list_mv_line.append((0, 0, fees_dict))
    #                                         fees_line.write({'base_paid':self.amount + fees_line.base_paid})
    #
    #                                         if tx_cal_amt:
    #                                             rem_fr_tx_amt = tx_cal_amt
    #                                         if not rem_fr_tx_amt:
    #                                             self.amount = 0.0
    #                                             break
    #
    #                                     ##recent changes ...........................
    #                                     if rem_fr_tx_amt:
    #                                         tx_amt = rem_fr_tx_amt
    #                                         if tx_amt:
    #                                             fees_dict_tx = {}
    #                                             if currency_id.id != company_curren.id:
    #                                                 amount_currency = tx_amt
    #                                                 amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                             else:
    #                                                 amount_currency = False
    #                                             if type_line.tax_id:
    #                                                 gl_acc = type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax')[0].account_id.id
    #                                             else:
    #                                                 gl_acc = type_line.gl_code.id
    #                                             if not amount_currency:
    #                                                 fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,'debit':0.0, 'credit':tx_amt})
    #                                             else:
    #                                                 fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,\
    #                                                                   'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                   'currency_id':currency_id.id})
    #                                             installment_line.with_context({'fee':fees_dict_tx.get('credit')}).onchange_fees()
    #                                             list_mv_line.append((0, 0, fees_dict_tx))
    #                                             installment_line.outstanding_fees = installment_line.outstanding_fees - tx_amt
    #                                             fees_line.write({'base_paid':tx_amt  + fees_line.tax_paid + fees_line.base_paid})
    #                                             installment_line.paid_fees_tx = tx_amt
    #                                             if installment_line.date <= today:
    #                                                 installment_line.due_fees = installment_line.outstanding_fees
    #                                             else:
    #                                                 installment_line.due_fees = 0.0
    #                                             tax_paid = True
    #                                             self.amount = 0.0
    #                                             break
    #
    #                     if not self.amount:
    #                         if not self.late_fee:
    #                             break_loop = True
    #                         break
    #
    #
    #         if installment_line.late_fee and installment_line.late_fee > 0.0:
    #             if not self.late_fee:
    #                 continue
    #             for type_line in search_ids:
    #                 if type_line.type == 'late_fee':
    #                     if not type_line.gl_code:
    #                         raise UserError(_('Please Configure GLCode For fees Amount'))
    #                     for fees_line in installment_line.fee_lines:
    #                         fees_dict = {}
    #                         interest_dict = {}
    #                         if fees_line.product_id.id == type_line.product_id.id and fees_line.is_paid == False:
    #                             fees_line_base = round(fees_line.base - fees_line.base_paid, 2)
    #                             fees_line_tax = round(fees_line.tax - fees_line.tax_paid,2)
    #                             if fees_line_base > 0.0 and self.late_fee >= fees_line_base + fees_line_tax:
    #                                 total_paid_amount = 0
    #                                 if type_line.tax_id:
    #                                     rm_tx = self.get_tax_value(type_line.tax_id, fees_line_base)
    #                                     fees_line_tax = fees_line_base - rm_tx
    #                                     fees_line_base = fees_line_base - fees_line_tax
    #                                 if fees_line_base:
    #                                     base_amt = fees_line_base
    #                                     if currency_id.id != company_curren.id:
    #                                         amount_currency = base_amt
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(base_amt, currency_id)
    #                                     else:
    #                                         amount_currency = False
    #                                     if not amount_currency:
    #                                         fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':base_amt})
    #                                     else:
    #                                         fees_dict.update({'partner_id':self.hp_id.partner_id.id,\
    #                                                           'account_id':type_line.gl_code.id,\
    #                                                           'debit':0.0, 'credit':amount, 'amount_currency':-amount_currency,\
    #                                                            'currency_id':currency_id.id})
    #                                     total_paid_amount = total_paid_amount + base_amt
    #                                 if type_line.tax_id:
    #                                     tx_tot = fees_line_tax
    #                                     if currency_id.id != company_curren.id:
    #                                         amount_currency = tx_tot
    #                                         amount = company_curren.with_context(date=self.payment_date).compute(tx_tot, currency_id)
    #                                     else:
    #                                         amount_currency = False
    #                                     if not amount_currency:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             interest_dict = self.get_interest_vals(tx_tot*(tax.factor_percent/100), tax.account_id)
    #                                             list_mv_line.append((0, 0, interest_dict))
    #                                     else:
    #                                         for tax in type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
    #                                             interest_dict.update({'partner_id': self.hp_id.partner_id.id,\
    #                                                                 'account_id': tax.account_id.id,\
    #                                                                 'debit':0.0, 'credit':amount*(tax.factor_percent/100),'amount_currency':-amount_currency,\
    #                                                                'currency_id':currency_id.id})
    #                                             list_mv_line.append((0, 0, interest_dict))
    #                                     total_paid_amount = total_paid_amount + tx_tot
    #                                     installment_line.paid_late_fee_tx = tx_tot
    #                                 fees_line.write({'base_paid':base_amt + fees_line.base_paid + fees_line_tax, 'is_paid':True})
    #                                 if fees_dict:
    #                                         list_mv_line.append((0, 0, fees_dict))
    #                                 if fees_line_tax:
    #                                     self.late_fee = self.late_fee - (fees_line_base + fees_line_tax)
    #                                 else:
    #                                     self.late_fee = self.late_fee - fees_line_base
    #
    #                                 installment_line.late_fee = installment_line.late_fee - total_paid_amount
    #                                 installment_line.paid_late_fee = base_amt
    #                                 if self.late_fee:
    #                                     break_loop = False
    #                                 else:
    #                                     if not self.amount:
    #                                         break_loop = True
    #                                         break
    #
    #                             else:
    #                                 if self.late_fee >= fees_line_base:
    #                                     total_paid_amount = 0
    #                                     base_amt = fees_line_base
    #                                     base_paid = False
    #                                     tax_paid = False
    #                                     if fees_line_base:
    #                                         if currency_id.id != company_curren.id:
    #                                             amount_currency = fees_line_base
    #                                             amount = company_curren.with_context(date=self.payment_date).compute(fees_line_base, currency_id)
    #                                         else:
    #                                             amount_currency = False
    #                                         if not amount_currency:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':fees_line_base})
    #                                         else:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,\
    #                                                               'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                               'currency_id':currency_id.id})
    #                                         list_mv_line.append((0, 0, fees_dict))
    #                                         base_paid = True
    #                                         installment_line.late_fee = installment_line.late_fee - fees_line_base
    #                                         installment_line.paid_late_fee = fees_line_base
    #                                         fees_line.write({'base_paid':fees_line_base  + fees_line.base_paid})
    #                                         self.late_fee = round(self.late_fee,2)
    #                                         rem = self.late_fee - fees_line_base
    #                                         self.late_fee = rem
    #                                     if self.late_fee >=fees_line_tax:
    #                                         ## new changes done hereesssssss for payment calculation ......
    #                                         tx_amt = 0.0
    #                                         if type_line.tax_id:
    #                                             tx_amt = fees_line_tax
    #                                             if tx_amt:
    #                                                 fees_dict_tx = {}
    #                                                 fees_line_tax = fees_line_tax - tx_amt
    #                                                 if currency_id.id != company_curren.id:
    #                                                     amount_currency = tx_amt
    #                                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                                 else:
    #                                                     amount_currency = False
    #                                                 if not amount_currency:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':tx_amt})
    #                                                 else:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,\
    #                                                                       'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                       'currency_id':currency_id.id})
    #                                                 list_mv_line.append((0, 0, fees_dict_tx))
    #                                                 installment_line.late_fee = installment_line.late_fee - tx_amt
    #                                                 fees_line.write({'tax_paid':tx_amt  + fees_line.tax_paid})
    #                                                 installment_line.paid_late_fee = tx_amt
    #                                                 tax_paid = True
    #                                                 self.late_fee = round(self.late_fee,2)
    #                                                 rem = self.late_fee - tx_amt
    #                                                 self.late_fee = rem
    #                                     else:
    #                                         tx_amt = 0.0
    #                                         if type_line.tax_id:
    #                                             tx_amt = self.get_tax_value(type_line.tax_id, self.late_fee)
    #                                             tx_cal_amt = self.late_fee - tx_amt
    #                                             self.late_fee = self.late_fee - tx_cal_amt
    #                                             tx_amt = self.late_fee
    #                                             if tx_amt:
    #                                                 fees_dict_tx = {}
    #                                                 fees_line_tax = fees_line_tax - tx_amt
    #                                                 if currency_id.id != company_curren.id:
    #                                                     amount_currency = tx_amt
    #                                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                                 else:
    #                                                     amount_currency = False
    #                                                 if not amount_currency:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':tx_amt})
    #                                                 else:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,\
    #                                                                       'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                       'currency_id':currency_id.id})
    #                                                 installment_line.with_context({'fee':fees_dict_tx.get('credit')}).onchange_fees()
    #                                                 list_mv_line.append((0, 0, fees_dict_tx))
    #                                                 fees_line.write({'tax_paid':tx_amt  + fees_line.tax_paid})
    #                                                 installment_line.outstanding_fees = installment_line.outstanding_fees - tx_amt
    #                                                 installment_line.paid_fees_tx = tx_amt
    #                                                 if installment_line.date <= today:
    #                                                     installment_line.due_fees = installment_line.outstanding_fees
    #                                                 else:
    #                                                     installment_line.due_fees = 0.0
    #                                                 if not fees_line_tax:
    #                                                     tax_paid = True
    #                                                 self.late_fee = 0.0
    #                                     if not fees_line_base:
    #                                         base_paid = True
    #                                     if base_paid and tax_paid: fees_line.is_paid = True
    #                                     if not self.late_fee:
    #                                         if not self.amount:
    #                                             break_loop = True
    #                                             break
    #
    #                                 else:
    #                                     rem_fr_tx_amt = 0.0
    #                                     if self.late_fee > 0.0:
    #                                         total_paid_amount = 0
    #                                         self.late_fee = round(self.late_fee, 2)
    #                                         tx_amt = self.get_tax_value(type_line.tax_id, self.late_fee)
    #                                         tx_cal_amt = self.late_fee - tx_amt
    #                                         self.late_fee = self.late_fee - tx_cal_amt
    #                                         if tx_cal_amt:
    #                                             rem_fr_tx_amt = tx_cal_amt
    #                                         if currency_id.id != company_curren.id:
    #                                             amount_currency = self.late_fee
    #                                             amount = company_curren.with_context(date=self.payment_date).compute(self.late_fee, currency_id)
    #                                         else:
    #                                             amount_currency = False
    #                                         if not amount_currency:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,'account_id':type_line.gl_code.id,'debit':0.0, 'credit':self.late_fee})
    #                                         else:
    #                                             fees_dict.update({'partner_id':self.hp_id.partner_id.id,\
    #                                                               'account_id':type_line.gl_code.id,'debit':0.0,\
    #                                                             'credit':amount,'amount_currency':-amount_currency,'currency_id':currency_id.id})
    #                                         installment_line.late_fee = installment_line.late_fee - self.late_fee
    #                                         installment_line.paid_late_fee = self.late_fee
    #                                         list_mv_line.append((0, 0, fees_dict))
    #                                         fees_line.write({'base_paid':self.late_fee + fees_line.base_paid})
    #                                         self.late_fee = 0.0
    #                                         break_loop = True
    #
    #                                         if rem_fr_tx_amt:
    #                                             tx_amt = rem_fr_tx_amt
    #                                             if tx_amt:
    #                                                 fees_dict_tx = {}
    #                                                 if currency_id.id != company_curren.id:
    #                                                     amount_currency = tx_amt
    #                                                     amount = company_curren.with_context(date=self.payment_date).compute(tx_amt, currency_id)
    #                                                 else:
    #                                                     amount_currency = False
    #                                                 if type_line.tax_id:
    #                                                     gl_acc = type_line.tax_id.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax')[0].account_id.id
    #                                                 else:
    #                                                     gl_acc = type_line.gl_code.id
    #                                                 if not amount_currency:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,'debit':0.0, 'credit':tx_amt})
    #                                                 else:
    #                                                     fees_dict_tx.update({'partner_id':self.hp_id.partner_id.id,'account_id':gl_acc,\
    #                                                                       'debit':0.0, 'credit':amount,'amount_currency':-amount_currency,\
    #                                                                       'currency_id':currency_id.id})
    #                                                 installment_line.with_context({'fee':fees_dict_tx.get('credit')}).onchange_fees()
    #                                                 list_mv_line.append((0, 0, fees_dict_tx))
    #                                                 installment_line.late_fee = installment_line.late_fee - tx_amt
    #                                                 fees_line.write({'base_paid':tx_amt  + fees_line.tax_paid + fees_line.base_paid})
    #                                                 installment_line.paid_fees_tx = tx_amt
    #                                                 if installment_line.date <= today:
    #                                                     installment_line.due_fees = installment_line.late_fee
    #                                                 else:
    #                                                     installment_line.due_fees = 0.0
    #                                                 tax_paid = True
    #                                                 self.amount = 0.0
    #                                                 if not self.amount:
    #                                                     break
    #                                     else:
    #                                         if not self.late_fee:
    #                                             if not self.amount:
    #                                                 break_loop = True
    #                                                 break
    #
    #                 #==========================for late fees====================
    #
    #
    #         if not installment_line.outstanding_prin and not installment_line.outstanding_int and not installment_line.outstanding_fees and not installment_line.late_fee:
    #             installment_line.state = 'paid'
    #         else:
    #             installment_line.state = 'open'
    #     if self.amount:
    #         if not self.hp_id.hp_type.account_id:
    #             raise Warning(_("Please Define Excess Payment Account"))
    #         excess_lines = self.get_extra_payment(self.amount, self.hp_id, self.payment_date, self.hp_id.hp_type.account_id, currency_id, company_curren)
    #         if excess_lines:
    #             list_mv_line.append((0, 0, excess_lines))
    #     move_vals.update({'line_ids':list_mv_line})
    #     move_id = self.env['account.move'].create(move_vals)
    #     if move_id:
    #         move_id.post()
    #         for l in affected_line_list:
    #
    #             vals = {}
    #             fees_amt = 0.0
    #             late_fee_amt = 0.0
    #             fees_amt = l.paid_fees + l.paid_fees_tx
    #             late_fee_amt = l.paid_late_fee + l.paid_late_fee_tx
    #             vals.update({'pay_date':self.payment_date, 'prin_amt':l.paid_prin,\
    #                          'int_amt':l.paid_int,'fees_amt':fees_amt,\
    #                          'late_fee_amt':late_fee_amt,'base_late_fee_amt':l.paid_late_fee ,\
    #                          'base_late_fee_amt_tx':l.paid_late_fee_tx,\
    #                          'move_id':move_id.id,\
    #                          'base_fee_paid':l.paid_fees,'base_fee_tax_paid':l.paid_fees_tx,\
    #                         'line_id':l.id,'state':'draft'})
    #             if vals:
    #                 self.env['payment.details'].create(vals)
    #                 l.paid_prin = 0.0
    #                 l.paid_int = 0.0
    #                 l.paid_fees = 0.0
    #                 l.paid_fees_tx = 0.0
    #                 l.paid_late_fee = 0.0
    #                 l.paid_late_fee_tx = 0.0
    #             l.move_id = move_id.id
    #         return move_id
            
    def get_extra_payment(self, main_amt, hp_id, date_new, account_id, currency_id, company_curren):
        move_lines_extra_payemnt = {}
        amount_currency = False
        if currency_id.id != company_curren.id:
            amount_currency = main_amt
            amount = company_curren.with_context(date=date_new).compute(main_amt, currency_id)
            move_lines_extra_payemnt.update({'credit':amount,
                                             'amount_currency': -amount_currency,
                                             'currency_id': currency_id.id
                                             })
        if not amount_currency:
            move_lines_extra_payemnt.update({'credit':main_amt,})
        move_lines_extra_payemnt.update({'account_id':account_id.id,
                                         'name':"Excess Payment",
                                         'debit':0.0,
                                         'partner_id':hp_id.partner_id.id})
        return move_lines_extra_payemnt
        
        