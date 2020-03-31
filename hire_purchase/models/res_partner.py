from odoo import fields, models, api, _
from datetime import date, datetime
import requests
import json,logging
from odoo.exceptions import UserError, ValidationError, Warning
import uuid

_logger = logging.getLogger(__name__)
class PartnerLine(models.Model):
    _name = 'res.partner.hp.line'
    _description = 'Partner HP Account Line'

    name = fields.Many2one('res.partner')
    hp_id = fields.Many2one('account.hp')

class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"
    account_type = fields.Selection(string="Bank Account Type", selection=[('C', 'Cheque'), ('S', 'Savings'),
                                                                      ('T', 'Transmission'), ('CC', 'Credit Card')])
    acc_branch_name = fields.Char(string="Branch Name")
    acc_branch_code = fields.Char(string="Branch Code")

class ResBank(models.Model):
    _inherit = 'res.bank'
    short_code = fields.Char(string="Short Code", )


class ResPartnerTitle(models.Model):
    _inherit = 'res.partner.title'

    def name_get(self):
        return [(x.id,x.shortcut) for x in self.search([])]

class HPCustomer(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def get_days(self):
        day_list = []
        for i in range(1, 32):
            day_list.append((i, str(i)))
        return day_list

    vip_status = fields.Selection([('vip', 'VIP'), ('gold_vip', 'Gold VIP')], String="VIP Status")
    income = fields.Float('Monthly Income', digits=(12, 2), store=True)
    is_group = fields.Boolean(string='Is Group',store=True)
    initials = fields.Char(string='Initials')
    gender = fields.Selection([('M', 'Male'), ('F', 'Female')], string="Gender")
    ethnic_group = fields.Selection([('Black', 'Black'), ('Coloured', 'Coloured'), ('Indian', 'Indian'), ('White', 'White')], string="Ethnic Group")
    marital_status = fields.Selection([('SINGLE', 'Single'), ('MARRIED', 'Married'), ('DIVORCED', 'Divorced'), ('SEPERATED', 'Seperated'), ('WIDOWED', 'Widowed'), ('OTHER', 'Other')], string="Marital Status")
    how_u_married = fields.Selection([('ANC', 'Ante Nuptial Contract'), ('COM', 'Community of Property')], string="How are you married ")
    home_lang = fields.Selection([('ndebele', 'Ndebele'), ('sotho','Sotho'), ('siSwati','SiSwati'), ('tsonga','Tsonga'),
                                  ('tswana','Tswana'), ('venda','Venda'), ('sotho','Sotho'), ('xhosa','Xhosa'),
                                  ('zulu','Zulu'), ('afrikaans','Afrikaans'), ('english','English')])
    prefered_lang = fields.Selection([('ndebele', 'Ndebele'), ('sotho', 'Sotho'), ('siSwati', 'SiSwati'), ('tsonga', 'Tsonga'),
                                        ('tswana', 'Tswana'), ('venda', 'Venda'), ('sotho', 'Sotho'), ('xhosa', 'Xhosa'),
                                        ('zulu', 'Zulu'), ('afrikaans', 'Afrikaans'), ('english', 'English')])
    period_at_address = fields.Integer(string="Period at Address (m)")
    previous_address = fields.Integer(string="Previous Address (m)")
    is_owner_or_tenant = fields.Selection([('tenant', 'Tenant'), ('owner','Owner')], String="Home Owner O.R. Tenant")
    is_own_vehical = fields.Boolean(string="Own a Vehicle")
    id_type = fields.Selection([('R', 'South African'), ('O', 'Other')],string="ID Type")
    id_no = fields.Char(string="ID/Passport No")
    dob = fields.Date(string="DOB")
    no_of_dependants = fields.Integer(string="No of Dependents")
    phone2 = fields.Char(string="Phone 2")

    emp_company_name = fields.Char(string="Employer's Company Name")
    occupation = fields.Char(string="Occupation")
    emp_department = fields.Char(string="Department")
    months_employed = fields.Integer(string="Months Employed")
    emp_work_street = fields.Char()
    emp_work_street2 = fields.Char()
    emp_work_zip = fields.Char(change_default=True)
    emp_work_city = fields.Char()
    emp_work_state_id = fields.Many2one("res.country.state", string="Work State", ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]")
    emp_work_country_id = fields.Many2one('res.country', string='Work Country', ondelete='restrict')
    emp_work_telephone = fields.Char(string="Work Telephone")
    salary_pay_date = fields.Selection(selection='get_days',string="Salary Pay Date")
    salary_freq = fields.Selection([('weekly', 'Weekly'), ('monthly','Monthly')],default='monthly', string="Salary Frequency")

    relationship = fields.Char(string="Relationship")
    ref_title = fields.Many2one('res.partner.title', string="Ref Title")
    ref_initials = fields.Char(string='Ref Initials')
    ref_surname = fields.Char(string="Ref Surname")
    ref_name = fields.Char(string="Ref Name")
    ref_id = fields.Char(String="I.D. Number")
    ref_work_street = fields.Char()
    ref_work_street2 = fields.Char()
    ref_work_zip = fields.Char(change_default=True)
    ref_work_city = fields.Char()
    ref_work_state_id = fields.Many2one("res.country.state", string="Ref Work State", ondelete='restrict',
                                        domain="[('country_id', '=?', country_id)]")
    ref_work_country_id = fields.Many2one('res.country', string='Ref Work Country', ondelete='restrict')
    ref_work_telephone = fields.Char(string="Ref Work Telephone")
    ref_home_telephone = fields.Char(string="Ref Home Telephone")
    ref_mobile = fields.Char(string="Ref Mobile")

    friend_name = fields.Char(string="Friend Name")
    friend_surname = fields.Char(string="Friend Surname")
    friend_employer = fields.Char(string="Friend Employeer")
    friend_home_telephone = fields.Char(string=" Friend Home Telephone")
    friend_work_telephone = fields.Char(string="Friend Work Telephone")

    spouse_name = fields.Char(string="Spouse Name")
    spouse_surname = fields.Char(string="Spouse Surname")
    spouse_cell_no = fields.Char(string="Spouse Cell No")
    spouse_department = fields.Char(string="Work Department")
    spouse_work_telephone = fields.Char(string="Spouse Work Telephone")
    spouse_id_type = fields.Selection([('R', 'South African'), ('O', 'Other')],string="Spouse ID Type")
    spouse_id_no = fields.Char(string="Spouse ID/Passport No")

    employer = fields.Char(string="Employer")
    income_expense_id = fields.Many2one('partner.income.expense', string="Partner Income Expense")

    receive_marketing_material = fields.Selection([('y','Y'),('n','N')], string="Receive Marketing Material")
    marketing_by_email = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By Email")
    marketing_by_sms = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By SMS")
    marketing_by_telephone = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By Telephone")
    debt_administration_by_court = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever been placed under debt administration by court")
    declared_insolvent = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever declared insolvent")
    debt_rearrangement = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever Subject to debt-rearrangement")

    hp_agreement_type = fields.Many2one("account.hp.hptype", string="HP Agreement Type",store=True)
    declared_expense = fields.Monetary(string='Declared Expenses')
    is_readonly = fields.Boolean(string="HP Application is in progress ?",compute="_get_is_editable")
    first_name = fields.Char(string="First Name", )
    surname = fields.Char(string="Surname",)


    def _get_is_editable(self):
        for record in self:
            readonly = False
            partners_hp = self.env['account.hp'].search([('partner_id','=',record.id)])
            if self.env.ref('hire_purchase.group_hp_account_controller') in self.env.user.groups_id:
                readonly = len(partners_hp.filtered(lambda x:x.stage_id.state == 'apply').ids) and True or False
            elif len(partners_hp.filtered(lambda x:x.stage_id.state not in ['approved','done','close'])):
                readonly = True
            record.is_readonly = readonly

    @api.onchange('id_no')
    def onchange_id_no(self):
        user_id_no = self.id_no
        if user_id_no and len(user_id_no) == 13:
            current_year = int(str(date.today().year)[2:])
            id_year = int(user_id_no[0:2])
            century = ((current_year - id_year) * -1) < 0 and int(str(date.today().year)[2:]) or int(str(date.today().year)[2:]) - 1
            dob = "{0}/{1}/{2}".format(user_id_no[2:4],user_id_no[4:6],'{0}{1}'.format(century,id_year))
            dob = datetime.strptime(dob,'%m/%d/%Y')
            gender = int(user_id_no[6:10])
            gender = gender in range(0000,4999) and 'F' or gender in range(5000,9999) and 'M' or False
            self.write({'dob':dob,'gender':gender})

    @api.model
    def default_get(self,fields):
        res = super(HPCustomer, self).default_get(fields)
        hp_agreement_type = self.hp_agreement_type.search([('is_default_type','=',True)])
        hp_agreement_type = len(hp_agreement_type) and hp_agreement_type[0].id or False
        country_id = self.env['res.country'].search([('code','=','ZA')]).id
        res.update(dict(hp_agreement_type=hp_agreement_type, country_id=country_id, id_type='R', is_company=False,
                        emp_work_country_id=country_id,ref_work_country_id=country_id))
        return res

    def open_income_expense(self):
        income_expense_id = self.env['partner.income.expense'].search([('partner_id','=',self.id)])
        context = {}
        if income_expense_id:
            res_id = income_expense_id.id
        else:
            res_id = False
            context = {'default_partner_id': self.id}
        return {
            'name': _('Income &amp; Expenses'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'partner.income.expense',
            'view_id': self.env.ref('hire_purchase.partner_income_expenses_view_form').id,
            'type': 'ir.actions.act_window',
            'res_id': res_id,
            'context': context,
            'target': 'current'
        }
    def write(self,vals):
        res = super(HPCustomer,self).write(vals)
        if vals.get('first_name', False) or vals.get('surname',False):
            for user in self.filtered(lambda x:x.company_type == 'person'):
                user.name = "{0} {1}".format(user.first_name,user.surname)
        return res

    @api.model
    def create(self,values):
        if values.get('company_type','') == 'person':
            values['name'] = values.get('first_name','')+ ' ' + values.get('surname', '')
        res = super(HPCustomer,self).create(values)
        return res


    def action_quick_check_api(self):
        if self.income <= 0.00:
            raise UserError("Monthly Income should be greater than 0.00")
        url = ''
        qc_app_url = ''
        username = ''
        password = ''
        ir_config_obj = self.env['ir.config_parameter']
        mode = ir_config_obj.sudo().get_param('hire_purchase.mode')
        if mode == 'prod':
            url = ir_config_obj.sudo().get_param('hire_purchase.production_url')
            username = ir_config_obj.sudo().get_param('hire_purchase.prod_username')
            password = ir_config_obj.sudo().get_param('hire_purchase.prod_password')
        elif mode == 'test':
            url = ir_config_obj.sudo().get_param('hire_purchase.test_url')
            username = ir_config_obj.sudo().get_param('hire_purchase.test_username')
            password = ir_config_obj.sudo().get_param('hire_purchase.test_password')

        body = {"grant_type": "password",
                "username": username,
                "password": password,
                }
        headers = {"Content-Type" : 'x-www-form-urlencoded',}

        try:
            resp = requests.post(url+'Token', headers=headers, data=body)
            resp = resp.json()
        except Exception as e:
            raise Warning(_(e))
        if resp:
            access_token = resp.get('access_token')
            # hed = {'Authorization': 'Bearer ' + access_token}
            qc_api = ir_config_obj.sudo().get_param('hire_purchase.qc_api')
            if qc_api and mode == 'prod':
                qc_app_url = ir_config_obj.sudo().get_param('hire_purchase.qc_app_prod_url')
            elif qc_api and mode == 'test':
                qc_app_url = ir_config_obj.sudo().get_param('hire_purchase.qc_app_test_url')
            # print("qc_app_url===========>", qc_app_url)

            # payload = "{\r\n  \"appNr\": \"3936f17b-9640-4788-818f-d5d443ab5f79\",\r\n  \"consumer\": {\r\n    \"name\": \"sejal\",\r\n    \"surname\": \"patel\",\r\n    \"idNo\": \"9012230723086\",\r\n    \"idType\": \"R\",\r\n    \"address\": {\r\n    \t\"addressline1\": \"22384 EXT 21\",\r\n    \t\"addressline2\": \"\",\r\n    \t\"suburb\": \"\",\r\n    \t\"towncity\": \"EMBALENMHLE\",\r\n    \t\"postcode\": \"2285\",\r\n    },\r\n  },\r\n  \"accountType\": \"ASTC\",\r\n  \"dealAmount\": 0,\r\n  \"grossIncome\": 35000,\r\n  \"nettIncome\": 25000,\r\n  \"otherIncome\": 0,\r\n}"
            app_nr = str(uuid.uuid4())
            payload = {"appNr": app_nr,
                       "consumer": {
                           "name": str(self.name.split(" ", 1)[0]),
                           "surname": str(self.name.split(" ", 1)[1]),
                           "idNo": self.id_no,
                           "idType": self.id_type,
                           "dob": str(self.dob),
                           "gender": self.gender,
                           "address": {
                               "addressline1": self.street,
                               "addressline2": self.street2,
                               "suburb": "",
                               "towncity": self.city,
                               "postcode": self.zip,
                           },
                       },
                       "accountType": "ASTC",
                       "dealAmount": 0.00,
                       "grossIncome": 0,
                       "nettIncome": self.income,
                       "otherIncome": 0,
                       "expenses": [{
                           "code": "BUSS",
                           "amount": self.declared_expense or 0.0
                       }]
                       }
            headers = {
                'content-type': "application/json",
                'cache-control': "no-cache",
                'Authorization': 'Bearer ' + access_token
            }
            try:
                _logger.info("Quick check request for {0} - {1}".format(self.name,json.dumps(payload)))
                qc_resp = requests.request("POST", qc_app_url, data=json.dumps(payload), headers=headers)
                # qc_resp = requests.post(qc_app_url, data=json.dumps(payload), headers=headers)
                qc_resp = qc_resp.json()
                status = ''
                if qc_resp.get('status') == 'CompletedApproved':
                    status = 'CompletedApproved'
                elif qc_resp.get('status') == 'CompletedDeclined':
                    status = 'CompletedDeclined'
                elif qc_resp.get('status') == 'CompletedInsolvent':
                    status = 'CompletedInsolvent'
                elif qc_resp.get('status') == 'Pending':
                    status = 'Pending'
                elif qc_resp.get('status') == 'SystemError':
                    status = 'SystemError'
                elif qc_resp.get('status') == 'ValidationError':
                    status = 'ValidationError'
                partner_deposit_percentage = self.hp_agreement_type.deposit_percentage
                if not qc_resp.get('validationErrors',False):
                    response_max_amount = qc_resp.get('maximumDealAmount') or 0.0
                    quick_check_deposit = 0.0
                    if partner_deposit_percentage != 0:
                        quick_check_deposit = response_max_amount * (partner_deposit_percentage/100)
                    max_deal_amnt = response_max_amount + quick_check_deposit
                frontier_api_call_id = self.env['frontier.api.calls'].create({'date': datetime.now(),
                                                                              'app_nr':app_nr,
                                                                              'type': 'qc',
                                                                              'partner_id': self.id,
                                                                              'status': status,
                                                                              'app_id': qc_resp.get('appId'),
                                                                              'decline_rsn': qc_resp.get('declineReasons'),
                                                                              'validation_error': qc_resp.get('validationErrors'),
                                                                              'est_credit_amount': response_max_amount,
                                                                              'quick_check_deposit': quick_check_deposit,
                                                                              'maximum_deal_amount': max_deal_amnt,
                                                                            })

                view_id = self.env.ref('hire_purchase.view_res_partner_quick_check_form').id
                return {
                    'name': _('Frontier API Calls'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'frontier.api.calls',
                    'view_id': view_id,
                    'res_id': frontier_api_call_id.id,
                    'target': 'new'
                }
            except Exception as e:
                raise Warning(_(e))
            # if qc_resp:
            #     # access_token = resp.get('access_token')
            #     # hed = {'Authorization': 'Bearer ' + access_token}
            #     qc_offer_app_url = 'https://apps.octagon.co.za/frontieruat/api/V1/QuickCheckOffer'
            #     # qc_api = ir_config_obj.sudo().get_param('hire_purchase.qc_api')
            #     # if qc_api and mode == 'prod':
            #     #     qc_app_url = ir_config_obj.sudo().get_param('hire_purchase.qc_app_prod_url')
            #     # elif qc_api and mode == 'test':
            #     #     qc_app_url = ir_config_obj.sudo().get_param('hire_purchase.qc_app_test_url')
            #     # # print("qc_app_url============>", qc_app_url)
            #     body = {
            #             "appId": 2392,
            #             "dealAmount": 15000.00,
            #             "grossIncome": 35000.00,
            #             "nettIncome": 25000.00,
            #             "otherIncome": 0.00,
            #             "expenses": [
            #                 {
            #                     "code": "CLOTH",
            #                     "amount": 2285.00
            #                 },
            #                 {
            #                     "code": "GROC",
            #                     "amount": 5000.00
            #                 },
            #                 {
            #                     "code": "HML",
            #                     "amount": 10000.00
            #                 },
            #                 {
            #                     "code": "FEES",
            #                     "amount": 2000.00
            #                 },
            #                 {
            #                     "code": "CELL",
            #                     "amount": 500.00
            #                 }
            #             ]
            #     }
            #     try:
            #         qc_offer_resp = requests.post(qc_offer_app_url, headers=hed, data=body)
            #         qc_offer_resp = qc_offer_resp.json()
            #         print("qc_offer_resp=======>", qc_offer_resp)
            #         if qc_offer_resp.get('status') == 'CompletedApproved':
            #             view_id = self.env.ref('hire_purchase.quickcheck_offer_result_wizard_form_view').id
            #             offers = []
            #             for i in qc_offer_resp.get('offers'):
            #                 offers.append((0,0, {'hp_amount': i.get('loanAmount'),
            #                                      'instalment': i.get('instalment'),
            #                                      'adminfee': i.get('adminFee'),
            #                                      'interest': i.get('interest'),
            #                                      'initiation_fee': i.get('initiationFee'),
            #                                      'total_vat': i.get('totalVAT'),
            #                                      'tcoc': i.get('tcoc'),
            #                                      'settlement_amount': i.get('settlementAmount'),
            #                                      'term': i.get('term'),
            #                                      'first_instalment_date': i.get('firstInstalmentDate'),
            #                                      'payment_freq': i.get('paymentFrequency'),
            #                                      'deposit_amt': i.get('depositAmount'),
            #                                      'deposit_per': i.get('depositPercentage')}))
            #             return {
            #                 'name': _('QuickCheck Offer Result'),
            #                 'type': 'ir.actions.act_window',
            #                 'view_mode': 'form',
            #                 'view_type': 'form',
            #                 'res_model': 'frontier.offer.result',
            #                 'view_id': view_id,
            #                 'views': [(view_id, 'form')],
            #                 'context': {'default_app_id': qc_offer_resp.get('appId'),
            #                             'default_offer_ids': offers,
            #                             },
            #                 'target': 'new'
            #             }
            #     except Exception as e:
            #         raise Warning(_(e))
