from odoo import api, fields, models
from datetime import date,datetime

class AccountHPRepayment(models.Model):
    _name = "account.hp.repayment"
    _description = 'Account HP repayment'

    hp_id = fields.Many2one('account.hp')
    release_number = fields.Many2one('account.move','Release Number')
    name = fields.Many2one('res.partner','Partner Name',required=True)
    pay_date = fields.Date("Re-payment Date",required=True)
    amt = fields.Float("Amount",required=True)
    is_button_visible = fields.Boolean("Is Button Visible")

    def hp_payment_cancel(self):
        today = datetime.today().date()
        if self.release_number:
            if self.release_number and self.release_number.state != 'posted':
                raise Warning('You can not cancel drafted Entries')
            reverse_changeslist = []
            payment_details_ids = self.env['payment.details'].search([('move_id', '=', self.release_number.id)])
            for pd_line in payment_details_ids:
                is_prin = False
                is_int = False
                is_fee = False
                is_late_fee = False
                flag = False
                reverse_changeslist.append(pd_line.line_id)
                if pd_line.line_id:
                    pd_line.line_id.outstanding_prin += pd_line.prin_amt
                    if pd_line.line_id.date <= today:
                        pd_line.line_id.due_principal += pd_line.prin_amt
                    else:
                        pd_line.line_id.due_principal = 0.00
                    if round(pd_line.line_id.outstanding_prin, 2) == pd_line.line_id.capital:
                        is_prin = True
                if pd_line.line_id:
                    pd_line.line_id.outstanding_int += pd_line.int_amt
                    if pd_line.line_id.date <= today:
                        pd_line.line_id.due_interest += pd_line.int_amt
                    else:
                        pd_line.line_id.due_interest = 0.00
                    if round(pd_line.line_id.outstanding_int, 2) == pd_line.line_id.interest:
                        is_int = True
                if pd_line.line_id:
                    pd_line.line_id.outstanding_fees += pd_line.fees_amt
                    if pd_line.line_id.date <= today:
                        pd_line.line_id.due_fees += pd_line.fees_amt
                    else:
                        pd_line.line_id.due_fees = 0.00
                    if round(pd_line.line_id.outstanding_fees, 2) == pd_line.line_id.fees:
                        is_fee = True
                    for fee_line in pd_line.line_id.fee_lines:
                        if fee_line.name == 'fees':
                            fee_line.base_paid -= pd_line.base_fee_paid
                            fee_line.tax_paid -= pd_line.base_fee_tax_paid
                            if pd_line.base_fee_paid or pd_line.base_fee_tax_paid:
                                fee_line.is_paid = False
                if pd_line.line_id:
                    pd_line.line_id.late_fee += pd_line.late_fee_amt
                    flag = True
                    if pd_line.line_id.late_fee == pd_line.line_id.late_fee:
                        is_late_fee = True
                    for fee_line in pd_line.line_id.fee_lines:
                        if fee_line.name == 'late_fee':
                            fee_line.base_paid -= pd_line.base_late_fee_amt
                            fee_line.tax_paid -= pd_line.base_late_fee_amt_tx
                            if fee_line.base_paid == 0.0 and fee_line.tax_paid == 0.0:
                                fee_line.is_paid = False

                if is_prin and is_int and is_fee and flag:
                    if is_late_fee:
                        pd_line.line_id.state = 'draft'
                elif is_prin and is_int and is_fee:
                    pd_line.line_id.state = 'draft'
                else:
                    pd_line.line_id.state = 'open'

            cancel_entry = self.release_number.button_cancel()
            if cancel_entry:
                self.is_button_visible = False
                payment_details_ids = self.env['payment.details'].search([('move_id', '=', self.release_number.id)])
                for pyline in payment_details_ids:
                    pyline.state = 'cancel'
        return True

    def delete_payment_line(self):
        for o in self:
            if o.release_number:
                payment_details_ids = self.env['payment.details'].search([('move_id', '=', self.release_number.id)])
                for pyline in payment_details_ids:
                    pyline.unlink()
            if o.release_number:
                o.release_number.unlink()
            o.unlink()
        return True
