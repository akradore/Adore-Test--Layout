from odoo import models, fields, api, _
import datetime
from odoo.exceptions import UserError

class set_hp_disbursement_amt(models.TransientModel):
    
    _name = "hp.disbursement.wizard"
    _description = "HP disbursement wizard"
    
    disbursement_amt = fields.Monetary("Amount To be disbursed", digits=(10,2), required=True)
    name = fields.Char(string="* ")
    date = fields.Date("Date", default = datetime.datetime.strftime(datetime.date.today(), '%Y-%m-7'))
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])

    @api.onchange('journal_id')
    def _onchange_disburse_journal(self):
        if self.journal_id:
            active_id = self._context.get('active_id')
            acc_hp = self.env['account.hp'].browse(active_id)
            self.currency_id = self.journal_id.currency_id or acc_hp.company_id.currency_id

    @api.onchange('disbursement_amt', 'currency_id')
    def _onchange_disburse_amount(self):
        journal_types = ['bank', 'cash']
        domain_on_types = [('type', 'in', list(journal_types))]
        journal_domain = []
        if not self.journal_id:
            if self.journal_id.type not in journal_types:
                self.journal_id = self.env['account.journal'].search(domain_on_types, limit=1)
        else:
            journal_domain = journal_domain.append(('id', '=', self.journal_id.id))
        return {'domain': {'journal_id': journal_domain}}
    
    def generate_lines_by_sanctioned_hp(self, acc_hp):
        move_id = None
        total_amt = 0.0
        if self.disbursement_amt:
            for line in acc_hp.disbursement_details:
                total_amt += float(line.disbursement_amt)
        
        if acc_hp.hp_amount-total_amt < self.disbursement_amt and not self._context.get('is_extended'):
            raise UserError("Warning : Disbursement amount can not be greater than %s"% str(acc_hp.hp_amount-total_amt))
        total_amt += self.disbursement_amt
        currency_id = self.currency_id
        if acc_hp.hp_type.calculation in ['flat','reducing','cnt_prin'] and self._context.get('is_extended'):
            move_id = acc_hp.with_context({'is_extended': True, 'date': self._context.get('date')})._simple_interest_get_by_disbursed(acc_hp.interest_rate, total_amt, disburse_date=self.date, currency_id = currency_id)

        elif acc_hp.hp_type.calculation in ['flat','reducing','cnt_prin'] and not acc_hp.installment_id:
            move_id = acc_hp._simple_interest_get_by_disbursed(acc_hp.interest_rate, total_amt, disburse_date=self.date, currency_id = currency_id)

        elif acc_hp.hp_type.calculation in ['flat','reducing','cnt_prin'] and acc_hp.installment_id:
            move_id = acc_hp._get_simple_int_by_existed_disbursed(acc_hp.interest_rate, self.disbursement_amt, self.date, currency_id = currency_id)

        if total_amt >= acc_hp.approve_amount:
            acc_hp.write({'state':'approved'})
        else:
            acc_hp.write({'state':'partial'})

        return True

    def approve_hp(self):
        active_id = self._context.get('active_id')
        acc_hp = self.env['account.hp'].browse(active_id)
        total_amt = 0
        currency_id = self.currency_id
        move_id = None
        if self.env['ir.config_parameter'].get_param('hire_purhcase.is_auto_create_inst_lines',False):
            if acc_hp.repayment_basis == 'sanctioned_amt':
                self.generate_lines_by_sanctioned_hp(acc_hp)
                return True
            if self.disbursement_amt:
                for line in acc_hp.disbursement_details:
                    total_amt += float(line.disbursement_amt)

            if acc_hp.hp_amount-total_amt < self.disbursement_amt and not self._context.get('is_extended'):
                raise UserError("Warning : Disbursement amount can not be greater than %s"% str(acc_hp.hp_amount-total_amt))
            if not self._context.get('is_extended'):
                total_amt += self.disbursement_amt
            if acc_hp.hp_type.calculation in ['flat','reducing','cnt_prin'] and self._context.get('is_extended'):
                move_id = acc_hp.with_context({'is_extended': True, 'date': self._context.get('date')})._get_simple_int_by_existed_disbursed(acc_hp.interest_rate, total_amt, self.date, currency_id = currency_id)

            elif acc_hp.hp_type.calculation in ['flat','reducing','cnt_prin'] and not acc_hp.installment_id:
                move_id = acc_hp._simple_interest_get_by_disbursed(acc_hp.interest_rate, total_amt, disburse_date=self.date, currency_id = currency_id)

            elif acc_hp.loan_type.calculation in ['flat','reducing','cnt_prin'] and acc_hp.installment_id:
                move_id = acc_hp._get_simple_int_by_existed_disbursed(acc_hp.interest_rate, self.disbursement_amt, disburse_date=self.date, currency_id = currency_id)

            if total_amt >= acc_hp.approve_amount:
                acc_hp.write({'state':'approved'})
            else:
                acc_hp.write({'state':'partial'})
        acc_hp.write({'state':'approved'})
        return True
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
