import uuid

from odoo import fields, models, api, _
import requests
import json, logging
from odoo.exceptions import UserError, ValidationError, Warning
from random import randint
from datetime import datetime, date

_logger = logging.getLogger("Quick Check offer")

class FrontierOfferwizard(models.TransientModel):
    _name = 'quickcheck.offer.result'
    _description = 'quickcheck.offer.result '

    app_id = fields.Integer(string="App ID")
    status = fields.Selection([('CompletedApproved', 'CompletedApproved'), ('CompletedDeclined', 'CompletedDeclined'),
                               ('CompletedInsolvent', 'CompletedInsolvent'),('Pending', 'Pending'), ('SystemError', 'SystemError'),
                               ('ValidationError', 'ValidationError')], string="Status")
    decline_rsn = fields.Char(string="Decline Reasons")
    validation_error = fields.Char(string="Validation Errors")
    maximum_deal_amount = fields.Float(string="Maximum Deal Amount")
    offer_ids = fields.One2many('hp.offer', 'result_id', string="HP Offer")
    hp_amount = fields.Float('HP Loan Amount', digits=(12, 2), compute='_get_amt_from_percentage')
    order_amount = fields.Float(string="Order Amount")
    sale_order_id = fields.Many2one("sale.order", string="order")
    deposit_slider = fields.Integer(string="How much deposit to be paid?")
    deposit_percentage = fields.Integer(string='Deposit %')
    deposit_amt = fields.Float('Deposit Amount', digits=(12, 2), compute='_get_amt_from_percentage')
    user_message = fields.Char(string="Message", required=False, )
    debit_order_date = fields.Selection(selection='get_days', string="Debit Order Date", track_visibility='onchange')
    is_override_code = fields.Boolean(string="Override Minimum Deposit",  )

    partner_id = fields.Many2one("res.partner", string="Customer",  )
    return_type = fields.Selection([('cash', 'By Cash'), ('automatic', 'Debit Order'), ], 'Payment Type', index=True,
                                   default='automatic')
    override_new_deposit = fields.Float("New Deposit Approved",digits=(12, 2))
    override_code = fields.Char(string="Manger Override Code",)
    override_reason = fields.Char(string="Deposit Override Reason",)
    override_otp = fields.Char(string="OTP", default=0)

    def check_override_code(self):
        context = {
            'default_order_amount': self.order_amount,
            'default_deposit_slider':self.deposit_slider
        }
        if not self.override_code and not self._context.get('get_reason',0):
            raise UserError(_("Please enter valid code to override"))

        if self._context.get('get_reason',0) and not self.override_reason:
            raise UserError(_("Please enter reason for overrider"))

        if self._context.get('active_model','') == 'sale.order':
            context.update(sale_order_id=self._context.get('active_id'))

        order_id = self._context.get('sale_order_id',False) or context.get('sale_order_id',False)
        order_id = self.env['sale.order'].browse(order_id)
        if order_id.id:
            user = self.env['res.users'].search([('override_code','=',self.override_code)])
            if order_id.deposit_approval_code == self.override_code and not context.get('get_reason',False):
                order_id.override_type = 'head_office'
                context.update(default_deposit_slider= order_id.approved_deposit,overridden=1)
                order_id.message_post(body="Deposit Overriden:<br/>Type:<b>{0}<b><br/>User:<b>{1}<b>".format(
                    'Head Office', self.env.user.name))
            else:
                if self.override_code and not self._context.get('get_reason',0) and len(user.ids) != 1:
                    raise UserError(_("Code Invalid"))

                if self.override_reason and self.override_reason != '':
                    context.update(default_deposit_slider=order_id.hp_type.store_deposit_limit, overridden=1)
                    order_id.override_type = 'store_manager'
                    order_id.deposit_overrider_reason = self.override_reason
                    order_id.message_post(body="Deposit Overriden:<br/>Type:<b>{0}<b/><br/>User:<b>{1}<b/>".format(
                        'Store Manager', user.name))
                else:
                    context.update(get_reason=1,default_override_code=self.override_code,overriden=1)
        view_id = self.env.ref('hire_purchase.quickcheck_offer_deposite_wizard_form_view').id
        return {
                'name': _('QuickCheck Offer Deposit'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'quickcheck.offer.result',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': context
        }

    def get_days(self):
        day_list = []
        for i in range(1, 32):
            day_list.append((i, str(i)))
        return day_list

    @api.onchange('deposit_slider')
    def onchange_deposit_slider(self):
        if self.deposit_slider:
            self.deposit_percentage = self.deposit_slider

    @api.depends('order_amount', 'deposit_percentage')
    def _get_amt_from_percentage(self):
        for each in self:
            each.deposit_percentage = each.deposit_percentage or each.deposit_slider
            each.deposit_amt = (each.deposit_percentage / 100) * each.order_amount
            each.hp_amount = each.order_amount - each.deposit_amt

    def override_deposit_head_office(self):
        context = self._context
        if context.get('active_model','') == 'sale.order':
            if self.override_new_deposit == 0:
                raise UserError(_("Please add valid amount to override"))
            user = self.env.user.search([('override_code','=',self.override_code)])
            if not len(user.ids):
                raise UserError(_("Invalid Code for Override"))
            otp = str(randint(10000,99999))
            order = self.env[context.get('active_model')].browse(context.get('active_id'))
            order.write(dict(approved_deposit=self.override_new_deposit,
                             deposit_overrider_reason=self.override_reason,
                             deposit_approval_code = otp,
                             override_type=False
                             ))
            view_id = self.env.ref('hire_purchase.quick_check_override_action_view').id
            return {
                'name': _('Override Deposit'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_id':view_id,
                'res_model': 'quickcheck.offer.result',
                'target': 'new',
                'context': dict(default_override_new_deposit=self.override_new_deposit,
                                default_override_reason=self.override_reason,
                                default_override_otp = otp,
                                opt_generated=True
                                )
            }

    def action_quick_check_offer(self):
        order_id = False
        if self._context.get('active_model','') == 'sale.order':
            order_id =  self._context.get('active_id')
        if not order_id and self._context.get('sale_order_id',False):
            order_id = self._context.get('sale_order_id',False)
        self.sale_order_id = self.env['sale.order'].browse(order_id)
        ir_config_obj = self.env['ir.config_parameter']
        # if self.amount_total > self.maximum_deal_amount:
        #     raise ValidationError(_("Please ensure that the Order total is less than the Maximum Deal Amount"))
        frontier_api_id = self.env['frontier.api.calls'].search([('sale_order_id', '=', self.sale_order_id.id)])
        resp = frontier_api_id.login_request()
        if resp:
            qc_offer_url = ''
            ir_config_obj = self.env['ir.config_parameter']
            mode = ir_config_obj.sudo().get_param('hire_purchase.mode')
            access_token = resp.get('access_token')
            # hed = {'Authorization': 'Bearer ' + access_token}
            qc_api = ir_config_obj.sudo().get_param('hire_purchase.qc_api')
            if qc_api and mode == 'prod':
                qc_offer_url = ir_config_obj.sudo().get_param('hire_purchase.qc_offer_prod_url')
            elif qc_api and mode == 'test':
                qc_offer_url = ir_config_obj.sudo().get_param('hire_purchase.qc_offer_test_url')



            payload = {
                  "appId": frontier_api_id.app_id if frontier_api_id else '',
                  "dealAmount": self.hp_amount or 0.0,
                  "grossIncome": self.sale_order_id.partner_id.income_expense_id.gross_income if self.sale_order_id.partner_id.income_expense_id else 0.00,
                  "nettIncome": self.sale_order_id.partner_id.income,
                  "otherIncome": 0.00,
                  "expenses": [
                    {
                      "code": "BUSS",
                      "amount": self.sale_order_id.partner_id.income_expense_id.hps if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    },
                    # {
                    #   "code": "CC",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.credit_card if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "CELL",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.mobile if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "CLOTH",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.cloths if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # # {
                    # #   "code": "CLOTHO",
                    # #   "amount": self.partner_id.income_expense_id.cloths if self.partner_id.income_expense_id else 0.00,
                    # # },
                    # {
                    #   "code": "FEES",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.education if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "FURN",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.astra_furnish_pay if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "GROC",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.food if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "HML",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "INS",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.insurance if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "INSO",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "MEDAID",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.medical_cost if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "NCABF",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "OTHEX",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.other_payment if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "OTHIN",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "PEN",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "PERS",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "PHCNT",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "PPAID",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "RATES",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "RENT",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.rent if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "SNDRYBUR",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "TEL",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.telephone if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "TRANS",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.travel if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "UNION",
                    #   "amount": 0.00,
                    # },
                    # {
                    #   "code": "UTIL",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.electricity if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                    # {
                    #   "code": "VEH",
                    #   "amount": self.sale_order_id.partner_id.income_expense_id.car_finance if self.sale_order_id.partner_id.income_expense_id else 0.00,
                    # },
                  ]
                }
            # print("payload======>", payload)

            try:
                context = {}
                headers = frontier_api_id._prepare_request_headers(access_token)
                _logger.info("Payload Data for sale order {0} --- {1}".format(self.sale_order_id.display_name,json.dumps(payload)))
                qc_offer_resp = requests.post(qc_offer_url, headers=headers, data=json.dumps(payload))
                if qc_offer_resp and qc_offer_resp.status_code == 200:
                    qc_offer_resp = qc_offer_resp.json()
                    # print("qc_offer_resp=======>", qc_offer_resp)
                    view_id = self.env.ref('hire_purchase.quickcheck_offer_result_wizard_form_view').id
                    if qc_offer_resp.get('status') == 'CompletedApproved':
                        offers = []
                        for i in qc_offer_resp.get('offers'):
                            # print("i==========>",i.get('loanAmount'))
                            offers.append((0,0, {'hp_amount': i.get('loanAmount'),
                                                 'instalment': i.get('instalment'),
                                                 'adminfee': i.get('adminFee'),
                                                 'interest': i.get('interest'),
                                                 'initiation_fee': i.get('initiationFee'),
                                                 'total_vat': i.get('totalVAT'),
                                                 'tcoc': i.get('tcoc'),
                                                 'settlement_amount': i.get('settlementAmount'),
                                                 'term': i.get('term'),
                                                 'first_instalment_date': datetime.strptime(i.get('firstInstalmentDate'),"%Y-%m-%dT%H:%M:%S"),
                                                 'payment_freq': i.get('paymentFrequency').lower(),
                                                 'deposit_amt': i.get('depositAmount'),
                                                 'deposit_per': i.get('depositPercentage'),
                                                 'life_insurance_amount':i.get("lifeInsuranceAmount"),
                                                 'insurance_amt':i.get("insuranceAmount"),
                                                 }))
                        offers.sort(key=lambda x:x[2].get('term'))
                        context.update({'default_status': 'CompletedApproved',
                                    'default_app_id': qc_offer_resp.get('appId'),
                                     'default_partner_id':self.sale_order_id.partner_id.id,
                                    'default_debit_order_date':False,
                                    'default_maximum_deal_amount': qc_offer_resp.get('maximumDealAmount'),
                                   'default_offer_ids': offers,
                                    })
                    elif qc_offer_resp.get('status') == 'CompletedDeclined':
                        context.update({'default_status': 'CompletedDeclined',})
                    elif qc_offer_resp.get('status') == 'CompletedInsolvent':
                        context.update({'default_status': 'CompletedInsolvent',})
                    elif qc_offer_resp.get('status') == 'Pending':
                        context.update({'default_status': 'Pending',})
                    elif qc_offer_resp.get('status') == 'SystemError':
                        context.update({'default_status': 'SystemError',})
                    elif qc_offer_resp.get('status') == 'ValidationError':
                        context.update({'default_status': 'ValidationError',})
                    # print("context======>", context)
                    any_active_hp=self.env['account.hp'].search(
                        [('partner_id', '=', self.sale_order_id.partner_id.id),
                         ('state', 'not in', ['done', 'cancel'])]).ids
                    any_active_hp = len(any_active_hp) and True or False
                    context.update(dict(any_active_hp=any_active_hp,order='term'))
                    return {
                        'name': _('QuickCheck Offer Result'),
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'view_type': 'form',
                        'res_model': 'quickcheck.offer.result',
                        'view_id': view_id,
                        'views': [(view_id, 'form')],
                        'context': context,
                        'target': 'new'
                    }
                else:
                    raise UserWarning(_(qc_offer_resp.json()['message']))
            except Exception as e:
                raise Warning(_(e))

    def submit_hp_application(self):
        selected_offer = self.offer_ids.filtered(lambda x: x.is_selected_offer)
        if not selected_offer.id:
            raise ValidationError(_("Please select an offer"))
        elif not self.debit_order_date:
            raise ValidationError(_("Please select the debit order date"))
        else:
            quick_check_result = self.browse(self._context['active_id'])
            fields_to_check = ['id_no','dob','mobile','phone','street','city','state_id','country_id','zip','bank_ids','income_expense_id']
            if quick_check_result.sale_order_id.partner_id.company_type == 'person':
                fields_to_check.extend(['title','gender','ethnic_group','marital_status','emp_company_name'])
                if quick_check_result.sale_order_id.partner_id.marital_status == 'MARRIED':
                    fields_to_check.extend(['spouse_name','spouse_surname'])

            frontier_api_id = self.env['frontier.api.calls'].search([('sale_order_id', '=', quick_check_result.sale_order_id.id)])
            frontier_api_id._check_missing_fields(quick_check_result.sale_order_id.partner_id,fields_to_check)
            hp_period = self.env['hp.installment.period'].search([('period','=',int(selected_offer.term))])
            create_values = {'name':quick_check_result.sale_order_id.name,
                       'apply_date':date.today(),
                        'return_type':self.return_type,
                        'payment_freq':selected_offer.payment_freq,
                        'user_id':self.env.user.id,
                        'repayment_basis':'sanctioned_amt',
                        'company_id':self.env.company.id ,
                        'store_id':quick_check_result.sale_order_id.store_id.id,
                        'partner_id':quick_check_result.sale_order_id.partner_id.id,
                        'req_amt':quick_check_result.hp_amount,
                        'deposit_per':quick_check_result.deposit_percentage,
                        'deposit_amt':quick_check_result.deposit_amt,
                        'hp_period':hp_period.id,
                        'is_cli':quick_check_result.sale_order_id.is_cli,
                        'is_gpi':quick_check_result.sale_order_id.is_gpi,
                        'hp_amount':quick_check_result.hp_amount,
                        'hp_amt':quick_check_result.hp_amount,
                        'hp_type':quick_check_result.sale_order_id.hp_type.id,
                        'interest':selected_offer.interest,
                        'total_installment':hp_period.period,
                        'initiation_fee':selected_offer.initiation_fee,
                        'finance_charges':selected_offer.adminfee,
                        'sale_order_id':quick_check_result.sale_order_id.id,
                        'debit_order_date': self.debit_order_date,
            }
            hp_account = self.env['account.hp'].sudo()
            ctx =dict(hp_account._context)
            hp_account_id =self.env['account.hp'].sudo().with_context(ctx).create(create_values) or False
            if hp_account_id:
                ir_config_obj = self.env['ir.config_parameter']
                is_frontier = ir_config_obj.sudo().get_param('hire_purchase.calculation_done_by',False)
                frontier_api_id.hp_account_id = hp_account_id
                resp = frontier_api_id.login_request()
                if resp.get('access_token',False):
                    mode = ir_config_obj.sudo().get_param('hire_purchase.mode')
                    url = mode == 'test' and 'test_create_application_url' or  mode == 'post' and 'prod_create_application_url' or ''
                    url = ir_config_obj.sudo().get_param("hire_purchase."+ url,False)
                    if url:
                        headers = frontier_api_id._prepare_request_headers(resp.get('access_token'))
                        payload_data = frontier_api_id._prepare_create_application_data(deposit=quick_check_result.deposit_amt,
                                                                                        term=hp_period.id,
                                                                                        sale_order=quick_check_result.sale_order_id,
                                                                                        debit_date_code=self.debit_order_date)
                        frontier_api_id.app_nr = payload_data.get('appNr')
                        create_application_response = requests.request("POST",url,data=json.dumps(payload_data),headers=headers).json()
                        status = create_application_response['status'].lower()
                        if  status == 'successful':
                            hp_account_id.stage_id = hp_account_id.stage_id.search([('name','=','Pending Documents')]).id
                            view_id = self.env.ref('hire_purchase.quickcheck_offer_result_submit_hp_application').id
                            return {
                                'name': _('Submitted HP Application'),
                                'type': 'ir.actions.act_window',
                                'view_mode': 'form',
                                'view_type': 'form',
                                'res_model': 'quickcheck.offer.result',
                                'view_id': view_id,
                                'views': [(view_id, 'form')],
                                'target': 'new',
                                'context':{'hp_account_id':hp_account_id.id}
                            }
                        elif status == 'successfulexists':
                            raise Warning(_("Application has already been submitted and is in process."))
                        elif status == 'systemerror':
                            raise UserError(_("Please contact octagon"))
                        elif status == 'validationerror':
                            raise UserError(_('\n'.join(create_application_response['validationErrors'])))

    def open_hp_application(self):
        view_id = self.env.ref('hire_purchase.account_hp_form').id
        return {
            'name': _('HP Account'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.hp',
            'view_id': view_id,
            'res_id': self._context.get('hp_account_id'),
            'target': 'current',
        }

class HPOffer(models.TransientModel):
    _name = 'hp.offer'
    _description = 'HP Offer'

    result_id = fields.Many2one('quickcheck.offer.result', string="QC Offer Result")
    approve_offers_id = fields.Many2one("approve.offers", "Approve Offers",)
    is_selected_offer = fields.Boolean(string="Select Offer",  )
    approve_offers_id = fields.Many2one("approve.offers", string="Approve Offers",)
    offer_id = fields.Integer(string="Offer Id",)
    hp_amount = fields.Float(string="HP Amount")
    instalment = fields.Float(string="Instalment")
    adminfee = fields.Float(string="Admin Fee")
    interest_rate = fields.Float(string="Interest Rate",)
    interest = fields.Float(string="Interest")
    initiation_fee = fields.Float(string="Initiation Fee")
    total_vat = fields.Float(string="Total VAT")
    tcoc = fields.Float(string="Total COC")
    settlement_amount = fields.Float(string="Settlement Amount")
    term = fields.Float(string="Term")
    first_instalment_date = fields.Datetime(string="First Installment Date")
    life_insurance_amount = fields.Float(string="CLI")
    insurance_amt = fields.Float(string="GPI",  required=False, )
    payment_freq = fields.Selection(
        [('daily', 'Daily'), ('weekly', 'Weekly'), ('bi_month', 'Bi Monthly'), ('monthly', 'Monthly'),
         ('quarterly', 'Quarterly'), ('half_yearly', 'Half-Yearly'), ('yearly', 'Yearly')], "Payment Frequency",
        default="monthly")
    deposit_amt = fields.Float(string="Deposit Amount")
    deposit_per = fields.Float(string="Deposit Percentage")

