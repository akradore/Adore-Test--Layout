import time
import calendar
import re
import math
import logging
from odoo import fields, models, api, _
from datetime import date,datetime, timedelta
from odoo import exceptions
from odoo.exceptions import UserError, ValidationError, Warning
from odoo.tools.safe_eval import safe_eval
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger("Hp Account")

class AccountHP(models.Model):
    _name = 'account.hp'
    _description = "Account HP"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'hp_id'

    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['hp.stages'].search([])

    def _get_default_stage_id(self):
        """ Gives default stage_id """
        state_obj = self.env['hp.stages'].search([('sequence', '=', 1)], limit=1)
        if not state_obj:
            return False
        return state_obj.id

    def get_days(self):
        day_list = []
        for i in range(1, 32):
            day_list.append((str(i), str(i)))
        return day_list

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = task.legend_normal
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = task.legend_blocked
            else:
                task.kanban_state_label = task.legend_done

    stage_id = fields.Many2one('hp.stages', string='Stage', group_expand='_read_group_stage_ids',
                               default=_get_default_stage_id, track_visibility='onchange', index=True, copy=False)
    color = fields.Integer(string='Color Index')
    priority = fields.Selection([
                            ('0', 'Low'),
                            ('1', 'Normal'),
                        ], default='0', index=True, string="Priority")

    kanban_state = fields.Selection([
                            ('normal', 'Grey'),
                            ('done', 'Green'),
                            ('blocked', 'Red')], string='Kanban State',
                            copy=False, default='normal', required=True,
        help="A task's kanban state indicates special situations affecting it:\n"
             " * Grey is the default situation\n"
             " * Red indicates something is preventing the progress of this task\n"
             " * Green indicates the task is ready to be pulled to the next stage")
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban  State Label',
                                     track_visibility='onchange')
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', readonly=True,
                                 related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', readonly=True,
                              related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', readonly=True,
                                related_sudo=False)

    hp_id = fields.Char('HP Id', size=32, readonly=True, track_visibility='onchange')
    proof_id = fields.One2many('account.hp.proof', 'hp_id', 'Proof Detail')
    name = fields.Char('HP Name', size=128, required=True, track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', 'Customer', required=True, track_visibility='onchange')
    proof_1 = fields.Many2one('res.partner', 'Guarantor/Co-Signer 1', track_visibility='onchange')
    proof_2 = fields.Many2one('res.partner', 'Guarantor/Co-Signer 2', track_visibility='onchange')
    hp_type = fields.Many2one('account.hp.hptype', 'Agreement Type', required=True, track_visibility='onchange')
    hp_period = fields.Many2one('hp.installment.period', 'HP Period', required=True, track_visibility='onchange')
    hp_amount = fields.Float('Account HP Amount', digits=(12, 2), required=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    approve_amount = fields.Float('Disbursement Amount', digits=(12, 2), readonly=True, track_visibility='onchange')
    process_fee = fields.Float('Processing Fee', digits=(12, 2), track_visibility='onchange')
    initiation_fee = fields.Float(string='Initiation Fee', compute='_get_amt_from_hptype', store=True)
    finance_charges = fields.Float(string='Finance Charges', compute='_get_amt_from_hptype', store=True)
    total_installment = fields.Integer('Total Installment', readonly=False, required=True, default=0.0,
                                       track_visibility='onchange')
    interest_rate = fields.Float(string='Interest Rate (%)', store=True,
                                 track_visibility='onchange')
    department = fields.Selection([('mbs', 'Micro Business Solutions'), ('sme', 'SME Growth')], string="Department")
    is_refugee = fields.Selection([('ref', 'Refugee'), ('non_ref', 'Non Refugee')])
    apply_date = fields.Date('Apply Date', states={'draft': [('readonly', False)]}, default=time.strftime('%Y-%m-%d'), track_visibility='onchange')
    approve_date = fields.Date('Approved Date', readonly=False, track_visibility='onchange')
    state = fields.Selection([
                        ('draft', 'New'),
                        ('apply', 'Application Review'),
                        ('partial', 'Partially Disbursed'),
                        ('approved', 'Approved'),
                        ('done', 'Closed'),
                        ('cancel', 'Declined'),
                    ], 'State', readonly=True, index=True, default='draft', track_visibility='onchange')
    return_type = fields.Selection([
                        ('cash', 'By Cash'),
                        ('automatic', 'Debit Order'),
                    ], 'Payment Type', index=True, default='automatic', track_visibility='onchange')
    debit_order_date = fields.Selection(selection='get_days',string="Debit Order Date", track_visibility='onchange')
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist', required=False, readonly=True,
                                   states={'draft': [('readonly', False)]}, track_visibility='onchange')
    installment_id = fields.One2many('account.hp.installment', 'hp_id', 'Installments', track_visibility='onchange')
    interest = fields.Float('Interest', digits=(12, 2), track_visibility='onchange', copy=False)
    arrears_interest_rate = fields.Float('Arrears Interest Rate', digits=(12, 2), track_visibility='onchange', copy=False)
    notes = fields.Text('Description', track_visibility='onchange')
    missing_documents = fields.Text('Missing Documents', track_visibility='onchange')
    customer_signature = fields.Binary('Customer Signature', track_visibility='onchange')
    stage_reason = fields.Text('Stage Reason')

    disbursement_details = fields.One2many("account.hp.disbursement", 'hp_id', readonly=True)
    old_disburse_amt = fields.Float("Remain amt")
    payment_freq = fields.Selection([('daily', 'Daily'), ('weekly', 'Weekly'), ('bi_month', 'Bi Monthly'), ('monthly', 'Monthly'),
                                    ('quarterly', 'Quarterly'), ('half_yearly', 'Half-Yearly'), ('yearly', 'Yearly')], "Payment Frequency",
                                    default="monthly")
    payment_schedule_ids = fields.One2many('payment.schedule.line', 'hp_id', 'Payment Schedule', track_visibility='onchange')

    cus_pay_acc = fields.Many2one('account.account', method=True, string="Customer HP Account", company_dependent=True, track_visibility='onchange')
    int_acc = fields.Many2one('account.account', method=True, string="Interest Account", company_dependent=True, track_visibility='onchange')
    bank_acc = fields.Many2one('account.account', method=True, string="Bank Account", company_dependent=True, track_visibility='onchange')
    proc_fee = fields.Many2one('account.account', method=True, string="Processing Fee Account", company_dependent=True, track_visibility='onchange')
    anal_acc = fields.Many2one('account.analytic.account', method=True, string="Analytic Account", company_dependent=True, help="This analytic account will be used", track_visibility='onchange')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    move_id = fields.One2many('account.move.line', 'acc_hp_id', 'Move Line', readonly=True, track_visibility='onchange')
    store_id = fields.Many2one('stores', string="Store")

    hp_amt = fields.Float('Amount ', digits=(12, 2), required=True, track_visibility='onchange')
    req_amt = fields.Float('Amount Required', digits=(12, 2))
    deposit_amt = fields.Float('Deposit', digits=(12, 2), compute='_get_amt_from_hptype', store=True)
    deposit_per = fields.Float(string='Deposit (%)', readonly=False)

    month = fields.Integer('Tenure (Months)', track_visibility='onchange')
    int_rate = fields.Float('Interest Rate', digits=(12, 2), default=1, track_visibility='onchange')
    emi_cal = fields.Float('Calculated Monthly EMI', readonly=True)
    tot_amt = fields.Float('Total Amount with Interest', readonly=True)
    flat_pa = fields.Float('Flat Interest Rate PA', readonly=True)
    flat_pm = fields.Float('Flat Interest Rate PM', readonly=True)
    tot_int_amt = fields.Float('Total Interest Amount', readonly=True)
    yr_int_amt = fields.Float('Yearly Interest Amount', readonly=True)

    flat_emi_cal = fields.Float('Calculated FLat Monthly  EMI', readonly=True)
    flat_tot_amt = fields.Float('Total Flat Amount with  Interest', readonly=True)
    flat_pa1 = fields.Float('Flat Interest Rate PA1', readonly=True)
    flat_pm1 = fields.Float('Flat Interest Rate  PM1', readonly=True)
    flat_tot_int_amt = fields.Float('Total Flat Interest  Amount', readonly=True)
    flat_yr_int_amt = fields.Float('Yearly Flat Interest  Amount', readonly=True)

    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get('account.hp'))
    group_members = fields.One2many('res.partner.hp.line', 'hp_id', 'Group Members')
    is_group = fields.Boolean(related='partner_id.is_group', store=True)
    is_collateral = fields.Boolean(string='Is Collateral', default=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)
    controller_id = fields.Many2one('res.users', string='Assigned Controller', index=True, track_visibility='onchange')
    date_done = fields.Date('Date Done', readonly=True)
    # collateral_lines = fields.One2many('collateral.line', 'hp_id', 'Collateral Lines')
    is_gpi = fields.Boolean(string='Goods Protection Insurance')
    is_cli = fields.Boolean(string='Credit Life Insurance', default=True, readonly=True)
    reference_checks_done = fields.Boolean(string='Reference Checks Done?')

    repayment_details = fields.One2many("account.hp.repayment", 'hp_id', readonly=True)
    repayment_basis = fields.Selection([('disbursed_amt', 'Disbursed Amount'), ('sanctioned_amt', 'Sanctioned Amount')],
                                       "Repayment Basis", default="sanctioned_amt")
    grace_period = fields.Integer("Grace Period (Days)")
    classification = fields.Char(string="Classification")
    interest_type = fields.Selection(related="hp_type.calculation", string='Interest Type', readonly=True, store=True,
                                     track_visibility='onchange')
    city = fields.Char(related='partner_id.city', string='City', store=True)

    total_payment = fields.Float(compute='_compute_payment')
    total_principal_paid = fields.Float(compute='_compute_payment')
    total_interest_paid = fields.Float(compute='_compute_payment')
    total_fees_paid = fields.Float(compute='_compute_payment')

    application_status  = fields.Char(string="Application Status",)

    contract_term = fields.Integer(string="Contract Term",)
    sale_value_inc = fields.Float(string="Sale Value (Incl)", )
    delivery_charges = fields.Float(string="Delivery Charges", )
    contract_value_inc = fields.Float(string="Contract Value (Inc)", )
    approve_finance_charges = fields.Float(string="Total Finance Charges", )
    contract_total = fields.Float(string="Contract Total", )

    capital_instalment = fields.Float(string="Capital Instalment",)
    monthly_service_fee = fields.Float(string="Monthly Service Fee",)
    monthly_insurance_cost = fields.Float(string="Monthly Insurance Cost",)
    total_monthly_instalment = fields.Float(string="Total Monthly Installment",)
    first_payment_date = fields.Date(string="First Payment Date",)
    final_payment_date = fields.Date(string="Final Payment Date",)
    last_payment_date = fields.Date(string="Last Payment Date",)
    last_payment_amount = fields.Float(string="Last Payment Amount",)

    initial_contract_balance = fields.Float(string="Initial Contract Balance",)
    initial_finance_charges = fields.Float(string="Initial Finance Charges",)
    deposit_payment = fields.Float(string="Deposit Payment",)
    payments_made_to_date = fields.Float(string="Payments Made To Date",)
    payments_made = fields.Integer(string="HP Payments Made",)
    balance_remaining = fields.Float(string="Balance Remaining",)
    interest_remaining = fields.Float(string="Interest Remaining",)
    months_remaining = fields.Integer(string="Months Remaining",)
    early_settlement_amount = fields.Float(string="Early Settlement Amount",)

    overdue_amount = fields.Float(string="Overdue Amount",)
    months_overdue = fields.Integer(string="Months Overdue",)
    interest_overdue = fields.Float(string="Interest on Overdue",)
    time_overdue = fields.Integer(string="Times Overdue",)
    selected_offer_id = fields.Integer(string="Selected Offer ID",)
    invoice_count = fields.Integer(string="Invoices",compute="_get_inovice_count")
    delivery_count = fields.Integer(string="Delivery count",compute="_get_inovice_count")

    hp_deposit_paid = fields.Float(string="Deposit Paid",)
    hp_deposit_outstanding = fields.Float(string="Deposit Outstanding",compute="_get_outstanding_deposit")
    hp_payment_count = fields.Integer(string="Payments",compute = '_get_payment_count')
    # new_field = fields.Integer(string="",)
    # new_field = fields.Integer(string="",)
    # new_field = fields.Integer(string="",)

    def _get_payment_count(self):
        for record in self:
            record.hp_payment_count = len(self.env['account.payment'].search([('hp_id','=',record.id)]))

    @api.depends('hp_deposit_paid')
    def _get_outstanding_deposit(self):
        for record in self:
            record.hp_deposit_outstanding = record.deposit_amt - record.hp_deposit_paid

    def _get_inovice_count(self):
        for record in self:
            record.invoice_count = len(self.sale_order_id.invoice_ids.ids)
            record.delivery_count = len(self.sale_order_id.picking_ids.ids)

    @api.model
    def create(self, vals):
        vals['hp_id'] = self.env['ir.sequence'].next_by_code('hp.account.number')
        analytic_acc_id = self.env['account.analytic.account'].create({'name': vals['name'],
                                                                       'code': vals['hp_id'],
                                                                       'partner_id': vals['partner_id']})
        vals['anal_acc'] = analytic_acc_id.id
        if vals['sale_order_id']:
            sale_order_id = self.env['sale.order'].browse(vals['sale_order_id'])
            sale_order_id.analytic_account_id = vals['anal_acc']
        res = super(AccountHP, self).create(vals)
        template = self.env.ref('hire_purchase.email_template_hp_creation')
        mail_obj = self.env['mail.template'].browse(template.id)
        if res.message_follower_ids and res.message_follower_ids[0].partner_id:
            for user in res.message_follower_ids:
                if not user.id == res.partner_id.id:
                    mail_obj.partner_to = user.id
                    mail_obj.sudo().send_mail(res.id)
        return res

    def convert_month_to_year(self, mth):
        if mth:
            return mth / 12

    def get_flat(self, amt, mth, intr):
        year = self.convert_month_to_year(mth)
        interest_amount = (amt * intr) / 100
        if year:
            total_interest = interest_amount * year
            moth_int = (amt / mth) + (total_interest / mth)
            total_amt_with_int = amt + total_interest
            year_int = total_interest / year
            self.write({'flat_tot_int_amt': total_interest, \
                        'flat_emi_cal': moth_int, 'flat_tot_amt': total_amt_with_int, \
                        'flat_yr_int_amt': year_int,
                        })

    def get_reducing(self, amt, mth, intr):
        try:
            k = 12
            i = intr / 100
            a = i / k or 0.00
            b = (1 - (1 / ((1 + (i / k)) ** mth))) or 0.00
            emi = ((amt * a) / b) or 0.00
            tot_amt = emi * mth
            tot_int_amt = tot_amt - amt
            yr_amt = (tot_int_amt * k) / mth
            flat_pa = (yr_amt * 100) / amt
            flat_pm = flat_pa / k
            self.write({'emi_cal':emi, 'tot_amt':tot_amt,\
                        'flat_pa':flat_pa, 'flat_pm':flat_pm,\
                        'tot_int_amt':tot_int_amt, 'yr_int_amt':yr_amt})
        except ZeroDivisionError:
            flat_pm = 0

    def cal_amt(self):
        for read_id in self.read():
            amt = read_id['hp_amt']
            mth = read_id['month']
            intr = read_id['int_rate']
            self.get_reducing(amt, mth, intr)
            self.get_flat(amt, mth, intr)

    def hp_interest_get(self):
        for hp in self:
            self.write({'approve_amount': hp.hp_amount - hp.process_fee, 'approve_date': time.strftime('%Y-%m-%d')})
        return True

    def upload_hp_document(self):
        if not len(self.proof_id):
            raise UserError(_("No Documents available for upload"))
        if not len(self.proof_id.filtered(lambda x:x.upload_status == False and x.state == 'done')):
            raise UserError(_("All attached verified documents are uploaded already"))

        frontier_obj = self.env['frontier.api.calls']
        app_nr = frontier_obj.search([('hp_account_id','=',self.id)]).app_nr or False
        body = self._prepare_document_upload(app_nr=app_nr)
        if not body:
            raise UserError(_("No Documents available for upload"))

        upload_response = frontier_obj._upload_hp_document(body=body) or []
        for resp in upload_response:
            if upload_response[resp] == True or upload_response[resp].lower() == 'already uploaded':
                self.proof_id.filtered(lambda x: x.type.shortcut.lower() == resp.lower()).upload_status = True
        self.check_missing_document()

    def approve_hp_application(self):
        frontier_obj = self.env['frontier.api.calls'].search([('hp_account_id','=',self.id)])
        if self.stage_id.id == self.env.ref('hire_purchase.hp_to_offer_acceptance').id:
            offers = frontier_obj.check_application_status(AppNr=frontier_obj.app_nr,get_offers=True)
            offers = isinstance(offers,dict) and offers.get('offers') or isinstance(offers,list) and offers
            offers.sort(key=lambda x:x['term'])
            return self.show_offer_wizard(offers)

    def show_offer_wizard(self,offers=False):
        if offers:
            offer_create_values = []
            for offer in offers:
                offer_create_values.append((0,0, {'hp_amount': offer.get('loanAmount'),
                                                  'instalment': offer.get('instalment'),
                                                  'offer_id':offer.get('offerId'),
                                                  'adminfee': offer.get('adminFee'),
                                                  'interest': offer.get('interest'),
                                                  'initiation_fee': offer.get('initiationFee'),
                                                  'total_vat': offer.get('totalVAT'),
                                                  'tcoc': offer.get('tcoc'),
                                                  'settlement_amount': offer.get('settlementAmount'),
                                                  'interest_rate': offer.get('interestRate'),
                                                  'term': offer.get('term'),
                                                  'first_instalment_date': datetime.strptime(offer.get('firstInstalmentDate'),"%Y-%m-%dT%H:%M:%S"),
                                                  'insurance_amt': offer.get('insuranceAmount'),
                                                  'life_insurance_amount':offer.get("lifeInsuranceAmount"),
                                                  'payment_freq': offer.get('paymentFrequency').lower(),
                                                  'deposit_amt': offer.get('depositAmount'),
                                                  'deposit_per': offer.get('depositPercentage')}))

            view_id = self.env.ref('hire_purchase.approve_offer_view').id
            return {
                'name': _('Offers'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'approve.offers',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'context': {'default_offer_ids':offer_create_values},
                'target': 'new'
            }

    def _prepare_application_take_up(self,status='Approved',reason=False):
        frontier_obj = self.env['frontier.api.calls']
        frontier_obj = frontier_obj.search([('hp_account_id','=',self.id)])
        data = {
            'appNr': frontier_obj.app_nr or '',
            'branchFinalDecision': status,
            'selectedOfferId':self.selected_offer_id or None,
            'statusDate': str(datetime.today())
            }
        if reason:
           data.update(reason={'code':'EV','description':reason})
        return data

    def _prepare_document_upload(self,app_nr = False):
        if not app_nr:
            raise UserError(_("Appnr is missing"))
        body = []
        document_type = self.env['frontier.api.calls']._get_document_type()
        for proof in self.proof_id.filtered(lambda x:not x.upload_status and x.type.shortcut in document_type):
            body.append({
                "appNr":app_nr,
                "documentCode": proof.type.shortcut or '',
                "imageType": proof.file_name.split('.')[-1].upper(),
                "image": proof.document.decode('utf-8') or '',
                "fileName":proof.file_name,
                "userName":self.partner_id.name or '',
                "documentQueue": "DEF"
            })
        return len(body) and body or False

    def approve_finance(self):
        if not self.proof_id:
            raise UserError("Dear applicant please provide proofs")
        else:
            required_proof_ids = [type.name.id for type in self.hp_type.prooftypes if type.is_mandatory]
            if len(self.proof_id) < len(required_proof_ids):
                proof_names = [x.name.name for x in self.hp_type.prooftypes if x.is_mandatory]
                st = ''
                for p in proof_names:
                    st = st + '\n' + str(p)
                raise UserError("Following proofs are mandatory: %s" % st)
            proof_type = []
            for proof in self.proof_id:
                if proof.type:
                    proof_type.append(proof.type.name.id)
            for proof in required_proof_ids:
                if not proof in proof_type:
                    proof_name = self.env['account.hp.proof.type'].search([('id', '=', proof)])
                    raise UserError("Following mandatory proof(s) is/are still missing:\n %s" % proof_name.name)
        if self.hp_amount <= 0:
            raise UserError("Sanctioned amount cannot be \"0.00\"")
        self.hp_interest_get()
        self.cal_amt()
        template = self.env.ref('hire_purchase.email_template_hp_sanction')
        mail_obj = self.env['mail.template'].browse(template.id).sudo()
        mail_obj.send_mail(self.id)
        if self.message_follower_ids and self.message_follower_ids[0].partner_id:
            for user in self.message_follower_ids:
                if not user.id == self.partner_id.id:
                    mail_obj.partner_to = user.id
                    mail_obj.sudo().send_mail(self.id)
        self.write({'state': 'apply'})

    @api.depends('hp_type','deposit_per')
    def _get_amt_from_hptype(self):
        is_done_by_hp = self.env['ir.config_parameter'].sudo().get_param('calculation_done_by','frontier')
        if is_done_by_hp == 'hp_app':
            for each in self:
                each.deposit_amt = (each.deposit_per / 100) * each.req_amt
                each.initiation_fee = (each.hp_type.initiation_fee / 100) * each.req_amt
                each.finance_charges = (each.hp_type.finance_charges / 100) * each.req_amt

    @api.depends('apply_date', 'total_installment', 'hp_amount', 'hp_type')
    def compute_hp_interest(self):
        for hp in self:
            rate = 0.0
            for int_version in hp.hp_type.interestversion_ids:
                if int_version.start_date and int_version.end_date:
                    if hp.apply_date >= int_version.start_date and hp.apply_date <= int_version.end_date:
                        date_check = 1
                    else:
                        date_check = 0
                elif int_version.start_date:
                    if hp.apply_date >= int_version.start_date:
                        date_check = 1
                    else:
                        date_check = 0
                elif int_version.end_date:
                    if hp.apply_date <= int_version.end_date:
                        date_check = 1
                    else:
                        date_check = 0
                else:
                    date_check = 1
                if date_check:
                    for int_version_line in int_version.interestversionline_ids:
                        if int_version_line.min_month and int_version_line.max_month:
                            if hp.total_installment >= int_version_line.min_month and hp.total_installment <= int_version_line.max_month:
                                month_check = 1
                            else:
                                month_check = 0
                        elif int_version_line.min_month:
                            if hp.total_installment >= int_version_line.min_month:
                                month_check = 1
                            else:
                                month_check = 0
                        elif int_version_line.max_month:
                            if hp.total_installment <= int_version_line.max_month:
                                month_check = 1
                            else:
                                month_check = 0
                        else:
                            month_check = 1
                        if month_check:
                            if int_version_line.min_amount and int_version_line.max_amount:
                                if hp.hp_amount >= int_version_line.min_amount and hp.hp_amount <= int_version_line.max_amount:
                                    rate = int_version_line.rate
                                    break
                            elif int_version_line.min_amount:
                                if hp.hp_amount >= int_version_line.min_amount:
                                    rate = int_version_line.rate
                                    break
                            elif int_version_line.max_amount:
                                if hp.hp_amount <= int_version_line.max_amount:
                                    rate = int_version_line.rate
                                    break
                            else:
                                rate = int_version_line.rate
                                break
            hp.interest_rate = rate

    def _compute_payment(self):
        for ele in self:
            paid_capital = 0
            paid_interest = 0
            paid_fee = 0
            for line in ele.installment_id:
                paid_line = self.env['payment.details'].search([('line_id', '=', line.id), ('state', '!=', 'cancel')])
                for o in paid_line:
                    paid_capital += o.prin_amt
                    paid_interest += o.int_amt
                    paid_fee += o.fees_amt
            ele.total_payment = paid_capital + paid_interest + paid_fee
            ele.total_principal_paid = paid_capital
            ele.total_interest_paid = paid_interest
            ele.total_fees_paid = paid_fee

    @api.constrains('deposit_per')
    def _check_deposit_per(self):
        if self.deposit_per < self.hp_type.deposit_percentage:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                raise ValidationError(_("You are not permitted to decrease the deposit % to be paid. Please consult your manager for further assistance."))


    @api.onchange('hp_type')
    def onchange_hp_type(self):
        if self.hp_type:
            self.deposit_per = self.hp_type.deposit_percentage

    @api.onchange('hp_period')
    def onchange_hp_period(self):
        if self.hp_period:
            self.total_installment = self.hp_period.period

    @api.onchange('deposit_amt', 'req_amt')
    def onchange_amount(self):
        if self.deposit_amt or self.req_amt:
            self.hp_amount = self.req_amt - self.deposit_amt

    @api.onchange('hp_amount')
    def onchange_hp_amount(self):
        if self.hp_amount:
            self.hp_amt = self.hp_amount

    @api.onchange('total_installment')
    def onchange_total_installment(self):
        if self.total_installment:
            self.month = self.total_installment

    @api.onchange('interest_rate')
    def onchange_interest_rate(self):
        if self.interest_rate:
            self.int_rate = self.interest_rate

    def action_view_sale_order(self):
        '''
             Opens the tree view of sale.order to show Sale Order Records
        '''
        self.ensure_one()
        action = self.env.ref('sale.action_orders').read()[0]
        if self.sale_order_id:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = self.sale_order_id.id
        return action

    def action_view_income_expense(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id.open_income_expense()

    def check_application_status(self,from_cron=False):
        app_nr = self._get_app_nr()
        if app_nr:
            resp = self.env['frontier.api.calls'].check_application_status(app_nr or False)
            application_status = resp.get('status','')
            display_status = re.sub(r"(\w)([A-Z])", r"\1 \2", application_status)
            context={}
            context['default_hp_application_status'] = display_status
            context['display_queue'] = 1
            if application_status == 'CompletedApproved':
                if resp.get('offers',False):
                    resp = self.show_offer_wizard(resp.get('offers'))
                    resp['context']['status']='CompletedApproved'
                    return resp
            elif application_status in ['Pending','SystemError']:
                hp_state = 'hp_to_review'
                context.update({
                    'default_hp_queue_code': resp.get('queue_code', ''),
                    'default_hp_queue_description': resp.get('queue_status', ''),
                    'display_queue': 0
                })
            elif application_status.lower() == 'pendingofferacceptance':
                hp_state = 'hp_to_offer_acceptance'
            elif application_status in ['CompletedInsolvent','CompletedDeclined','CompletedNTU','CompletedCancelled']:
                hp_state = 'hp_to_declined'

            if self.stage_id.id != self.env.ref('hire_purchase.'+hp_state).id:
                self.stage_id = self.env.ref('hire_purchase.'+hp_state).id
                self.message_post(body=display_status)
            if not from_cron:
                view_id = self.env.ref('hire_purchase.form_application_status_wizard').id
                return {
                    'name': _('Submitted HP Application'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'approve.offers',
                    'context':context,
                    'view_id': view_id,
                    'views': [(view_id, 'form')],
                    'target': 'new',
                }


    def _get_app_nr(self,):
        frontier_call = self.env['frontier.api.calls'].search([('sale_order_id','=',self.sale_order_id.id)])
        return frontier_call.app_nr

    def check_missing_document(self):
        app_nr = self._get_app_nr()
        if app_nr:
            missing_document_response = self.env['frontier.api.calls'].check_missing_documents(app_nr or False)
            if 'PIC' not in self.proof_id.mapped('type.shortcut'):
                missing_document_response+=', Customer photo'
            self.missing_documents = missing_document_response


    def action_view_invoice(self):
        if self.sale_order_id:
            if not self._context.get('view_delivery_order',False):
                invoices = self.sale_order_id.mapped('invoice_ids')
                action = self.env.ref('account.action_move_out_invoice_type').read()[0]
                if len(invoices) > 1:
                    action['domain'] = [('id', 'in', invoices.ids)]
                elif len(invoices) == 1:
                    action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
                    action['res_id'] = invoices.ids[0]
                else:
                    action = {'type': 'ir.actions.act_window_close'}
                return action
            else:
                deliver_ids = self.sale_order_id.mapped('picking_ids')
                if len(deliver_ids.ids):
                    return self.sale_order_id.action_view_delivery()
        return False

    def action_view_payments(self):
        return {
            'name': _('HP Payments'),
            'domain': [('hp_id', '=', self.id)],
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_account_payment_tree').id, 'tree'), (False, 'form')],
        }

    def approve_hp(self):
        context = dict(self.env.context or {})
        context['active_id'] = self.id
        return {
            'name': _('Disbursement Wizard'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hp.disbursement.wizard',
            'view_id': self.env.ref('hire_purchase.hp_disbursement_wizard_form_view').id,
            'type': 'ir.actions.act_window',
            'res_id': self.env.context.get('id'),
            'context': {'default_name': 'Repayment Schedule Shall be Generated On "%s". Do you want to continue ?' % (
                dict(self._fields['repayment_basis'].selection).get(self.repayment_basis))},
            'target': 'new'
        }

    def approve_proofs(self):
        # if self.is_collateral and (not self.collateral_lines):
        #     raise UserError("Dear applicant please provide collateral details")
        if self.partner_id.is_group and (not self.group_members):
            raise UserError("Please provide name of group members before you proceed further.")
        self.write({'state': 'apply'})

    def apply_hp(self):
        for hp in self:
            if hp.hp_type.calculation == 'flat':
                self._simple_interest_get(hp.interest_rate)
            else:
                self._simple_interest_get(hp.interest_rate)

    def get_grace_amount(self, tot_grc_amt, total_installment):
        amt = 0.0
        if tot_grc_amt and total_installment:
            amt = round(tot_grc_amt / total_installment, 2)
        return amt

    def get_rounding_amt(self, total, installment):
        if installment.capital:
            installment.capital = installment.capital + total
            installment.outstanding_prin = installment.outstanding_prin + total
            installment.total = installment.total + total

    def get_intstallments(self, total, rate_interest, total_installment):
        try:
            installment = round(((total * (rate_interest / 12)) / (1 - ((1 + rate_interest / 12) ** -(total_installment)))))
        except ZeroDivisionError:
            installment = 0
        return installment

    def _simple_interest_get(self, inter_rate):
        hp = self.read()
        installment_cr = self.env['account.hp.installment']
        if not self.partner_id:
            raise exceptions.except_orm(_('Field Required'), _('Please select Customer.'))

        part_id = self.partner_id.id
        int_rate = 0.0
        inter_sed = self.hp_type
        if inter_sed:
            inter_cal_type = inter_sed.calculation
            if inter_cal_type:
                if inter_cal_type == 'flat':
                    if self.hp_amount > 0.0 and self.total_installment > 0:
                        int_rate = self.calculate_eir(inter_rate, self.hp_amount, self.total_installment / 12,
                                                      inter_rate, 0)
                elif inter_cal_type == 'reducing':
                    int_rate = inter_rate

        rate_interest = int_rate / 100
        total = self.hp_amount
        approve_amt = self.approve_amount
        interest_amt = self.interest
        fees_amt = self._get_fees_amount(self.hp_type, approve_amt, interest_amt)
        try:
            installment = round(
                ((total * (rate_interest / 12)) / (1 - ((1 + rate_interest / 12) ** -(self.total_installment)))))
        except ZeroDivisionError:
            installment = 0

        i = 1
        j = 1
        interest = 0
        acc_hp_bank_cheque_obj = []
        date_update = datetime.date(2000, 0o1, 0o7)
        date_new = date.today()
        if date_update != date_new:
            new_month = date_new.month
            new_year = date_new.year
            date_update = date_update.replace(month=new_month)
            date_update = date_update.replace(year=new_year)
        present_month = date_update.month
        cnt = 0

        numbering = 1
        for num in self.installment_id:
            numbering += 1
        for i in range(numbering, self.total_installment + 1):
            interest_month = round(((total * rate_interest) / 12))
            principle_amount = round(installment - interest_month)
            remain_amount = round(total - principle_amount)
            for item in acc_hp_bank_cheque_obj:
                installment_cr.create({'name': 'installment' + str(i), 'hp_id': self.id, 'capital': principle_amount,
                                       'fees': fees_amt['total_fee'], 'interest': interest_month, 'total': installment,
                                       'cheque_id': item.id, 'partner_id': part_id})
                total = remain_amount
                interest += interest_month
        #                 i += 1
        self.write({'interest': interest});
        for line in self.installment_id:
            total_amt = 0.0
            total_amt = line.fees + line.total
            line.write({'total': total_amt})
        #         d_l = self.read(['apply_date'])[0]
        curr_date = self.apply_date
        sal_obj = self
        gross = self.hp_amount
        pr_fee = self.process_fee
        amt = self.approve_amount
        emp_name = self.partner_id.name
        journal_id = self.env['account.journal'].search([('name', '=', 'Bank')])[0]

        acc_move_line_name = emp_name
        try:
            move_vals = {
                'acc_hp_id': self.id,
                'name': acc_move_line_name,
                'date': curr_date,
                'account_id': sal_obj.proc_fee.id,
                'credit': pr_fee,
                'debit': 0.0,
                'journal_id': 5
            }

            move_vals1 = {
                'acc_hp_id': self.id,
                'name': acc_move_line_name,
                'date': curr_date,
                'account_id': sal_obj.partner_id.property_account_payable_id.id,
                'credit': amt,
                'debit': 0.0,
                'journal_id': 5
            }

            move_vals2 = {
                'acc_hp_id': self.id,
                'name': acc_move_line_name,
                'date': curr_date,
                'account_id': sal_obj.cus_pay_acc.id,
                'debit': gross,
                'credit': 0.0,
                'journal_id': 5
            }
            self.env['account.move'].create(
                {'name': '/', 'partner_id': self.partner_id.id, 'journal_id': journal_id.id, 'date': curr_date,
                 'line_ids': [(0, 0, move_vals), (0, 0, move_vals1), (0, 0, move_vals2)]})
        except:
            raise UserError(_('Could not create account move lines.'))

    def calculate_eir(self, e, t, n, i, o):
        r = float(i) / float(12 * n)
        a = float(e) / 100 * float(i) / 12
        s = r + a
        t = s
        o = s * n * 12
        l = float(e) / 100 / 12
        c = 1 + l
        d = -float(12 * n)
        u = d - 1
        h = s * math.pow(c, d)
        f = l * float(i)
        p = s - h - f
        m = float(12 * n) * s * math.pow(c, u) - float(i)
        g = l - p / m
        for v in range(0, 7):
            y = g * float(i)
            E = g
            b = 1 + E
            T = s - s * math.pow(b, d) - y
            C = float(12 * n) * s * math.pow(b, u) - float(i)
            D = g - T / C
            g = D
        I = 12 * g * 100
        return I

    ## total calculatin of tax for fee calculation in installment ................
    def get_tax_total(self, tx_ids, amount):
        tax_amt = 0.0
        for tx in tx_ids:
            if tx.amount:
                if not tx.price_include:
                    tax = (amount * tx.amount) / 100
                    tax_amt = tax_amt + tax
            else:
                tax = round(amount - ((amount * 100) / (100 + tx.amount)), 2)
                tax_amt = tax_amt + tax
        return tax_amt

        ## late fee tax calculations .........................

    def get_late_fee_tax_total(self, tx_ids, amount):
        tax_amt = 0.0
        dict_include_tx = {}
        for tx in tx_ids:
            if tx.amount:
                if not tx.price_include:
                    tax = (amount * tx.amount) / 100
                    tax_amt = tax_amt + tax
                else:
                    tax = (amount) - (amount * 100) / (100 + tx.amount)
                    tax_amt = tax_amt + tax
                    if tax_amt:
                        dict_include_tx.update({'include': tax_amt})
            else:
                tax = round(amount - ((amount * 100) / (100 + tx.amount)), 2)
                tax_amt = tax_amt + tax
        if dict_include_tx:
            return dict_include_tx
        return tax_amt

    ## total calculatin of tax for fee calculation in installment ................
    def get_tax_total_incl_exl(self, tx_ids, amount):
        tax_amt = 0.0
        for tx in tx_ids:
            if tx.amount:
                if not tx.price_include:
                    tax = (amount * tx.amount) / 100
                    tax_amt = round(tax_amt + tax, 2)
                else:
                    tax = (amount) - (amount * 100) / (100 + tx.amount)
                    tax_amt = round(tax_amt + tax, 2)
            else:
                tax = round(amount - ((amount * 100) / (100 + tx.amount)), 2)
                tax_amt = tax_amt + tax
        return tax_amt

    def get_fees_as_tenure(self, hp_type, fee_amt, tot_installemnt):
        ##code are here .....................
        tx_tot = 0.0
        fees_dict = {}
        for line in hp_type.hp_component_ids:
            if line.type == 'fees' and line.tenure == 'tenure':
                amt = round(fee_amt / tot_installemnt, 2)
                amt_fees = amt
                if line.tax_id and amt:
                    tx_tot = self.get_tax_total_incl_exl(line.tax_id, amt)
                if tx_tot:
                    amt_fees = amt_fees - tx_tot
                fees_dict.update({'fees_amt': amt, 'actual_fee': amt, 'tax_amt': tx_tot})
            elif line.type == 'fees' and line.tenure == 'per_year':
                if tot_installemnt >= 1:
                    main_amt = round((fee_amt / 12) * tot_installemnt, 2)
                    if main_amt:
                        amt = main_amt / tot_installemnt
                    amt_fees = amt
                if line.tax_id and amt:
                    tx_tot = self.get_tax_total_incl_exl(line.tax_id, amt)
                if tx_tot:
                    amt_fees = amt_fees - tx_tot
                fees_dict.update({'fees_amt': amt, 'actual_fee': amt, 'tax_amt': tx_tot})
        return fees_dict

    ##getting fees values basis of principle, interest and fees products ................
    def _get_fees_amount(self, hp_type, approve_amt, interest_amt):
        amt = 0.0
        if not hp_type.hp_component_ids:
            return amt
        sum_amt = 0.0
        flag = False
        flag1 = False
        principal_list = []
        interest_list = []
        global_dict = {}
        global_dict1 = {}
        global_dict2 = {}
        internal_dict = {}
        gpi_dict = {}
        cli_dict = {}
        for line in hp_type.hp_component_ids:
            if line.type == 'principal':
                flag = True
                if line.product_id.id not in principal_list:
                    principal_list.append(line.product_id.id)
            if line.type == 'int_rate':
                flag1 = True
                if line.product_id.id not in interest_list:
                    interest_list.append(line.product_id.id)
            if line.type == 'fees':
                if line.product_id.id not in global_dict:
                    global_dict.update({line.product_id.id: line})
            if line.type == 'insurance_fees' and line.insurance_fee_type == 'gpi':
                if line.product_id.id not in global_dict1:
                    global_dict1.update({line.product_id.id: line})
            if line.type == 'insurance_fees' and line.insurance_fee_type == 'cli':
                if line.product_id.id not in global_dict2:
                    global_dict2.update({line.product_id.id: line})

        for line in hp_type.hp_component_ids:
            if line.type == 'fees':
                tx_tot = 0.0
                if line.amount_select == 'percentage':
                    for product in line.amount_percentage_base:
                        sum_amt = 0.0
                        if product.id in principal_list:
                            if line.amount_percentage and flag:
                                percent = line.amount_percentage * line.quantity
                                amt = (approve_amt * percent) / 100
                                sum_amt = sum_amt + amt
                                if line.tax_id:
                                    tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                    sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                sum_amt = 0

                        elif product.id in interest_list:
                            if line.amount_percentage and flag1:
                                percent = line.amount_percentage * line.quantity
                                amt1 = (interest_amt * line.amount_percentage) / 100
                                sum_amt = sum_amt + amt1
                                if line.tax_id:
                                    tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                    sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                sum_amt = 0

                        elif product.id in global_dict:
                            amt_tot = 0.0
                            for o in global_dict[product.id]:
                                if o.amount_select == 'percentage':
                                    if o.product_id.id in internal_dict:
                                        amt_tot = internal_dict[o.product_id.id]
                                elif o.amount_select == 'fix':
                                    amt_tot = internal_dict[o.product_id.id]
                                percent1 = line.amount_percentage * line.quantity
                                amttotal = (amt_tot * percent1) / 100
                                sum_amt = amttotal
                                if line.tax_id:
                                    tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                    sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                sum_amt = 0

                elif line.amount_select == 'fix':
                    fix_amt = line.amount_fix * line.quantity
                    sum_amt = sum_amt + fix_amt
                    if line.tax_id:
                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                    if tx_tot:
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                        sum_amt = sum_amt + tx_tot
                        line.write({'outstanding_product_amt': sum_amt})
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        internal_dict.update({line.product_id.id: sum_amt})
                    else:
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                        internal_dict.update({line.product_id.id: sum_amt})
                    sum_amt = 0

                elif line.amount_select == 'code':
                    sum_amt = self.evaluate_python_code(line.amount_python_compute, approve_amt, interest_amt)
                    if line.tax_id:
                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                    if tx_tot:
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                        sum_amt = sum_amt + tx_tot
                        line.write({'outstanding_product_amt': sum_amt})
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        internal_dict.update({line.product_id.id: sum_amt})
                    else:
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                        internal_dict.update({line.product_id.id: sum_amt})
                    sum_amt = 0

            elif self.is_gpi or self.is_cli:
                if line.type == 'insurance_fees' and line.insurance_fee_type == 'gpi':
                    tx_tot = 0.0
                    if line.amount_select == 'percentage':
                        for product in line.amount_percentage_base:
                            sum_amt = 0.0
                            if product.id in principal_list:
                                if line.amount_percentage and flag:
                                    percent = line.amount_percentage * line.quantity
                                    amt = (approve_amt * percent) / 100
                                    sum_amt = sum_amt + amt
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                            elif product.id in interest_list:
                                if line.amount_percentage and flag1:
                                    percent = line.amount_percentage * line.quantity
                                    amt1 = (interest_amt * line.amount_percentage) / 100
                                    sum_amt = sum_amt + amt1
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                            elif product.id in global_dict1:
                                amt_tot = 0.0
                                for o in global_dict1[product.id]:
                                    if o.amount_select == 'percentage':
                                        if o.product_id.id in gpi_dict:
                                            amt_tot = gpi_dict[o.product_id.id]
                                    elif o.amount_select == 'fix':
                                        amt_tot = gpi_dict[o.product_id.id]
                                    percent1 = line.amount_percentage * line.quantity
                                    amttotal = (amt_tot * percent1) / 100
                                    sum_amt = amttotal
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in gpi_dict:
                                            sum_amt = sum_amt + gpi_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        gpi_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                    elif line.amount_select == 'fix':
                        fix_amt = line.amount_fix * line.quantity
                        sum_amt = sum_amt + fix_amt
                        if line.tax_id:
                            tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                        if tx_tot:
                            line.write(
                                {'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                            line.write({'outstanding_product_amt': sum_amt})
                            if line.product_id.id in gpi_dict:
                                sum_amt = sum_amt + gpi_dict[line.product_id.id]
                            gpi_dict.update({line.product_id.id: sum_amt})
                        else:
                            if line.product_id.id in gpi_dict:
                                sum_amt = sum_amt + gpi_dict[line.product_id.id]
                            line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                            gpi_dict.update({line.product_id.id: sum_amt})
                        sum_amt = 0

                    elif line.amount_select == 'code':
                        sum_amt = self.evaluate_python_code(line.amount_python_compute, approve_amt, interest_amt)
                        if line.tax_id:
                            tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                        if tx_tot:
                            line.write(
                                {'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                            line.write({'outstanding_product_amt': sum_amt})
                            if line.product_id.id in gpi_dict:
                                sum_amt = sum_amt + gpi_dict[line.product_id.id]
                            gpi_dict.update({line.product_id.id: sum_amt})
                        else:
                            if line.product_id.id in gpi_dict:
                                sum_amt = sum_amt + gpi_dict[line.product_id.id]
                            line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                            gpi_dict.update({line.product_id.id: sum_amt})
                        sum_amt = 0

                elif line.type == 'insurance_fees' and line.insurance_fee_type == 'cli':
                    tx_tot = 0.0
                    if line.amount_select == 'percentage':
                        for product in line.amount_percentage_base:
                            sum_amt = 0.0
                            if product.id in principal_list:
                                if line.amount_percentage and flag:
                                    percent = line.amount_percentage * line.quantity
                                    amt = (approve_amt * percent) / 100
                                    sum_amt = sum_amt + amt
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                            elif product.id in interest_list:
                                if line.amount_percentage and flag1:
                                    percent = line.amount_percentage * line.quantity
                                    amt1 = (interest_amt * line.amount_percentage) / 100
                                    sum_amt = sum_amt + amt1
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                            elif product.id in global_dict2:
                                amt_tot = 0.0
                                for o in global_dict2[product.id]:
                                    if o.amount_select == 'percentage':
                                        if o.product_id.id in cli_dict:
                                            amt_tot = cli_dict[o.product_id.id]
                                    elif o.amount_select == 'fix':
                                        amt_tot = cli_dict[o.product_id.id]
                                    percent1 = line.amount_percentage * line.quantity
                                    amttotal = (amt_tot * percent1) / 100
                                    sum_amt = amttotal
                                    if line.tax_id:
                                        tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                                    if tx_tot:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                        line.write({'outstanding_product_amt': sum_amt})
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    else:
                                        if line.product_id.id in cli_dict:
                                            sum_amt = sum_amt + cli_dict[line.product_id.id]
                                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                        cli_dict.update({line.product_id.id: sum_amt})
                                    sum_amt = 0

                    elif line.amount_select == 'fix':
                        fix_amt = line.amount_fix * line.quantity
                        sum_amt = sum_amt + fix_amt
                        if line.tax_id:
                            tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                        if tx_tot:
                            line.write(
                                {'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                            line.write({'outstanding_product_amt': sum_amt})
                            if line.product_id.id in cli_dict:
                                sum_amt = sum_amt + cli_dict[line.product_id.id]
                            cli_dict.update({line.product_id.id: sum_amt})
                        else:
                            if line.product_id.id in cli_dict:
                                sum_amt = sum_amt + cli_dict[line.product_id.id]
                            line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                            cli_dict.update({line.product_id.id: sum_amt})
                        sum_amt = 0

                    elif line.amount_select == 'code':
                        sum_amt = self.evaluate_python_code(line.amount_python_compute, approve_amt, interest_amt)
                        if line.tax_id:
                            tx_tot = self.get_tax_total(line.tax_id, sum_amt)
                        if tx_tot:
                            line.write(
                                {'product_amt': sum_amt, 'outstanding_product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                            line.write({'outstanding_product_amt': sum_amt})
                            if line.product_id.id in cli_dict:
                                sum_amt = sum_amt + cli_dict[line.product_id.id]
                            cli_dict.update({line.product_id.id: sum_amt})
                        else:
                            if line.product_id.id in cli_dict:
                                sum_amt = sum_amt + cli_dict[line.product_id.id]
                            line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                            cli_dict.update({line.product_id.id: sum_amt})
                        sum_amt = 0

        total_fee = sum(internal_dict.values())
        total_gpi = sum(gpi_dict.values())
        total_cli = sum(cli_dict.values())
        dict = {'total_fee': total_fee, 'total_gpi': total_gpi, 'total_cli': total_cli}
        return dict

    ##python code for execute expressions.............
    def evaluate_python_code(self, pycode=None, approve_amt=None, interest_amt=None):
        '''
            This function will calculate/evaluavate the python code in Loan Component Lines.
            @params :
            @returns : total
        '''
        try:
            if pycode and approve_amt and interest_amt:
                localdict = {'approve_amt': approve_amt, 'result': 0.0, 'interest_amt': interest_amt}
                safe_eval(pycode, localdict, mode="exec", nocopy=True)
                return localdict['result'] or 0.0
            else:
                return 0.0
        except Exception as e:
            return 0.0

    def check_date(self,date_update,new_day,present_month):
        if int(present_month) == 2:
            if int(date_update.year)%4 == 0:
                date_update = date_update.replace(day = 29,month = present_month)
            else:
                date_update = date_update.replace(day = 28,month = present_month)
        elif int(present_month) in [4,6,9,11] and new_day > 30:
            date_update = date_update.replace(day = 30,month = present_month)
        else:
            date_update = date_update.replace(day = new_day,month = present_month)
        return date_update

    def calculate_for_flat(self,num, date_update, disbursed_amt, total_installment, part_id):
        capital = round(disbursed_amt / float(total_installment),2)
        interest = round(((disbursed_amt / 100 * self.interest_rate)*(float(total_installment)/12.0))/float(total_installment),2)
        vals = {'name':'installment'+str(num), 'date':date_update,
                'hp_id':self.id, 'capital':capital,
                'interest':interest, 'total':capital+interest,
                'partner_id':part_id,'outstanding_prin':capital,'outstanding_int':interest,}
        return vals

    def calculate_for_constant_prin(self,num, date_update, disbursed_amt, total_amt, total_installment, part_id):
        capital = round(disbursed_amt / float(total_installment),2)
        interest = round(total_amt * self.interest_rate / 100)
        vals = {'name':'installment'+str(num), 'date':date_update,
                'hp_id':self.id, 'capital':capital,
                'interest':interest, 'total':capital+interest,
                'partner_id':part_id,'outstanding_prin':capital,'outstanding_int':interest,}
        return vals

    def _partial_by_disbursed(self, inter_rate, disbursed_amt=0.0, total_installment=0, actual_disbursed_amt=0.0,
                              disburse_date=False, currency_id=False):
        if not self.repayment_basis == 'sanctioned_amt':
            hp = self.read()
            installment_cr = self.env['account.hp.installment']
            if not self.partner_id:
                raise exceptions.except_orm(_('Field Required'), _('Please select Customer.'))

            part_id = self.partner_id.id
            int_rate = 0.0
            inter_sed = self.hp_type
            if inter_sed:
                inter_cal_type = inter_sed.calculation
                if inter_cal_type:
                    if inter_cal_type == 'flat':
                        if self.hp_amt > 0.0 and self.total_installment > 0:
                            pass
                    elif inter_cal_type == 'reducing':
                        int_rate = inter_rate

            rate_interest = int_rate / 100
            total = disbursed_amt
            install_list = []
            check_list = []
            try:
                installment = round(
                    ((total * (rate_interest / 12)) / (1 - ((1 + rate_interest / 12) ** -(total_installment)))))
            except ZeroDivisionError:
                installment = 0
            i = 1
            j = 1
            interest = 0
            date_update = disburse_date
            date_new = date.today()
            new_day = int(date_update.day)
            present_month = date_update.month
            cnt = 0
            remain_amount = 0.0
            numbering = 1
            if self._context.get('is_extended'):
                to_be_deleted = installment_cr.search([('state', '=', 'draft'), ('hp_id', '=', self.id)])
                to_be_deleted.unlink()
            for num in self.installment_id:
                numbering += 1
            remain_amount = 0.0
            for i in range(numbering, self.total_installment + 1):
                if self.hp_type.calculation == 'reducing':
                    interest_month = round(((total * rate_interest) / 12), 2)
                    principle_amount = round(installment - interest_month, 2)
                    remain_amount = round(total - principle_amount, 2)
                    present_month += 1
                    if present_month > 12:
                        present_month = 1;
                        s = date_update.year + 1
                        date_update = date_update.replace(year=s);
                    if new_day > 28:
                        date_update = self.check_date(date_update, new_day, present_month)
                    date_update = date_update.replace(month=present_month);

                    installment_vals = {'name': 'installment' + str(i), 'date': date_update, \
                                        'hp_id': self.id, 'capital': principle_amount, \
                                        'interest': interest_month, 'total': principle_amount + interest_month,
                                        'partner_id': part_id, \
                                        'outstanding_prin': principle_amount, 'outstanding_int': interest_month, }
                elif self.hp_type.calculation == 'flat':
                    present_month += 1
                    if present_month > 12:
                        present_month = 1;
                        s = date_update.year + 1
                        date_update = date_update.replace(year=s);
                    if new_day > 28:
                        date_update = self.check_date(date_update, new_day, present_month)
                    date_update = date_update.replace(month=present_month);

                    installment_vals = self.calculate_for_flat(i, date_update, disbursed_amt, total_installment,
                                                               part_id)
                    interest_month = installment_vals['interest']
                else:
                    present_month += 1
                    if present_month > 12:
                        present_month = 1;
                        s = date_update.year + 1
                        date_update = date_update.replace(year=s);
                    if new_day > 28:
                        date_update = self.check_date(date_update, new_day, present_month)
                    date_update = date_update.replace(month=present_month);

                    installment_vals = self.calculate_for_constant_prin(i, date_update, disbursed_amt, total,
                                                                        total_installment, part_id)
                    remain_amount = round(total - installment_vals['capital'], 2)
                    interest_month = installment_vals['interest']

                install_id = installment_cr.create(installment_vals)
                install_list.append(install_id)
                total = remain_amount
                interest += interest_month
            if total and self.installment_id:
                self.get_rounding_amt(total, self.installment_id[-1])
            fees_vals = {}
            gpi_vals = {}
            cli_vals = {}
            fees_amt = self._get_fees_amount(self.hp_type, disbursed_amt, interest)
            if fees_amt:
                for fees_line in self.hp_type.hp_component_ids:
                    if fees_line.type == 'fees':
                        if fees_line.tenure in ['tenure', 'per_year']:
                            fees_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_fee'],
                                                                total_installment)
                        elif fees_line.tenure == 'month':
                            fees_vals.update({'fees_amt': fees_amt['total_fee']})
                    if fees_line.type == 'insurance_fees' and fees_line.insurance_fee_type == 'gpi':
                        if fees_line.tenure in ['tenure', 'per_year']:
                            gpi_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_gpi'], total_installment)
                        elif fees_line.tenure == 'month':
                            gpi_vals.update({'fees_amt': fees_amt['total_gpi']})
                    if fees_line.type == 'insurance_fees' and fees_line.insurance_fee_type == 'cli':
                        if fees_line.tenure in ['tenure', 'per_year']:
                            cli_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_insurance'],
                                                               total_installment)
                        elif fees_line.tenure == 'month':
                            cli_vals.update({'fees_amt': fees_amt['total_insurance']})

            for line in install_list:
                total_amt = 0.0
                vals_fee = {}
                if 'fees_amt' in fees_vals:
                    total_amt = round(fees_vals['fees_amt'] + line.total, 2)
                    line.write(
                        {'fees': fees_vals['fees_amt'], 'total': total_amt, 'outstanding_fees': fees_vals['fees_amt']})
                if 'fees_amt' in gpi_vals and self.is_gpi:
                    total_amt = round(gpi_vals['fees_amt'] + line.total, 2)
                    line.write(
                        {'gli': gpi_vals['fees_amt'], 'total': total_amt, 'outstanding_fees': gpi_vals['fees_amt']})
                if 'fees_amt' in cli_vals and self.is_cli:
                    total_amt = round(cli_vals['fees_amt'] + line.total, 2)
                    line.write(
                        {'gli': cli_vals['fees_amt'], 'total': total_amt, 'outstanding_fees': cli_vals['fees_amt']})

                for fees_line in line.hp_id.hp_type.hp_component_ids:
                    if fees_line.type == 'fees' and fees_line.tenure == 'tenure':
                        vals_fee.update({'installment_id': line.id,
                                         'product_id': fees_line.product_id.id,
                                         'name': fees_line.type,
                                         })

                        if 'actual_fee' in fees_vals:
                            vals_fee.update({'base': fees_vals['actual_fee']})

                        if fees_line.tax_id and 'tax_amt' in fees_vals:
                            if 'base' in vals_fee:
                                vals_fee.update({'base': fees_vals['actual_fee'] + fees_vals['tax_amt']})

                        if vals_fee:
                            self.env['fees.lines'].create(vals_fee)
                    elif fees_line.type == 'fees' and fees_line.tenure == 'month':
                        vals_fee.update({'installment_id': line.id,
                                         'product_id': fees_line.product_id.id,
                                         'name': fees_line.type,
                                         'base': fees_line.product_amt + fees_line.tax_amount, })
                        if vals_fee:
                            self.env['fees.lines'].create(vals_fee)
            if self.payment_freq == 'daily':
                self._get_daily_calculation()
            elif self.payment_freq == 'weekly':
                self._get_weekly_calculation()
            elif self.payment_freq == 'bi_month':
                self._get_bymonth_calculation()
            elif self.payment_freq == 'quarterly':
                self._get_calculation_quarterly()
            elif self.payment_freq == 'monthly':
                self._get_calculation_monthly()
            elif self.payment_freq == 'half_yearly':
                self._get_half_yearly()
            else:
                self._get_yearly()

    def _get_simple_int_by_existed_disbursed(self, inter_rate, disbursed_amt = 0.0, disburse_date=False, currency_id = False):
        disburse_date = disburse_date
        count = 0
        installment_day = False
        sum_of_paid = main_prin_total = 0.0
        counter_list = []
        max_date = []
        if not self.repayment_basis == 'sanctioned_amt':
            for line in self.installment_id:
                if line.state in ['paid','open']:
                    count = count + 1
                    if line.is_paid_installment == False:
                        counter_list.append(line)
                    max_date.append(line.date)
                else:
                    if line.state not in ['open','paid']:
                        if line.hp_id.cheque_ids:
                            line.hp_id.cheque_ids.unlink()
                        line.unlink()
            if max_date:
                final_date = max(max_date)
                if final_date and disburse_date < final_date:
                    raise UserError(_('Please specify Disbursed Date greater than %s' % final_date))

            for l in counter_list:
                main_prin_total = main_prin_total + l.capital
                sum_of_paid = sum_of_paid + l.outstanding_prin
                if l.state == 'open':
                    l.capital = l.capital - l.outstanding_prin
                    l.outstanding_prin = 0.0

                l.write({'is_paid_installment':True})
                date_of_lines = l.date
                installment_day = date_of_lines.day

        sum_of_paid = main_prin_total - sum_of_paid
        differ = self.old_disburse_amt - sum_of_paid
        new_disburse = differ + disbursed_amt
        if self._context.get('is_extended'):
            new_disburse = differ
            disbursed_amt = 0
        total_installment =  self.total_installment - count
        self.write({'old_disburse_amt':new_disburse})
        if installment_day:
            disburse_date = disburse_date.replace(day = installment_day)

    def _simple_interest_get_by_disbursed(self, inter_rate, disbursed_amt=0.0, disburse_date=False, currency_id=False):
        installment_cr = self.env['account.hp.installment']
        if not self.partner_id:
            raise exceptions.except_orm(_('Field Required'), _('Please select Customer.'))
        int_rate = 0.0
        if self.hp_type and self.hp_type.calculation == 'reducing':
            int_rate = inter_rate
        rate_interest = int_rate / 100
        if self.repayment_basis == 'sanctioned_amt':
            if self._context.get('is_extended'):
                draft_installment = installment_cr.search([('state', '=', 'draft'), ('hp_id', '=', self.id)])
                draft_installment.unlink()
                for line in self.installment_id:
                    self.hp_amount -= line.capital
            total = self.hp_amount
            pr_total = self.hp_amount
            main_tot = self.hp_amount
        else:
            total = disbursed_amt
            pr_total = disbursed_amt
            main_tot = disbursed_amt

        ##changes according to grace period of component lines.===========================================
        gp_int = 0
        gp_principal = 0
        gp_fee = 0
        gp_insurance = 0
        lst_gp = []
        global_dict = {}
        key_min = None
        flag = True
        el_flag = True
        grc_installment = 0.0

        for hp_com_line in self.hp_type.hp_component_ids:
            if hp_com_line.type == 'principal':
                gp_principal = hp_com_line.grace_period
                global_dict.update({'principal': gp_principal})
                lst_gp.append(hp_com_line.grace_period)
            if hp_com_line.type == 'int_rate':
                gp_int = hp_com_line.grace_period
                global_dict.update({'int_rate': gp_int})
                lst_gp.append(hp_com_line.grace_period)
            if hp_com_line.type == 'fees':
                gp_fee = hp_com_line.grace_period
                global_dict.update({'fees': gp_fee})
                lst_gp.append(hp_com_line.grace_period)
            if hp_com_line.type == 'insurance_fees':
                gp_insurance = hp_com_line.grace_period
                global_dict.update({'insurance_fees': gp_insurance})
                lst_gp.append(hp_com_line.grace_period)

        if lst_gp and gp_fee == gp_int == gp_principal:
            total_installment = self.total_installment - (min(lst_gp))
            grc_installment = self.total_installment - total_installment

        total_installment = self.total_installment - len(self.installment_id) - (min(lst_gp if lst_gp else [0]))
        grc_install = self.total_installment - total_installment

        if gp_fee == gp_int == gp_principal:
            try:
                installment = round(
                    ((total * (rate_interest / 12)) / (1 - ((1 + rate_interest / 12) ** -(total_installment if (gp_fee == gp_int == gp_principal) else self.total_installment)))))
            except ZeroDivisionError:
                installment = 0

        i = 1
        inst_num = len(self.installment_id)
        interest =0
        tot_grc_int = tot_grc_capital = sum_of_inst = 0.0
        cnt_fees_flag = False
        date_update = disburse_date

        present_month = (date_update.month + min(lst_gp)) if lst_gp else date_update.month
        key_min = min(global_dict, key=lambda k: global_dict[k]) if lst_gp else None

        cnt = min(lst_gp) if lst_gp else 0
        count_grace_line = 0
        numbering = 1
        for num in self.installment_id:
            numbering += 1
        remaining_instalment = self.total_installment + 1 - numbering
        for i in range(numbering, self.total_installment + 1):
            grace_int = round(((main_tot * rate_interest) / 12), 2)
            principle_amount = 0.0
            interest_month = 0.0
            is_capital_pay = False
            int_for_prin = round(((total * rate_interest) / 12), 2)
            if not total_installment:
                raise Warning(
                    'Please Check grace periods in the HP component lines total installment and grace period should not be same.')
            interest = round(((100000 / 100 * self.interest_rate) * (float(total_installment) / 12.0)) / float(total_installment), 2)
            if gp_fee == gp_int == gp_principal:
                if self.hp_type.calculation == 'flat':
                    if self.repayment_basis == 'sanctioned_amt':
                        capital = round(self.hp_amount / float(remaining_instalment - global_dict.get('principal')), 2)
                        interest = round(((self.hp_amount / 100 * self.interest_rate) * (
                                    float(self.total_installment) / 12.0)) / float(self.total_installment), 2)
                    else:
                        capital = round(disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)
                        interest = round(((disbursed_amt / 100 * self.interest_rate) * (
                                    float(self.total_installment) / 12.0)) / float(self.total_installment), 2)
                elif self.hp_type.calculation == 'reducing':
                    interest_month = round(((total * rate_interest) / 12), 2)
                    principle_amount = round(installment - interest_month, 2)
                else:
                    if self.repayment_basis == 'sanctioned_amt':
                        capital = round(self.hp_amount / float(remaining_instalment - global_dict.get('principal')), 2)
                        interest = round(total * self.interest_rate / 100)
                    else:
                        capital = round(disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)
                        interest = round(total * self.interest_rate / 100)

                if i <= grc_installment:
                    principle_amount = 0.0
                    if self.hp_type.calculation == 'flat':
                        tot_grc_capital = tot_grc_capital + capital
                        tot_grc_int = tot_grc_int + interest
                    elif self.hp_type.calculation == 'reducing':
                        tot_grc_capital = tot_grc_capital + principle_amount
                        tot_grc_int = tot_grc_int + interest_month
                        remain_amount = round(total - principle_amount, 2)
                        total = remain_amount
                    else:
                        remain_amount = round(total - capital, 2)
                        total = remain_amount
                    continue
                inst_num = inst_num + 1
            else:
                cnt_fees_flag = True
                ## for interest calculations .............................
                if key_min == 'int_rate':
                    if self.hp_type.calculation == 'flat':
                        if self.repayment_basis == 'sanctioned_amt':
                            interest = round(((self.hp_amount / 100 * self.interest_rate) * (
                                        float(total_installment) / 12.0)) / float(total_installment), 2)
                        else:
                            interest = round(((disbursed_amt / 100 * self.interest_rate) * (
                                        float(total_installment) / 12.0)) / float(total_installment), 2)
                    elif self.hp_type.calculation == 'reducing':
                        interest_month = round(((total * rate_interest) / 12), 2)
                    else:
                        interest = round(total * self.interest_rate / 100)

                elif cnt >= global_dict.get('int_rate'):
                    if self.hp_type.calculation == 'flat':
                        if self.repayment_basis == 'sanctioned_amt':
                            interest = round(((self.hp_amount / 100 * self.interest_rate) * (
                                        float(total_installment) / 12.0)) / float(total_installment), 2)
                        else:
                            interest = round(((disbursed_amt / 100 * self.interest_rate) * (
                                        float(total_installment) / 12.0)) / float(total_installment), 2)
                    elif self.hp_type.calculation == 'reducing':
                        interest_month = round(((total * rate_interest) / 12), 2)
                    else:
                        interest = round(total * self.interest_rate / 100)
                else:
                    interest_month = 0.0
                    interest = 0.0

                ## for principal calculations .............................
                if key_min == 'principal':
                    if self.hp_type.calculation == 'flat':
                        if self.repayment_basis == 'sanctioned_amt':
                            capital = round(self.hp_amount / float(self.total_installment - global_dict.get('principal')), 2)
                        else:
                            capital = round(disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)
                    elif self.hp_type.calculation == 'reducing':
                        principle_amount = round(installment - int_for_prin, 2)
                    else:
                        if self.repayment_basis == 'sanctioned_amt':
                            capital = round(self.hp_amount / float(self.total_installment - global_dict.get('principal')), 2)
                        else:
                            capital = round(disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)

                elif cnt >= global_dict.get('principal'):
                    tot_inst = self.total_installment - i
                    if self.hp_type.calculation == 'flat':
                        if flag:
                            flag = False
                            if self.repayment_basis == 'sanctioned_amt':
                                capital = round(self.hp_amount / float(self.total_installment - global_dict.get('principal')), 2)
                            else:
                                capital = round(disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)
                    elif self.hp_type.calculation == 'reducing':
                        if flag:
                            flag = False
                            installment = self.get_intstallments(pr_total, rate_interest, tot_inst + 1)
                            int_month = round(((pr_total * rate_interest) / 12), 2)
                        principle_amount = round(installment - int_for_prin, 2)
                    else:
                        if self.repayment_basis == 'sanctioned_amt':
                            capital = round(self.hp_amount / float(self.total_installment - global_dict.get('principal')), 2)
                        else:
                            capital = round(
                                disbursed_amt / float(self.total_installment - global_dict.get('principal')), 2)
                else:
                    principle_amount = 0.0
                    capital = 0.0
                if i <= grc_install:
                    if self.hp_type.calculation == 'flat':
                        tot_grc_capital = tot_grc_capital + capital
                        tot_grc_int = tot_grc_int + interest
                    elif self.hp_type.calculation == 'reducing':
                        tot_grc_capital = tot_grc_capital + principle_amount
                        tot_grc_int = tot_grc_int + interest_month
                        remain_amount = round(total - principle_amount, 2)
                        total = remain_amount
                    else:
                        remain_amount = round(total - capital, 2)
                        total = remain_amount
                        is_capital_pay = True
                    continue

                inst_num = inst_num + 1

            present_month += 1
            if present_month > 12:
                present_month = present_month - 12;
                s = date_update.year + 1
                date_update = date_update.replace(year=s);
            if int(date_update.day) > 28:
                date_update = self.check_date(date_update, int(date_update.day), present_month)
            date_update = date_update.replace(month=present_month);
            installment_vals = {}

            if self.hp_type.calculation == 'reducing':
                remain_amount = round(total - principle_amount, 2)
                sum_of_inst = sum_of_inst + principle_amount
                if principle_amount <= 0:
                    count_grace_line = 0
                    installment_vals = {'name': 'installment' + str(inst_num), \
                                        'date': date_update, 'hp_id': self.id, \
                                        'capital': principle_amount, 'interest': grace_int, \
                                        'total': principle_amount + interest_month, 'partner_id': self.partner_id.id, \
                                        'outstanding_prin': principle_amount, 'outstanding_int': grace_int, \
                                        }
                else:
                    count_grace_line += 1
                    if count_grace_line == 1:
                        installment_vals = {'name': 'installment' + str(inst_num), \
                                            'date': date_update, 'hp_id': self.id, \
                                            'capital': principle_amount, 'interest': grace_int, \
                                            'total': principle_amount + interest_month, 'partner_id': self.partner_id.id, \
                                            'outstanding_prin': principle_amount, 'outstanding_int': grace_int, \
                                            }
                    else:
                        installment_vals = {'name': 'installment' + str(inst_num), \
                                            'date': date_update, 'hp_id': self.id, \
                                            'capital': principle_amount, 'interest': interest_month, \
                                            'total': principle_amount + interest_month, 'partner_id': self.partner_id.id, \
                                            'outstanding_prin': principle_amount, 'outstanding_int': interest_month, \
                                            }
            elif self.hp_type.calculation == 'flat':
                remain_amount = round(total - capital, 2)
                sum_of_inst = sum_of_inst + capital
                installment_vals = {'name': 'installment' + str(inst_num), 'date': date_update,
                                    'hp_id': self.id, 'capital': capital,
                                    'interest': interest, 'total': capital + interest,
                                    'partner_id': self.partner_id.id, 'outstanding_prin': capital,
                                    'outstanding_int': interest, }
                interest_month = installment_vals['interest']
            else:
                if is_capital_pay == False:
                    if total:
                        remain_amount = round(total - capital, 2)
                sum_of_inst = sum_of_inst + capital
                installment_vals = {'name': 'installment' + str(inst_num), 'date': date_update,
                                    'hp_id': self.id, 'capital': capital,
                                    'interest': interest, 'total': capital + interest,
                                    'partner_id': self.partner_id.id, 'outstanding_prin': capital,
                                    'outstanding_int': interest, }
                interest_month = installment_vals['interest']
            installment_cr.create(installment_vals)
            total = remain_amount
            interest += interest_month
            cnt = cnt + 1
        self.write({'interest': interest, 'old_disburse_amt': disbursed_amt, });

        ## Fee calculation .........................
        fees_vals = {}
        gpi_vals = {}
        cli_vals = {}
        if self.repayment_basis == 'sanctioned_amt':
            fees_amt = self._get_fees_amount(self.hp_type, self.hp_amount, interest)
        else:
            fees_amt = self._get_fees_amount(self.hp_type, disbursed_amt, interest)
        if fees_amt:
            for fees_line in self.hp_type.hp_component_ids:
                if fees_line.type == 'fees':
                    if fees_line.tenure in ['tenure', 'per_year']:
                        fees_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_fee'],
                                                            self.total_installment - fees_line.grace_period)
                    elif fees_line.tenure == 'month':
                        fees_vals.update({'fees_amt': fees_amt['total_fee']})
                if fees_line.type == 'insurance_fees' and fees_line.insurance_fee_type == 'gpi':
                    if fees_line.tenure in ['tenure', 'per_year']:
                        gpi_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_gpi'],
                                                           self.total_installment)
                    elif fees_line.tenure == 'month':
                        gpi_vals.update({'fees_amt': fees_amt['total_gpi']})
                if fees_line.type == 'insurance_fees' and fees_line.insurance_fee_type == 'cli':
                    if fees_line.tenure in ['tenure', 'per_year']:
                        cli_vals = self.get_fees_as_tenure(self.hp_type, fees_amt['total_cli'],
                                                           self.total_installment)
                    elif fees_line.tenure == 'month':
                        cli_vals.update({'fees_amt': fees_amt['total_cli']})

        ##grace period principal and interest calculation ................
        grc_cp = 0.0
        grc_int = 0.0
        grc_fees = 0.0
        if total and self.installment_id:
            self.get_rounding_amt(total, self.installment_id[-1])
        if tot_grc_int and grc_installment:
            grc_int = self.get_grace_amount(tot_grc_int, total_installment)
        if tot_grc_int and cnt_fees_flag:
            grc_int = self.get_grace_amount(tot_grc_int, self.total_installment - gp_int)
        # for same grace period to all fees, capital, interest ...................
        if grc_installment:
            if 'fees_amt' in fees_vals and fees_vals['fees_amt']:
                grc_fees = fees_vals.get('fees_amt') * grc_installment
            if grc_fees:
                grc_fees = self.get_grace_amount(grc_fees, total_installment)
        ## for random grace period to all fees, capital, interest ...................
        if cnt_fees_flag:
            if 'fees_amt' in fees_vals and fees_vals['fees_amt']:
                if min(lst_gp) == 0 and gp_fee != 0:
                    grc_fees = fees_vals.get('fees_amt') * gp_fee
                    if grc_fees:
                        grc_fees = self.get_grace_amount(grc_fees, self.total_installment - gp_fee)
        if grc_cp or grc_int:
            for ins_line in self.installment_id:
                if ins_line.capital:
                    ins_line.capital = (ins_line.capital + grc_cp)
                    ins_line.total = ins_line.total + grc_cp
                if ins_line.interest:
                    ins_line.interest = (ins_line.interest + grc_int)
                    ins_line.total = ins_line.total + grc_int
                if ins_line.outstanding_prin:
                    ins_line.outstanding_prin = (ins_line.outstanding_prin + grc_cp)
                if ins_line.outstanding_int:
                    ins_line.outstanding_int = (ins_line.outstanding_int + grc_int)

        ## fee updating in installment line level ...................
        gp_fee_cnt = min(lst_gp) if lst_gp else 0
        is_updated_fees = False
        is_updated_insurance = False
        for line in self.installment_id:
            if line.state in ['open', 'paid']:
                continue
            total_amt = 0.0
            vals_fee = {}
            if gp_fee == gp_int == gp_principal:
                is_updated_fees = True
                if 'fees_amt' in fees_vals:
                    total_amt = fees_vals['fees_amt'] + line.total + grc_fees
                    line.write({'fees': fees_vals['fees_amt'] + grc_fees,
                                'outstanding_fees': fees_vals['fees_amt'] + grc_fees, 'total': total_amt})
            else:
                if key_min == 'fees':
                    is_updated_fees = True
                    if 'fees_amt' in fees_vals:
                        total_amt = fees_vals['fees_amt'] + line.total + grc_fees
                        line.write({'fees': fees_vals['fees_amt'] + grc_fees,
                                    'outstanding_fees': fees_vals['fees_amt'] + grc_fees, 'total': total_amt})
                elif gp_fee_cnt >= global_dict.get('fees'):
                    is_updated_fees = True
                    if 'fees_amt' in fees_vals:
                        total_amt = fees_vals['fees_amt'] + line.total + grc_fees
                        line.write({'fees': fees_vals['fees_amt'] + grc_fees,
                                    'outstanding_fees': fees_vals['fees_amt'] + grc_fees, 'total': total_amt})
            if is_updated_fees:
                for fees_line in line.hp_id.hp_type.hp_component_ids:
                    if fees_line.type == 'fees' and fees_line.tenure == 'month':
                        vals_fee.update({'installment_id': line.id,
                                         'product_id': fees_line.product_id.id,
                                         'name': fees_line.type,
                                         'base': (fees_line.product_amt + fees_line.tax_amount + grc_fees), })
                        if vals_fee:
                            self.env['fees.lines'].create(vals_fee)
                    elif fees_line.type == 'fees' and fees_line.tenure == 'tenure':
                        vals_fee.update({'installment_id': line.id,
                                         'product_id': fees_line.product_id.id,
                                         'name': fees_line.type,
                                         })

                        if 'actual_fee' in fees_vals:
                            vals_fee.update({'base': (fees_vals['actual_fee'] + grc_fees)})
                        if vals_fee:
                            self.env['fees.lines'].create(vals_fee)

                    elif fees_line.type == 'fees' and fees_line.tenure == 'per_year':
                        vals_fee.update({'installment_id': line.id,
                                         'product_id': fees_line.product_id.id,
                                         'name': fees_line.type,
                                         })

                        if 'actual_fee' in fees_vals:
                            vals_fee.update({'base': (fees_vals['actual_fee'] + grc_fees)})
                        if vals_fee:
                            self.env['fees.lines'].create(vals_fee)

            for insurance_line in self.hp_type.hp_component_ids:
                if insurance_line.type == 'insurance_fees' and insurance_line.insurance_fee_type == 'gpi' and self.is_gpi:
                    if 'fees_amt' in gpi_vals:
                        total_amt = gpi_vals['fees_amt'] + line.total
                    line.write(
                        {'gpi': gpi_vals['fees_amt'], 'outstanding_gpi': gpi_vals['fees_amt'],
                         'total': total_amt})

                elif insurance_line.type == 'insurance_fees' and insurance_line.insurance_fee_type == 'cli' and self.is_cli:
                    if 'fees_amt' in cli_vals:
                        total_amt = cli_vals['fees_amt'] + line.total
                    line.write(
                        {'cli': cli_vals['fees_amt'], 'outstanding_cli': cli_vals['fees_amt'],
                         'total': total_amt})
            gp_fee_cnt = gp_fee_cnt + 1

        ## line installment using by Payment Frequency.........................
        if self.payment_freq == 'daily':
            self._get_daily_calculation()
        elif self.payment_freq == 'weekly':
            self._get_weekly_calculation()
        elif self.payment_freq == 'bi_month':
            self._get_bymonth_calculation()
        elif self.payment_freq == 'quarterly':
            self._get_calculation_quarterly()
        elif self.payment_freq == 'monthly':
            self._get_calculation_monthly()
        elif self.payment_freq == 'half_yearly':
            self._get_half_yearly()
        else:
            self._get_yearly()

    ## yearly calcultion ..................
    def _get_yearly(self):
        cnt = 0
        inst = 'installment'
        cnt1 = 1
        principal = interest = fees = gpi = cli = 0.0
        installment_ids = []
        vals = {}
        inst_list = []
        if (len(self.installment_id) % 12) != 0:
            raise UserError(_('You can not apply for yearly basis hp. Please check no. of installments.'))
        if self.payment_schedule_ids:
            self.payment_schedule_ids.unlink()
        for line in self.installment_id:
            principal = round(principal + line.capital, 2)
            interest = round(interest + line.interest, 2)
            fees = round(fees + line.fees, 2)
            gpi = round(gpi + line.gpi, 2)
            cli = round(cli + line.cli, 2)
            installment_ids.append(line)
            inst_list.append(line.id)
            if cnt == 11:
                date_update = line.date
                total = round(principal + interest + fees + gpi + cli, 2)
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': date_update, 'installment_id': [(6, 0, inst_list)], 'hp_id': self.id})
                inst_list = []
                self.env['payment.schedule.line'].create(vals)
                vals = {}
                vals1 = {}
                principal = interest = fees = 0.0
                cnt1 = cnt1 + 1
                cnt = 0
            else:
                cnt = cnt + 1

    ## half yearly calculation ...........................
    def _get_half_yearly(self):
        cnt = 0
        inst = 'installment'
        cnt1 = 1
        principal = interest = fees = gpi = cli = 0.0
        installment_ids = []
        vals = {}
        inst_list = []
        if self.payment_schedule_ids:
            self.payment_schedule_ids.unlink()
        if (len(self.installment_id) % 6) != 0:
            raise UserError(_('You can not apply for half yearly hp. Please check no. of installments.'))
        for line in self.installment_id:
            principal = principal + line.capital
            interest = interest + line.interest
            fees = fees + line.fees
            gpi = gpi + line.gpi
            cli = cli + line.cli
            installment_ids.append(line)
            inst_list.append(line.id)
            if cnt == 5:
                date_update = line.date
                total = principal + interest + fees + gpi + cli
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': date_update, 'installment_id': [(6, 0, inst_list)]})
                inst_list = []
                vals.update({'hp_id': self.id})
                self.env['payment.schedule.line'].create(vals)
                vals = {}
                principal = interest = fees = 0.0
                cnt1 = cnt1 + 1
                cnt = 0
            else:
                cnt = cnt + 1

    ##monthly calculation .........................
    def _get_calculation_monthly(self):
        cnt1 = 1
        if self.payment_schedule_ids:
            self.payment_schedule_ids.unlink()
        for line in self.installment_id:
            vals = {'name': line.name, 'capital': line.capital, \
                    'interest': line.interest, 'fees': line.fees, 'gpi': line.gpi, 'cli': line.cli, 'total': line.total, \
                    'date': line.date, 'installment_id': [(6, 0, [line.id])], 'hp_id': self.id}
            self.env['payment.schedule.line'].create(vals)
            cnt1 = cnt1 + 1

    ## Daily basis calculation ...................
    def _get_daily_calculation(self):
        inst = 'installment'
        principal = interest = fees = gpi = cli =0.0
        cnt = 0
        for line in self.installment_id:
            vals = {}
            inst_list = []
            total = 0.0
            if line.date:
                back_date = line.date - relativedelta(months=1)
                tot_days = (line.date - back_date).days
                principal = line.capital / tot_days
                interest = line.interest / tot_days
                fees = line.fees / tot_days
                gpi = line.gpi / tot_days
                cli = line.cpi / tot_days
                total = principal + interest + fees + gpi + cli
                inst_list.append(line.id)
                back_date = back_date + relativedelta(days=1)
                for dline in range(tot_days):
                    cnt = cnt + 1
                    vals.update({'name': inst + str(cnt), 'capital': principal, \
                                 'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                                 'date': back_date, 'hp_id': self.id, 'installment_id': [(6, 0, inst_list)]})
                    self.env['payment.schedule.line'].create(vals)
                    back_date = back_date + relativedelta(days=1)
        return True

    ## Weekly basis calculation ...................
    def _get_weekly_calculation(self):
        self._get_daily_calculation()
        inst = 'installment'
        principal = interest = fees = gpi = cli = 0.0
        vals = {}
        cnt = cnt1 = count = 0
        list_vals = []
        py_line_len = len(self.payment_schedule_ids)
        for py_schule_line in self.payment_schedule_ids:
            principal = principal + py_schule_line.capital
            interest = interest + py_schule_line.interest
            fees = fees + py_schule_line.fees
            gpi = gpi + py_schule_line.gpi
            cli = cli + py_schule_line.cli
            total = (principal + interest + fees + gpi + cli)
            inst_list = []
            count += 1
            if py_line_len == count and cnt != 6:
                inst_list.append(py_schule_line.installment_id.id)
                cnt1 += 1
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': py_schule_line.date, 'hp_id': self.id, 'installment_id': [(6, 0, inst_list)]})
                list_vals.append(vals)
            if cnt == 6:
                inst_list.append(py_schule_line.installment_id.id)
                cnt1 += 1
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': py_schule_line.date, 'hp_id': self.id, 'installment_id': [(6, 0, inst_list)]})
                list_vals.append(vals)
                principal = interest = fees = total = 0.0
                vals = {}
                cnt = 0
            else:
                cnt += 1
        if list_vals:
            self.payment_schedule_ids.unlink()
            for line in list_vals:
                self.env['payment.schedule.line'].create(line)
        return True

    ## by monthly basis calculation ...................
    def _get_bymonth_calculation(self):
        self._get_daily_calculation()
        inst = 'installment'
        principal = interest = fees = gpi = cli = 0.0
        cnt = cnt1 = count = 0
        vals = {}
        list_vals = []
        py_line_len = len(self.payment_schedule_ids)
        for py_schule_line in self.payment_schedule_ids:
            principal = principal + py_schule_line.capital
            interest = interest + py_schule_line.interest
            fees = fees + py_schule_line.fees
            gpi = gpi + py_schule_line.gpi
            cli = cli + py_schule_line.cli
            total = (principal + interest + fees + gpi + cli)
            inst_list = []
            count += 1
            if py_line_len == count and cnt != 14:
                inst_list.append(py_schule_line.installment_id.id)
                cnt1 += 1
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': py_schule_line.date, 'hp_id': self.id, 'installment_id': [(6, 0, inst_list)]})
                list_vals.append(vals)
            if cnt == 14:
                inst_list.append(py_schule_line.installment_id.id)
                cnt1 += 1
                vals.update({'name': inst + str(cnt1), 'capital': principal, \
                             'interest': interest, 'fees': fees, 'gpi': gpi, 'cli': cli, 'total': total, \
                             'date': py_schule_line.date, 'hp_id': self.id, 'installment_id': [(6, 0, inst_list)]})
                list_vals.append(vals)
                principal = interest = fees = total = 0.0
                vals = {}
                cnt = 0
            else:
                cnt += 1
        if list_vals:
            self.payment_schedule_ids.unlink()
            for line in list_vals:
                self.env['payment.schedule.line'].create(line)
        return True

    def hp_classification_status(self):
        records = self.search([])
        date = datetime.datetime.now().date()
        for hp in records:
            arrear_day = 0
            for inst in hp.installment_id:
                if inst.date:
                    if inst.date < date and inst.state != 'paid':
                        if not arrear_day:
                            arrear_day = inst.date
            if arrear_day:
                arrear_day = arrear_day
                arrear_day =  date - arrear_day
                arrear_day = arrear_day.days
            classification = None
            if arrear_day > 360:
                classification = self.env['hp.classifications'].search([('min','<=',arrear_day)])
            else:
                classification = self.env['hp.classifications'].search([('min','<=',arrear_day),('max','>=',arrear_day)])
            if classification:
                hp.write({'classification':classification[0].name})

    def hp_due_cron(self):
        records = self.search([])
        for record in records:
            for line in record.installment_id:
                if line.date:
                    if(line.date <= date.today()) and line.state != 'paid':
                        line.due_principal = line.outstanding_prin
                        line.due_interest = line.outstanding_int
                        line.due_fees = line.outstanding_fees
                        line.due_gpi = line.outstanding_gpi
                        line.due_cli = line.outstanding_cli

    ##getting fees values basis of principle, interest and fees products ................
    def _get_late_fees_amount(self, hp_type, approve_amt, interest_amt):
        amt = 0.0
        if not hp_type.hp_component_ids:
            return amt
        sum_amt = global_add1 = global_add2 = global_add3 = global_add4 = 0.0
        flag = flag1 = False
        global_list = []
        principal_list = []
        interest_list = []
        fees_list = []
        lfees_list = []

        global_dict = {}
        global_dict1 = {}
        internal_dict = {}
        for line in hp_type.hp_component_ids:
            if line.type == 'principal':
                flag = True
                if line.product_id.id not in principal_list:
                    principal_list.append(line.product_id.id)
            if line.type == 'int_rate':
                flag1 = True
                if line.product_id.id not in interest_list:
                    global_list.append(line.product_id.id)
                    interest_list.append(line.product_id.id)
            if line.type == 'fees':
                if line.product_id.id not in fees_list:
                    global_list.append(line.product_id.id)
                    fees_list.append(line.product_id.id)
                    global_dict.update({line.product_id.id: line})

            if line.type == 'late_fee':
                if line.product_id.id not in lfees_list:
                    lfees_list.append(line.product_id.id)
                    global_dict1.update({line.product_id.id: line})

        for line in hp_type.hp_component_ids:
            if line.type == 'late_fee':
                tx_tot = 0.0
                if line.amount_select == 'percentage':
                    for product in line.amount_percentage_base:
                        sum_amt = 0.0
                        if product.id in principal_list:
                            if line.amount_percentage and flag:
                                percent = line.amount_percentage * line.quantity
                                amt = (approve_amt * percent) / 100
                                sum_amt = sum_amt + amt
                                if line.tax_id:
                                    tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    if type(tx_tot) == dict:
                                        bse_tx = 0.0
                                        bse_tx = sum_amt - tx_tot.get('include')
                                        line.with_context({'inclsive': bse_tx}).write(
                                            {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                                    else:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                global_add1 = global_add1 + sum_amt
                                sum_amt = 0

                        elif product.id in interest_list:
                            if line.amount_percentage and flag1:
                                percent = line.amount_percentage * line.quantity
                                amt1 = (interest_amt * line.amount_percentage) / 100
                                sum_amt = sum_amt + amt1
                                if line.tax_id:
                                    tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    if type(tx_tot) == dict:
                                        bse_tx = 0.0
                                        bse_tx = sum_amt - tx_tot.get('include')
                                        line.with_context({'inclsive': bse_tx}).write(
                                            {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                                    else:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                global_add2 = global_add2 + sum_amt
                                sum_amt = 0

                        elif product.id in global_dict:
                            amt_tot = 0.0
                            for o in global_dict[product.id]:
                                if o.amount_select == 'percentage':
                                    if o.product_id.id in internal_dict:
                                        amt_tot = internal_dict[o.product_id.id]
                                elif o.amount_select == 'fix':
                                    amt_tot = internal_dict[o.product_id.id]
                                percent1 = line.amount_percentage * line.quantity
                                amttotal = (amt_tot * percent1) / 100
                                sum_amt = amttotal
                                if line.tax_id:
                                    tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    if type(tx_tot) == dict:
                                        bse_tx = 0.0
                                        bse_tx = sum_amt - tx_tot.get('include')
                                        line.with_context({'inclsive': bse_tx}).write(
                                            {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                                    else:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot

                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                global_add3 = global_add3 + sum_amt
                                sum_amt = 0

                        elif product.id in global_dict1:
                            amt_tot = 0.0
                            for o in global_dict1[product.id]:
                                if o.amount_select == 'percentage':
                                    if o.product_id.id in internal_dict:
                                        amt_tot = internal_dict[o.product_id.id]
                                elif o.amount_select == 'fix':
                                    amt_tot = internal_dict[o.product_id.id]
                                percent1 = line.amount_percentage * line.quantity
                                amttotal = (amt_tot * percent1) / 100
                                sum_amt = amttotal
                                if line.tax_id:
                                    tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                                if tx_tot:
                                    if type(tx_tot) == dict:
                                        bse_tx = 0.0
                                        bse_tx = sum_amt - tx_tot.get('include')
                                        line.with_context({'inclsive': bse_tx}).write(
                                            {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                                    else:
                                        line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                                        sum_amt = sum_amt + tx_tot
                                    line.write({'outstanding_product_amt': sum_amt})
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    internal_dict.update({line.product_id.id: sum_amt})
                                else:
                                    if line.product_id.id in internal_dict:
                                        sum_amt = sum_amt + internal_dict[line.product_id.id]
                                    line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                                    internal_dict.update({line.product_id.id: sum_amt})
                                sum_amt = 0

                elif line.amount_select == 'fix':
                    fix_amt = line.amount_fix * line.quantity
                    sum_amt = sum_amt + fix_amt
                    if line.tax_id:
                        tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                    if tx_tot:
                        if type(tx_tot) == dict:
                            bse_tx = 0.0
                            bse_tx = sum_amt - tx_tot.get('include')
                            line.with_context({'inclsive': bse_tx}).write(
                                {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                        else:
                            line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        internal_dict.update({line.product_id.id: sum_amt})
                    else:
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                        internal_dict.update({line.product_id.id: sum_amt})

                    global_add4 = global_add4 + sum_amt
                    sum_amt = 0

                elif line.amount_select == 'code':
                    sum_amt = self.evaluate_python_code(line.amount_python_compute, approve_amt, interest_amt)
                    if line.tax_id:
                        tx_tot = self.get_late_fee_tax_total(line.tax_id, sum_amt)
                    if tx_tot:

                        if type(tx_tot) == dict:
                            bse_tx = 0.0
                            bse_tx = sum_amt - tx_tot.get('include')
                            line.with_context({'inclsive': bse_tx}).write(
                                {'product_amt': bse_tx, 'tax_amount': tx_tot.get('include')})
                        else:
                            line.write({'product_amt': sum_amt, 'tax_amount': tx_tot})
                            sum_amt = sum_amt + tx_tot
                        line.write({'outstanding_product_amt': sum_amt})
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        internal_dict.update({line.product_id.id: sum_amt})
                    else:
                        if line.product_id.id in internal_dict:
                            sum_amt = sum_amt + internal_dict[line.product_id.id]
                        line.write({'product_amt': sum_amt, 'outstanding_product_amt': sum_amt})
                        internal_dict.update({line.product_id.id: sum_amt})
                    sum_amt = 0
        if internal_dict:
            print ('to do list')

        total_all = sum(internal_dict.values())
        return total_all

    def hp_late_fees(self):
        records = self.search([('state', 'in', ['approved', 'partial'])])
        current_date = datetime.date.today()
        vals_fee = {}
        for record in records:
            if record.grace_period:
                for py_line in record.payment_schedule_ids:
                    is_grace_period = False
                    last_record = False
                    for line in py_line.installment_id:
                        if line.state == 'draft':
                            is_grace_period = True
                            last_record = line
                        else:
                            is_grace_period = False
                            last_record = False
                            break
                    if is_grace_period and last_record:
                        total = 0.0
                        date_object = last_record.date
                        delta = current_date - date_object
                        diff = int(delta.days / record.grace_period)
                        if diff > 0:
                            if record.repayment_basis == 'sanctioned_amt':
                                total = self._get_late_fees_amount(record.hp_type, record.hp_amount,
                                                                   record.interest)
                            else:
                                dis_amt = 0.0
                                for line in record.disbursement_details:
                                    dis_amt = dis_amt + line.disbursement_amt

                                if dis_amt > 0.0:
                                    total = self._get_late_fees_amount(record.hp_type, dis_amt, record.interest)

                        if total:
                            for cmp_line in record.hp_type.hp_component_ids:
                                if cmp_line.type == 'late_fee':
                                    search_id = self.env['fees.lines'].search(
                                        [('product_id', '=', cmp_line.product_id.id),
                                         ('installment_id', '=', last_record.id)])
                                    if search_id:
                                        if cmp_line.product_amt:
                                            base_amt = (cmp_line.product_amt * diff)
                                            if cmp_line.tax_amount > 0.0 and cmp_line.tax_id:
                                                base_amt = base_amt + (cmp_line.tax_amount * diff)
                                            search_id.write({'base': base_amt})
                                    else:
                                        vals_fee.update({'installment_id': last_record.id,
                                                         'product_id': cmp_line.product_id.id,
                                                         'name': cmp_line.type,
                                                         'base': cmp_line.product_amt * diff})
                                        if cmp_line.tax_amount > 0.0 and cmp_line.tax_id:
                                            bs_amt = vals_fee['base'] + (cmp_line.tax_amount * diff)
                                            vals_fee.update({'base': bs_amt})
                                        if vals_fee:
                                            self.env['fees.lines'].create(vals_fee)
                            last_record.late_fee = total * diff

    def hp_paid(self):
        for line in self.installment_id:
            if not line.state == 'paid':
                raise UserError(
                    "Warning : This hp application can not be marked as Done as there is some installment amount still pending.")
        # voucher_dict = {
        #     'draft': ['proforma_voucher'],
        #     'proforma': ['proforma_voucher']
        # }
        # voucher_pool = self.env['account.voucher']
        # for this_obj in self:
        #     voucher_obj = this_obj.voucher_id and this_obj.voucher_id or False
        #     voucher_state = voucher_obj and voucher_obj.state or False
        #     if voucher_state and voucher_state in voucher_dict:
        #         for voucher_method in voucher_dict[voucher_state]:
        #             #                     values = this_obj.voucher_id.id
        #             getattr(voucher_pool, voucher_method)
        #
        #     move_id = voucher_obj and [x.id for x in voucher_obj.move_id] or []
        #     if move_id:
        #         self.env['account.move.line'].write({'acc_hp_id': this_obj.id})
        self.date_done = date.today()
        self.write({'state': 'done'})
        return True

    def button_cancel_hp(self):
        is_disburse = False
        is_payment = False
        for disburse_line in self.disbursement_details:
            if disburse_line.release_number and disburse_line.release_number.state != 'post':
                print ('for Disbursement entry cancel')
            if disburse_line.release_number:
                cancel_entry = disburse_line.release_number.button_cancel()
                if cancel_entry:
                    disburse_line.release_number.unlink()
                    disburse_line.unlink()
                    is_disburse = True

        for repayment_line in self.repayment_details:
            if repayment_line.release_number and repayment_line.release_number != 'post':
                print ('For Payment Cancel')
            if repayment_line.release_number:
                py_cancel_entry = repayment_line.release_number.button_cancel()
                if py_cancel_entry:
                    repayment_line.release_number.unlink()
                    repayment_line.unlink()
                    is_payment = True
        self.state = 'cancel'
        return True

    ##manually added fees
    def button_fees_calculation(self):
        ## Fee calculation .........................
        fees_vals = {}
        product_id = False
        late_fee_prodcut = False
        late_tax_id = False
        tax_id = False
        for type_details in self.hp_type.hp_component_ids:
            if type_details.type == 'fees':
                if type_details.product_id:
                    product_id = type_details.product_id.id
                if type_details.tax_id:
                    tax_id = type_details.tax_id
            if type_details.type == 'late_fee':
                if type_details.product_id:
                    late_fee_prodcut = type_details.product_id.id
                if type_details.tax_id:
                    late_tax_id = type_details.tax_id

        for line in self.installment_id:
            fees_vals = {}
            late_fees_vals = {}
            if line.state not in  ['open','paid'] and line.outstanding_fees:
                fees_line_id = self.env['fees.lines'].search([('product_id','=',product_id),('installment_id','=',line.id)], limit=1)
                fees_amt = line.outstanding_fees
                if tax_id:
                    tx_tot = self.get_tax_total_incl_exl(tax_id, line.outstanding_fees)
                    fees_amt = fees_amt - tx_tot
                    fees_vals.update({'tax':tx_tot})
                fees_vals.update({'name':'fees','product_id':product_id, 'base':fees_amt,'installment_id':line.id})

                if not fees_line_id:
                    self.env['fees.lines'].create(fees_vals)

            if line.state not in  ['open','paid'] and line.late_fee:
                late_fees_amt = line.late_fee
                late_fees_line_id = self.env['fees.lines'].search([('product_id','=',late_fee_prodcut),('installment_id','=',line.id)], limit=1)
                if late_tax_id:
                    tx_tot = self.get_tax_total_incl_exl(late_tax_id, line.late_fee)
                    late_fees_amt = late_fees_amt - tx_tot
                    late_fees_vals.update({'tax':tx_tot})
                late_fees_vals.update({'name':'late_fee', 'product_id':late_fee_prodcut, 'base':late_fees_amt,'installment_id':line.id})
                if not late_fees_line_id:
                    self.env['fees.lines'].create(late_fees_vals)
        return True

    def hp_cancel(self):
        self.installment_id.unlink()
        acc_move_line = self.env['account.move.line']
        ac_ids = acc_move_line.search([('acc_hp_id', '=', self.id)]);
        ac_ids.unlink();
        self.write({'state': 'cancel'})
        return True

    def reject_hp(self):
        installment_cr = self.env['account.hp.installment']
        install_ids = installment_cr.search([('hp_id', '=', self.id)])
        for install_id in install_ids:
            install_id.unlink()
        acc_move_line = self.env['account.move.line']
        ac_ids = acc_move_line.search([('acc_hp_id', '=', self.id)])
        for acc_id in ac_ids:
            acc_id.unlink()

        return True

    def add_installment_line(self,offer=False):
        if offer:

            # if self.is_cli:
            #     if len(hp_components):
            #         cli = self.get_fees_as_tenure(self.hp_type,offer.instalment,offer.term)
            #         cli = cli['fee_amt'] or 0.0
            #     else:
            #         cli = fees_amount['total_cli'] or 0.0
            #
            # if self.is_gpi:
            #     if len(hp_components):
            #         gpi = self.get_fees_as_tenure(self.hp_type,offer.instalment,offer.term)
            #         gpi = gpi['fee_amt'] or 0.0
            #     else:
            #         gpi = fees_amount['total_gpi'] or 0.0
            next_date = False
            offer_term = offer.term
            interest_per_installment = offer.interest / offer_term
            cli = self.is_cli and offer.life_insurance_amount or 0.0;
            gpi = self.is_gpi and offer.insurance_amt or 0.0;
            capital = self.hp_amount /offer_term
            initiation_fee = self.initiation_fee / offer_term
            total = (capital + initiation_fee + interest_per_installment + offer.adminfee + gpi + cli)
            for index,installment in enumerate(range(0, int(offer_term))):
                is_feb = next_date and (next_date.month == 2 and next_date.day in [28,29])
                next_date = not next_date and offer.first_instalment_date or next_date + relativedelta(months=+1)
                next_date = is_feb and next_date.replace(day=calendar.monthrange(next_date.year,next_date.month)[1]) or next_date
                values = {
                    'name': 'installment '+ str(index+1),
                    'date': next_date,
                    'hp_id': self.id,
                    'capital': capital,
                    'initiation_fee':initiation_fee,
                    'interest': interest_per_installment,
                    'fees':offer.adminfee,
                    'cli':cli,
                    'gpi':gpi,
                    'total': total,
                    'partner_id': self.partner_id.id,
                    'outstanding_prin': capital,
                    'outstanding_int':interest_per_installment,
                    'outstanding_fees':offer.adminfee,
                    'outstanding_gpi':  gpi,
                    'outstanding_cli':cli,
                }
                self.env['account.hp.installment'].create(values)

    def hp_application_status_cron(self):
        stages = [self.env.ref('hire_purchase.' + x).id for x in ['hp_to_pending', 'hp_to_process']]
        hp_accounts = len(stages) and self.search([('stage_id', 'in', stages)]) or []
        if len(hp_accounts):
            _logger.info(_("Checking HP status for {0}".format(hp_accounts.mapped('display_name'))))
            for hp in hp_accounts:
                try:
                    hp.check_application_status(from_cron=True)
                    _logger.info("Current status for HP: {0} - {1}".format(hp.display_name,hp.stage_id.name))
                except Exception as e:
                   _logger.info("Exception in Checking application Status Cron for HP {0}: {1}".format(hp.display_name,e.name.strip('\n')))
        else:
            _logger.info("No HP accounts found for Pending Documents and Pending Decision stages")

    def hp_application_staus_ntu_cron(self):
            diff_date = datetime.today() - timedelta(days=13)
            hp_accounts = self.search([('state','not in',['approved','cancel','done'])]) or []
            hp_accounts = hp_accounts.filtered(lambda x:diff_date.date() >= x.create_date.date()) or []
            if len(hp_accounts):
                frontier_obj = self.env['frontier.api.calls']
                stage_id = self.env.ref('hire_purchase.hp_to_cancelled_ntu').id
                _logger.info("Checking Application NTU status for following HP :{0}".format(hp_accounts.mapped('display_name')))
                access_token = frontier_obj.login_request().get('access_token',False)
                for hp in hp_accounts:
                    request_data = response = False
                    try:
                        request_data = hp._prepare_application_take_up(status='NotTakenUp',reason='NTU, Not taken up')
                        _logger.info("Checking for status for HP {0} - {1}".format(hp.display_name or hp.name,request_data))
                        if access_token:
                            response = frontier_obj._application_taken_up(body=request_data,access_token=access_token)
                        if response:
                            hp.write({'state':'cancel','stage_id':stage_id,'stage_reason':'NTU, Not taken up'})
                    except Exception as e:
                        _logger.info(
                            "Exception for Cron HP Application {0}: Request Data: {1} and Response: {2}".format(e, response,
                                                                                                                request_data))
            else:
                _logger.info("No HP accounts found for NTU status cron")

    def hp_application_edit(self):
        self.ensure_one()
        frontier_obj = self.env['frontier.api.calls']
        data = self._prepare_hp_application_edit()
        edit_response = frontier_obj._application_edit(body=data)

    def _prepare_hp_application_edit(self,):
        app_nr = self.env['frontier.api.calls'].search([('hp_account_id','=',self.id)]).app_nr
        if not app_nr:
            raise UserError(_("AppNr not found for HP while application edit"))
        if not self.sale_order_id.id:
            raise UserError(_("Order not found for HP while application edit"))
        product_models = []
        for line in self.sale_order_id.order_line or []:
            product_models.append({
                "modelName": line.product_id.name,
                "price": line.price_unit,
                "quantity": line.product_uom_qty,
                "referenceNo": line.product_id.default_code
            })
        return {
            "appNr": app_nr,
            "dealAmt": self.req_amt,
            "totalValueOfGoods": 22000,
            "contractPeriod": self.hp_period.period,
            "depositAmount": self.deposit_amt,
            "productModels":product_models
        }

    def deposit_hp_payment(self):
        sca_proof = self.proof_id.filtered(lambda x:x.type.id == self.env.ref('hire_purchase.hp_proof_sca').id)
        if not sca_proof.id or not sca_proof.upload_status == True:
            raise UserError(_("Please upload the Signed Contract Agreement"))
        view_id = self.env.ref('hire_purchase.deposit_hp_payment_view').id
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'deposit.hp.payment',
            'view_id': view_id,
            'target': 'new',
        }

    def hp_assign_me(self):
        self.ensure_one()
        user = self.env.user
        self.controller_id = user.id
        activites = self.activity_ids.filtered(lambda x:x.user_id.id != user.id)
        if len(activites.ids) and self.controller_id:
            activites.unlink()
            _logger.info("HP {0} assigned to {1} and deleted activtites".format(self.display_name,user.name))

    def send_for_review(self,note=False,summary=False,users=False):
        model_id = self.env['ir.model']._get(self._name).id
        stage = self.env.ref('hire_purchase.hp_to_review').id
        activites = self.env['mail.activity'].search([('res_model_id','=',model_id),('res_id','in',self.ids)])

        if not self.env.user.email:
            raise UserError(_("Please add your email address."))

        customer_photo = self.proof_id.filtered(lambda x:x.type.shortcut == 'PIC')
        if not customer_photo.id:
            raise ValidationError("Please take and upload a photo of the customer to proceed.")
        else:
            self.partner_id.write({'image_1920':customer_photo.attachment_id.datas.decode('utf-8') or False})

        if not note:
            note = """<ul><li>Review application</li>
                            <li>Verify Documents</li>
                            <li>Submit Documents to Frontier</li>
                            <li>Conduct Reference Checks</li>
                        </ul>"""
        if not summary:
            summary = "Review & Submit Documents & Conduct Reference Checks"

        if not users:
            group = self.env.ref('hire_purchase.group_hp_account_controller')
            users = group.id and len(group.users.ids) and group.users or []

        for record in self:
            try:
                mail_ids = []
                for user in users:
                    values = {
                        'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        'date_deadline': date.today(),
                        'summary': summary,
                        'user_id': user.id,
                        'res_model_id':model_id,
                        'res_id':record.id,
                        'note': note,
                    }
                    mail_activity = self.env['mail.activity'].create(values)
                    mail_ids.append(mail_activity.id)
                    if mail_activity.id:
                        _logger.info("Activity created in HP {0} for User {1}".format(record.display_name,user.name))
                if len(mail_ids) == len(group.users.ids):
                    record.write({'stage_id':stage,
                                    'kanban_state':'done'})
            except Exception as e:
                _logger.info("Exception raise for the HP {0} while creating activity: {1}".format(self.display_name,e))
        if self.missing_documents:
            self.missing_documents = ", ".join([doc for doc in self.missing_documents.split(',') if doc.lower().strip() != 'customer photo'])

    def write(self,values):
        if values.get('stage_id',False):
            values.update(state=self.env['hp.stages'].browse(values.get('stage_id')).state)
        res = super(AccountHP,self).write(values)
        if values.get('stage_id',False) and values.get('stage_id') == self.env.ref('hire_purchase.hp_to_offer_acceptance').id:
            summary = note = "Review Final Offers & Select Offer with Customer"
            self.send_for_review(note=note,summary=summary,users=self.user_id)
        return res

    def confirm_reference_check(self):
        if not self.reference_checks_done:
            self.reference_checks_done = True
        if self.stage_id.id == self.env.ref('hire_purchase.hp_to_reference_check').id:
            self.confirm_hp_sale_order()

    def confirm_hp_sale_order(self):
        for record in self:
            response = False
            if record.selected_offer_id:
                app_taken_up_data = record._prepare_application_take_up()
                response = record.env['frontier.api.calls']._application_taken_up(body=app_taken_up_data)
            if response:
                order_id = record.sale_order_id
                order_confirm = order_id.state
                if order_id.state in ['draft']:
                    order_confirm = order_id.action_confirm()
                if order_confirm:
                    order_invoice = order_id._create_invoices()
                    if order_invoice.id:
                        order_invoice.action_post()


                payments = self.env['account.payment'].search([('hp_id','=',self.id),('invoice_ids','=',False)])

                if order_invoice and len(payments.ids):
                    receivable_line = payments.mapped('move_line_ids').filtered('credit')
                    order_invoice.js_assign_outstanding_line(receivable_line.ids)

                if order_invoice.id:
                    record.stage_id = self.env.ref('hire_purchase.hp_to_approved').id

    def _get_component_sequence(self):
        self.ensure_one()
        component = self.hp_type.hp_component_ids.sorted(lambda x:x.sequence)
        sequence = []
        for cs in component:
            if cs.type == 'int_rate':
                sequence.append('Interest')
            elif cs.type == 'fees':
                sequence.append('Fees')
            elif cs.type == 'insurance_fees' and cs.insurance_fee_type == 'gpi':
                sequence.append('GPI')
            elif cs.type == 'insurance_fees' and cs.insurance_fee_type == 'cli':
                sequence.append('CLI')
            elif cs.type == 'initiation_fee':
                sequence.append('Initiation Fee')
        return sequence