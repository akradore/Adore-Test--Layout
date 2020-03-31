from odoo import api, fields, models
import base64
from datetime import datetime
import xlwt
import io
from odoo.exceptions import UserError


class HPGenerateReport(models.TransientModel):
    _name = 'wiz.download.report'
    _description = "Wiz download Report "

    exported_file = fields.Binary("Exported File")
    file_name = fields.Char('File Name')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env['res.company']._company_default_get('wiz.download.report'))
    report_type = fields.Selection(string='Report Type',
                                   selection=[('portfolio', 'PortFolio Management'), ('sector', 'Sector Report')
                                       , ('product', 'Product Report'), ('closed', 'Closed Loans Report')])
    date = fields.Date(string="To Date", default=fields.Date.today())
    type = fields.Selection(string="Reports",
                            selection=[('detailed_report', 'Detail Report'), ('summary_report', 'Summary Report')],
                            default='detailed_report')

    def generate_file(self):
        exported_data = []
        hp_obj = self.env['account.hp']
        file = ''
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Loan Report')
        bold = xlwt.easyxf("font: bold on;")
        decimal_style = xlwt.XFStyle()
        decimal_style.num_format_str = '#,##0.00'
        font0 = xlwt.Font()
        font0.bold = True
        decimal_style1 = xlwt.XFStyle()
        decimal_style1.num_format_str = '#,##0.00'
        decimal_style1.font = font0
        r = 0
        c = 0
        count = 1
        date = datetime.now()
        curr = self.company_id.currency_id.name
        if self.report_type == 'portfolio':
            file = 'portfolio_management.xls'
            if self.type == 'detailed_report':
                head = ['User', "Company name/client's name", 'Loan Number', 'Purpose', 'Department',
                        'Is Refugee',
                        'Cycle',
                        'Industry/Sector of activity',
                        'Physical Address Province',  'Country', 'Telephone', 'Mobile', 'Approval Date',
                        'Applied Amount', 'Approved Amount', 'Disbused amount', 'Difference', 'Currency Type',
                        'Repayment Term', 'Agreement Type', 'Application Term Duration', 'Terms Duration',
                        'Actual Payment Amount', 'Actual Payment Amount (%s)' % curr,
                        'Principal Paid', 'Principal Paid (%s)' % curr,
                        'Interest Paid', 'Interest Paid(%s)' % curr,
                        'Fees Paid', 'Fees Paid(%s)' % curr,
                        'Current Balance', 'Current Balance(%s)' % curr,
                        'Principal Balance', 'Principal Balance(%s)' % curr,
                        'Interest Balance', 'Interest Balance(%s)' % curr,
                        'Fees Balance', 'Fees Balance(%s)' % curr,
                        'Amount Past Due', 'Amount Past Due(%s)' % curr,
                        'Principal Past Due', 'Principal Past Due(%s)' % curr,
                        'Interest Past Due', 'Interest Past Due(%s)' % curr,
                        'Fees Past Due', 'Fees Past Due(%s)' % curr,
                        'Scheduled Payment Amount', 'Scheduled Payment Amount(%s)' % curr,
                        'Scheduled Principal Amount', 'Scheduled Principal Amount(%s)' % curr,
                        'Scheduled Interest Amount', 'Scheduled Interest Amount(%s)' % curr,
                        'Scheduled Fees Amount', 'Scheduled Fees Amount(%s)' % curr,
                        'Last Payment Amount', 'Last Payment Amount(%s)' % curr,
                        'Last Principal Amount', 'Last Principal Amount(%s)' % curr,
                        'Last Interest Amount', 'Last Interest Amount(%s)' % curr,
                        'Last Fees Amount', 'Last Fees Amount(%s)' % curr,
                        'Account Status',
                        'Days in Arrears', 'Installments in Arrears', 'Classification', 'Last Payment Date',
                        'Final Payment Date', 'Date Closed', 'Application State']
                for item in head:
                    worksheet.write(r, c, item, bold)
                    c += 1
                cycle_dict = {}
                for hp in hp_obj.search([('state', 'in', ['partial', 'approved', 'done']),
                                             ('approve_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d"))]):
                    amt = terms = cycle = 0
                    for dis in hp.disbursement_details:
                        amt += dis.disbursement_amt
                    final_date = ''
                    last_date = ''
                    closed = ''
                    arrear_day = arrear_installment = 0
                    actual_payment = paid_pri = local_paid_pri = paid_int = local_paid_int =  paid_fees = local_paid_fees =0.00
                    sch_pri = sch_int = sch_fees = bal_pri = bal_int = bal_fees = past_pri = past_int = past_fees = 0.00
                    status = ''
                    name = ''
                    currency_name = ''
                    cur_id = None
                    actual_paid = 0.0
                    paid_flag = True
                    if hp.partner_id.parent_id:
                        if hp.partner_id.parent_id.name == hp.partner_id.name:
                            name = hp.partner_id.name
                        else:
                            name = hp.partner_id.parent_id.name + ', ' + hp.partner_id.name
                    else:
                        name = hp.partner_id.name

                    tot_bal_pri = tot_bal_int = tot_bal_fees = 0
                    tot_prin = tot_int = tot_fee = 0
                    paid_capital = paid_interest = paid_fee = 0
                    last_payment_prin = last_payment_int = last_payment_fee = 0
                    last_payment_date = False

                    ##search for getting last payment details of every individual hp ..............
                    repayment_lines = self.env['account.hp.repayment'].search(
                        [('pay_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d")),
                         ('is_button_visible', '!=', False), ('hp_id', '=', hp.id)], order='id')
                    if repayment_lines:
                        for payment_line in repayment_lines[-1]:
                            last_payment_date = payment_line.pay_date
                    for inst in hp.installment_id:
                        tot_bal_pri += inst.capital
                        tot_bal_int += inst.interest
                        tot_bal_fees += inst.fees

                        if inst.state != 'paid':
                            paid_flag = False
                        if inst.date:
                            '''Get Last Payment details'''
                            if last_payment_date:
                                last_payment_details = self.env['payment.details'].search(
                                    [('pay_date', '=', datetime.strptime(str(last_payment_date), "%Y-%m-%d")),
                                     ('line_id', '=', inst.id), ('state', '!=', 'cancel')])
                                for pline in last_payment_details:
                                    last_payment_prin += pline.prin_amt
                                    last_payment_int += pline.int_amt
                                    last_payment_fee += pline.fees_amt

                            '''Get paid balance for current balance'''
                            paid_line = self.env['payment.details'].search(
                                [('pay_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d")),
                                 ('line_id', '=', inst.id), ('state', '!=', 'cancel')])
                            for o in paid_line:
                                paid_capital += o.prin_amt
                                paid_interest += o.int_amt
                                paid_fee += o.fees_amt

                            if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                                '''Get Actual Payment Amount'''
                                paid_pri += inst.capital - inst.outstanding_prin
                                paid_int += inst.interest - inst.outstanding_int
                                paid_fees += inst.fees - inst.outstanding_fees
                                local_paid_pri += inst.local_principle
                                local_paid_int += inst.local_interest
                                local_paid_fees += inst.local_fees

                                '''Get Balance Amount'''
                                pay_line = self.env['payment.details'].search(
                                    [('line_id', '=', inst.id), ('state', '!=', 'cancel')])
                                for pline in pay_line:
                                    if pline.pay_date:
                                        if datetime.strptime(str(pline.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                                              "%Y-%m-%d"):
                                            bal_pri += pline.prin_amt
                                            bal_int += pline.int_amt
                                            bal_fees += pline.fees_amt

                            if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                             "%Y-%m-%d"):  # == 'draft'
                                tot_prin += inst.capital
                                tot_int += inst.interest
                                tot_fee += inst.fees

                            if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                             "%Y-%m-%d") and inst.state != 'paid':  # == 'draft'
                                '''Get Amount Past Due'''
                                past_pri += inst.due_principal
                                past_int += inst.due_interest
                                past_fees += inst.due_fees
                                if not arrear_day:
                                    arrear_day = inst.date
                                arrear_installment += 1

                    ## for total outstanding amount ..........................
                    past_pri = tot_prin - bal_pri
                    past_int = tot_int - bal_int
                    past_fees = tot_fee - bal_fees

                    bal_pri = tot_bal_pri - paid_capital
                    if paid_interest:
                        bal_int = tot_bal_int - paid_interest
                    if paid_fee:
                        bal_fees = tot_bal_fees - paid_fee

                    for pays in hp.repayment_details:
                        if pays.pay_date:
                            if datetime.strptime(str(pays.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                                 "%Y-%m-%d") and pays.is_button_visible != False:
                                actual_payment += pays.amt
                        last_date = pays.pay_date
                    if last_date:
                        last_date = datetime.strptime(str(last_date), "%Y-%m-%d").strftime('%m/%d/%Y')

                    for cheque in hp.payment_schedule_ids:
                        terms += 1

                    if arrear_day:
                        arrear_day = datetime.strptime(str(arrear_day), "%Y-%m-%d")
                        arrear_day = date - arrear_day
                        arrear_day = arrear_day.days

                    if paid_flag:
                        status = 'Paid'
                    else:
                        status = 'Unpaid'

                    for pay in hp.payment_schedule_ids:
                        '''Get Scheduled Payment'''
                        if pay.date and datetime.strptime(str(pay.date), "%Y-%m-%d") > datetime.strptime(str(self.date),
                                                                                                    "%Y-%m-%d"):
                            sch_pri = pay.capital
                            sch_int = pay.interest
                            sch_fees = pay.fees
                            break

                    for pay in hp.payment_schedule_ids:
                        final_date = pay.date

                    if final_date:
                        final_date = datetime.strptime(str(final_date), "%Y-%m-%d").strftime('%m/%d/%Y')

                    #                     cycle_dict = {}
                    for user_hp in hp_obj.search([('partner_id', '=', hp.partner_id.id)], order="id asc"):
                        cycle += 1
                        cycle_dict.update({user_hp.id: cycle})

                    mail_id = self.env['mail.message'].search([('model', '=', 'account.hp'), ('res_id', '=', hp.id)])
                    mail_message_id = [mail.id for mail in mail_id]
                    if mail_message_id:
                        track_id = self.env['mail.tracking.value'].search(
                            [('mail_message_id', 'in', mail_message_id), ('new_value_char', '=', 'Closed')], limit=1)
                        if track_id and track_id.create_date:
                            closed = datetime.strptime(str(track_id.create_date), "%Y-%m-%d %H:%M:%S").strftime('%m/%d/%Y')

                    local_bal_total = bal_pri + bal_int + bal_fees
                    local_bal_pri = bal_pri
                    local_bal_int = bal_int
                    local_bal_fee = bal_fees
                    local_past_total = past_pri + past_int + past_fees
                    local_past_pri = past_pri
                    local_past_int = past_int
                    local_past_fee = past_fees
                    local_sch_total = sch_pri + sch_int + sch_fees
                    local_sch_pri = sch_pri
                    local_sch_int = sch_int
                    local_sch_fee = sch_fees
                    local_last_payment_total = last_payment_prin + last_payment_int + last_payment_fee
                    local_last_payment_prin = last_payment_prin
                    local_last_payment_int = last_payment_int
                    local_last_payment_fee = last_payment_fee
                    local_actual_payment = actual_payment
                    local_paid_prin = paid_capital
                    local_paid_int = paid_interest
                    local_paid_fee = paid_fee

                    exported_data.append([hp.user_id.name,
                                          name,
                                          hp.hp_id,
                                          hp.name or '',
                                          dict(hp._fields['department'].selection).get(hp.department) or '',
                                          dict(hp._fields['is_refugee'].selection).get(hp.is_refugee) or '',
                                          str(cycle_dict.get(hp.id)),
                                          hp.partner_id.country_id and hp.partner_id.country_id.name or '',
                                          hp.partner_id.phone or '',
                                          hp.partner_id.mobile or '',
                                          hp.approve_date and datetime.strptime(str(hp.approve_date), "%Y-%m-%d").strftime('%m/%d/%Y') or '',
                                          round(hp.req_amt, 2),
                                          round(hp.hp_amount, 2),
                                          round(amt, 2), round(hp.hp_amount - amt, 2),
                                          currency_name,
                                          dict(hp._fields['payment_freq'].selection).get(hp.payment_freq),
                                          hp.hp_type.name,
                                          hp.total_installment,
                                          str(terms),
                                          round(local_actual_payment, 2),
                                          round(paid_capital + paid_interest + paid_fee, 2),
                                          round(local_paid_prin, 2), round(paid_capital, 2),
                                          round(local_paid_int, 2), round(paid_interest, 2),
                                          round(local_paid_fee, 2), round(paid_fee, 2),

                                          round(bal_pri + bal_int + bal_fees, 2),
                                          round(local_bal_total, 2),
                                          round(bal_pri, 2), round(local_bal_pri, 2),
                                          round(bal_int, 2), round(local_bal_int, 2),
                                          round(bal_fees, 2), round(local_bal_fee, 2),

                                          round(past_pri + past_int + past_fees, 2),
                                          round(local_past_total, 2),
                                          round(past_pri, 2), round(local_past_pri, 2),
                                          round(past_int, 2), round(local_past_int, 2),
                                          round(past_fees, 2), round(local_past_fee, 2),

                                          round(sch_pri + sch_int + sch_fees, 2),
                                          round(local_sch_total, 2),
                                          round(sch_pri, 2), round(local_sch_pri, 2),
                                          round(sch_int, 2), round(local_sch_int, 2),
                                          round(sch_fees, 2), round(local_sch_fee, 2),

                                          round(last_payment_prin + last_payment_int + last_payment_fee),
                                          round(local_last_payment_total, 2),
                                          round(last_payment_prin, 2), round(local_last_payment_prin, 2),
                                          round(last_payment_int, 2), round(local_last_payment_int, 2),
                                          round(last_payment_fee, 2), round(local_last_payment_fee, 2),

                                          status, str(arrear_day), str(arrear_installment),
                                          hp.classification or '',
                                          last_date,
                                          final_date,
                                          closed,
                                          dict(hp._fields['state'].selection).get(hp.state)
                                          ])
            else:
                head = ["Company name/client's name", 'Purpose', 'Department', 'Is Refugee',
                        'Gender', 'Physical Address City', 'Country', 'Telephone', 'Approval Date',
                        'Disbused amount', 'Application State']
                for item in head:
                    worksheet.write(r, c, item, bold)
                    c += 1

                for hp in hp_obj.search([('state', 'in', ['partial', 'approved', 'done']),
                                             ('approve_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d"))]):
                    amt = 0.00
                    for dis in hp.disbursement_details:
                        amt += dis.disbursement_amt
                    if hp.partner_id.parent_id:
                        if hp.partner_id.parent_id.name == hp.partner_id.name:
                            name = hp.partner_id.name
                        else:
                            name = hp.partner_id.parent_id.name + ', ' + hp.partner_id.name
                    else:
                        name = hp.partner_id.name

                    exported_data.append([
                        name,
                        hp.name or '',
                        dict(hp._fields['department'].selection).get(hp.department) or '',
                        dict(hp._fields['is_refugee'].selection).get(hp.is_refugee) or '',
                        hp.partner_id.city or '',
                        hp.partner_id.country_id and hp.partner_id.country_id.name or '',
                        hp.partner_id.phone or '',
                        hp.approve_date and datetime.strptime(str(hp.approve_date), "%Y-%m-%d").strftime(
                            '%m/%d/%Y') or '',
                        round(amt, 2),
                        dict(hp._fields['state'].selection).get(hp.state)
                    ])


        elif self.report_type == 'sector':
            file = 'sector_report.xls'
            head = ['S/N', "Company name/client's name", 'Account Number',
                    'Purpose', 'Department', 'Is Refugee',
                    'Cycle', 'Sector/Industry', 'Gender',
                    'Approval date', 'Amount Disbursed', 'Currency',
                    'Amount paid', 'Amount paid(%s)' % curr,
                    'Current Balance', 'Current Balance(%s)' % curr,
                    'Amount past due', 'Amount past due(%s)' % curr,
                    'Application State']

            for item in head:
                worksheet.write(r, c, item, bold)
                c += 1

            sec_cycle_dict = {}
            for hp in hp_obj.search([('approve_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d"))]):
                amt = amt_paid = 0.00
                cycle = 0

                bal_pri = bal_int = bal_fees = 0.00
                past_pri = past_int = past_fees = 0.00
                local_paid_pri = local_paid_int = local_paid_fee = 0.00
                tot_bal_pri = tot_bal_int = tot_bal_fees = 0
                tot_prin = tot_int = tot_fee = 0
                paid_capital = paid_interest = paid_fee = 0
                paid_pri = paid_int = paid_fees = 0.00
                currency_name = ''
                cur_id = None
                if hp.partner_id.parent_id:
                    if hp.partner_id.parent_id.name == hp.partner_id.name:
                        name = hp.partner_id.name
                    else:
                        name = hp.partner_id.parent_id.name + ', ' + hp.partner_id.name
                else:
                    name = hp.partner_id.name

                for inst in hp.installment_id:
                    tot_bal_pri += inst.capital
                    tot_bal_int += inst.interest
                    tot_bal_fees += inst.fees
                    if inst.date:
                        '''Get paid balance for current balance'''
                        paid_line = self.env['payment.details'].search(
                            [('pay_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d")), ('line_id', '=', inst.id),
                             ('state', '!=', 'cancel')])
                        for o in paid_line:
                            paid_capital += o.prin_amt
                            paid_interest += o.int_amt
                            paid_fee += o.fees_amt

                        if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                            '''Get Actual Payment Amount'''
                            paid_pri += inst.capital - inst.outstanding_prin
                            paid_int += inst.interest - inst.outstanding_int
                            paid_fees += inst.fees - inst.outstanding_fees
                            local_paid_pri += inst.local_principle
                            local_paid_int += inst.local_interest
                            local_paid_fee += inst.local_fees

                            '''Get Balance Amount'''
                            pay_line = self.env['payment.details'].search(
                                [('line_id', '=', inst.id), ('state', '!=', 'cancel')])
                            for pline in pay_line:
                                if pline.pay_date:
                                    if datetime.strptime(str(pline.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                                          "%Y-%m-%d"):
                                        bal_pri += pline.prin_amt
                                        bal_int += pline.int_amt
                                        bal_fees += pline.fees_amt

                        if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                         "%Y-%m-%d"):  # == 'draft'
                            tot_prin += inst.capital
                            tot_int += inst.interest
                            tot_fee += inst.fees

                ## for total outstanding amount ..........................
                past_pri = tot_prin - bal_pri
                past_int = tot_int - bal_int
                past_fees = tot_fee - bal_fees

                bal_pri = tot_bal_pri - paid_capital
                bal_int = tot_bal_int - paid_interest
                bal_fees = tot_bal_fees - paid_fee

                for dis in hp.disbursement_details:
                    amt += dis.disbursement_amt

                for pays in hp.repayment_details:
                    if datetime.strptime(str(pays.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                         "%Y-%m-%d") and pays.is_button_visible != False:
                        amt_paid += pays.amt

                for user_hp in hp_obj.search([('partner_id', '=', hp.partner_id.id)], order="id asc"):
                    cycle += 1
                    sec_cycle_dict.update({user_hp.id: cycle})

                local_paid_total = local_paid_pri + local_paid_int + local_paid_fee
                local_bal_total = bal_pri + bal_int + bal_fees
                local_past_due = past_pri + past_int + past_fees
                exported_data.append([str(count),
                                      name,
                                      hp.hp_id,
                                      hp.name or '',
                                      dict(hp._fields['department'].selection).get(hp.department) or '',
                                      dict(hp._fields['is_refugee'].selection).get(hp.is_refugee) or '',
                                      str(sec_cycle_dict.get(hp.id)),
                                      hp.approve_date and datetime.strptime(str(hp.approve_date), "%Y-%m-%d").strftime(
                                          '%m/%d/%Y') or '',
                                      amt,
                                      round(local_paid_total, 2),
                                      amt_paid,
                                      round(local_bal_total, 2),
                                      round(bal_pri + bal_int + bal_fees, 2),
                                      round(local_past_due, 2),
                                      round(past_pri + past_int + past_fees, 2),
                                      dict(hp._fields['state'].selection).get(hp.state)
                                      ])
                count += 1

        elif self.report_type == 'product':
            file = 'product_report.xls'
            head = ['S/N', "Company name/client's name", 'Account Number',
                    'Purpose', 'Department', 'Is Refugee',
                    'Cycle', 'Product', 'Gender',
                    'Approval date', 'Amount Disbursed', 'Currency',
                    'Amount paid', 'Amount paid(%s)' % curr,
                    'Current Balance', 'Current Balance(%s)' % curr,
                    'Amount past due', 'Amount past due(%s)' % curr,
                    'Application State']
            for item in head:
                worksheet.write(r, c, item, bold)
                c += 1

            pro_cycle_dict = {}
            for hp in hp_obj.search([('approve_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d"))]):
                amt = amt_paid = 0.00
                cycle = 0
                name = ''

                bal_pri = bal_int = bal_fees = 0.00
                past_pri = past_int = past_fees = 0.00
                local_paid_pri = local_paid_int = local_paid_fee = 0.00
                tot_prin = tot_int = tot_fee = 0.0
                paid_capital = paid_interest = paid_fee = paid_pri = paid_int = paid_fees = 0.0
                tot_bal_pri = tot_bal_int = tot_bal_fees = 0.0
                currency_name = ''
                cur_id = None
                if hp.partner_id.parent_id:
                    if hp.partner_id.parent_id.name == hp.partner_id.name:
                        name = hp.partner_id.name
                    else:
                        name = hp.partner_id.parent_id.name + ', ' + hp.partner_id.name
                else:
                    name = hp.partner_id.name
                for inst in hp.installment_id:
                    tot_bal_pri += inst.capital
                    tot_bal_int += inst.interest
                    tot_bal_fees += inst.fees
                    if inst.date:
                        '''Get paid balance for current balance'''
                        paid_line = self.env['payment.details'].search(
                            [('pay_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d")), ('line_id', '=', inst.id),
                             ('state', '!=', 'cancel')])
                        for o in paid_line:
                            paid_capital += o.prin_amt
                            paid_interest += o.int_amt
                            paid_fee += o.fees_amt

                        if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                            '''Get Actual Payment Amount'''
                            paid_pri += inst.capital - inst.outstanding_prin
                            paid_int += inst.interest - inst.outstanding_int
                            paid_fees += inst.fees - inst.outstanding_fees
                            local_paid_pri += inst.local_principle
                            local_paid_int += inst.local_interest
                            local_paid_fee += inst.local_fees

                            '''Get Balance Amount'''
                            pay_line = self.env['payment.details'].search([('line_id', '=', inst.id), ('state', '!=', 'cancel')])
                            for pline in pay_line:
                                if pline.pay_date:
                                    if datetime.strptime(str(pline.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                                        bal_pri += pline.prin_amt
                                        bal_int += pline.int_amt
                                        bal_fees += pline.fees_amt
                        if datetime.strptime(str(inst.date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):  # == 'draft'
                            tot_prin += inst.capital
                            tot_int += inst.interest
                            tot_fee += inst.fees

                ## for total outstanding amount ..........................
                past_pri = tot_prin - bal_pri
                past_int = tot_int - bal_int
                past_fees = tot_fee - bal_fees

                bal_pri = tot_bal_pri - paid_capital
                bal_int = tot_bal_int - paid_interest
                bal_fees = tot_bal_fees - paid_fee

                for dis in hp.disbursement_details:
                    amt += dis.disbursement_amt

                for pays in hp.repayment_details:
                    if datetime.strptime(str(pays.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date),
                                                                                         "%Y-%m-%d") and pays.is_button_visible != False:
                        amt_paid += pays.amt

                for user_hp in hp_obj.search([('partner_id', '=', hp.partner_id.id)], order="id asc"):
                    cycle += 1
                    pro_cycle_dict.update({user_hp.id: cycle})

                local_paid_total = local_paid_pri + local_paid_int + local_paid_fee
                local_bal_total = bal_pri + bal_int + bal_fees
                local_past_due = past_pri + past_int + past_fees

                exported_data.append([str(count),
                                      name,
                                      hp.hp_id,
                                      hp.name or '',
                                      dict(hp._fields['department'].selection).get(hp.department) or '',
                                      dict(hp._fields['is_refugee'].selection).get(hp.is_refugee) or '',
                                      str(pro_cycle_dict.get(hp.id)),
                                      hp.hp_type and hp.hp_type.name or '',
                                      hp.approve_date and datetime.strptime(str(hp.approve_date), "%Y-%m-%d").strftime(
                                          '%m/%d/%Y') or '',
                                      amt,
                                      round(local_paid_total, 2),
                                      amt_paid,
                                      round(local_bal_total, 2),
                                      round(bal_pri + bal_int + bal_fees, 2),
                                      round(local_past_due, 2),
                                      round(past_pri + past_int + past_fees, 2),
                                      dict(hp._fields['state'].selection).get(hp.state)
                                      ])
                count += 1

        elif self.report_type == 'closed':
            file = 'closed_hp_report.xls'
            head = ['S/N', "Company name/client's name", 'Account Number',
                    'Purpose', 'Department', 'Is Refugee',
                    'Cycle', 'Sector of activity',
                    'Gender', 'Approval date', 'Amount Disbursed', 'Currency', 'Close/final payment date']
            for item in head:
                worksheet.write(r, c, item, bold)
                c += 1
            cycle_dict_close = {}
            for hp in hp_obj.search(
                    [('state', 'in', ['done']), ('approve_date', '<=', datetime.strptime(str(self.date), "%Y-%m-%d"))]):
                amt = 0
                cycle = 0
                name = ''
                currency_name = ''
                if hp.partner_id.parent_id:
                    if hp.partner_id.parent_id.name == hp.partner_id.name:
                        name = hp.partner_id.name
                    else:
                        name = hp.partner_id.parent_id.name + ', ' + hp.partner_id.name
                else:
                    name = hp.partner_id.name

                for dis in hp.disbursement_details:
                    if datetime.strptime(str(dis.bill_date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                        amt += dis.disbursement_amt

                final_date_list = []
                final_date = ''

                for pay in hp.repayment_details:
                    if datetime.strptime(str(pay.pay_date), "%Y-%m-%d") <= datetime.strptime(str(self.date), "%Y-%m-%d"):
                        final_date_list.append(pay.pay_date)
                if final_date_list:
                    final_date = max(final_date_list)
                    final_date = datetime.strptime(str(final_date), "%Y-%m-%d").strftime('%m/%d/%Y')

                for user_hp in hp_obj.search([('partner_id', '=', hp.partner_id.id)], order="id asc"):
                    cycle += 1
                    cycle_dict_close.update({user_hp.id: cycle})

                exported_data.append([str(count),
                                      name,
                                      hp.hp_id,
                                      hp.name or '',
                                      dict(hp._fields['department'].selection).get(hp.department) or '',
                                      dict(hp._fields['is_refugee'].selection).get(hp.is_refugee) or '',
                                      str(cycle_dict_close.get(hp.id)),
                                      hp.approve_date and datetime.strptime(str(hp.approve_date), "%Y-%m-%d").strftime(
                                          '%m/%d/%Y') or '',
                                      amt,
                                      final_date
                                      ])
                count += 1
        else:
            raise UserError('Please Select Loan Report Type')

        r += 1
        for data in exported_data:
            c = 0
            for item in data:
                worksheet.write(r, c, item, decimal_style)
                c += 1
            r += 1
        if r > 1:
            if self.report_type == 'portfolio':
                if self.type == "detailed_report":
                    worksheet.write(r, 0, "Total", bold)
                    worksheet.write(r, 29, xlwt.Formula("SUM(AD2:AD%d)" % (r)), decimal_style1)
                    worksheet.write(r, 31, xlwt.Formula("SUM(AF2:AF%d)" % (r)), decimal_style1)
                    worksheet.write(r, 33, xlwt.Formula("SUM(AH2:AH%d)" % (r)), decimal_style1)
                    worksheet.write(r, 35, xlwt.Formula("SUM(AJ2:AJ%d)" % (r)), decimal_style1)
                    worksheet.write(r, 37, xlwt.Formula("SUM(AL2:AL%d)" % (r)), decimal_style1)
                    worksheet.write(r, 39, xlwt.Formula("SUM(AN2:AN%d)" % (r)), decimal_style1)
                    worksheet.write(r, 41, xlwt.Formula("SUM(AP2:AP%d)" % (r)), decimal_style1)
                    worksheet.write(r, 43, xlwt.Formula("SUM(AR2:AR%d)" % (r)), decimal_style1)
                    worksheet.write(r, 45, xlwt.Formula("SUM(AT2:AT%d)" % (r)), decimal_style1)
                    worksheet.write(r, 47, xlwt.Formula("SUM(AV2:AV%d)" % (r)), decimal_style1)
                    worksheet.write(r, 49, xlwt.Formula("SUM(AX2:AX%d)" % (r)), decimal_style1)
                    worksheet.write(r, 51, xlwt.Formula("SUM(AZ2:AZ%d)" % (r)), decimal_style1)
                    worksheet.write(r, 53, xlwt.Formula("SUM(BB2:BB%d)" % (r)), decimal_style1)
                    worksheet.write(r, 55, xlwt.Formula("SUM(BD2:BD%d)" % (r)), decimal_style1)
                    worksheet.write(r, 57, xlwt.Formula("SUM(BF2:BF%d)" % (r)), decimal_style1)
                    worksheet.write(r, 59, xlwt.Formula("SUM(BH2:BH%d)" % (r)), decimal_style1)
            elif self.report_type == 'sector':
                worksheet.write(r, 0, "Total", bold)
                worksheet.write(r, 15, xlwt.Formula("SUM(O2:O%d)" % (r)), decimal_style1)
                worksheet.write(r, 17, xlwt.Formula("SUM(R2:R%d)" % (r)), decimal_style1)
                worksheet.write(r, 19, xlwt.Formula("SUM(T2:T%d)" % (r)), decimal_style1)

            elif self.report_type == 'product':
                worksheet.write(r, 0, "Total", bold)
                worksheet.write(r, 15, xlwt.Formula("SUM(O2:O%d)" % (r)), decimal_style1)
                worksheet.write(r, 17, xlwt.Formula("SUM(R2:R%d)" % (r)), decimal_style1)
                worksheet.write(r, 19, xlwt.Formula("SUM(T2:T%d)" % (r)), decimal_style1)
            else:
                pass

        buf = io.BytesIO()
        workbook.save(buf)
        out = base64.encodestring(buf.getvalue())

        self.exported_file = out
        self.file_name = file

        return {
            'type': 'ir.actions.report.xml',
            'report_type': 'controller',
            'report_file': '/web/content/wiz.download.report/%s/data/%s?download=true' % (self.id, file),
        }
