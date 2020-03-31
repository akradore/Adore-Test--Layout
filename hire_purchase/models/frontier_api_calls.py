import uuid
import json
import requests
from datetime import date
from odoo import api, fields, models,_
from odoo.exceptions import UserError,ValidationError

class FrontierAPICalls(models.Model):
    _name = 'frontier.api.calls'
    _description = 'Frontier API Calls'

    date = fields.Datetime(string="Date")
    app_nr = fields.Char(string="App Nr")
    type = fields.Selection([('qc', 'QuickCheck'), ('qc_offer', 'QuickCheckOffer')], string="Type")
    partner_id = fields.Many2one('res.partner', string="Partner")
    sale_order_id = fields.Many2one('sale.order', string="Sales Order")
    hp_account_id = fields.Many2one('account.hp', string="HP Account")
    status = fields.Selection([('CompletedApproved', 'CompletedApproved'), ('CompletedDeclined', 'CompletedDeclined'), ('CompletedInsolvent', 'CompletedInsolvent'),
                               ('Pending', 'Pending'), ('SystemError', 'SystemError'), ('ValidationError', 'ValidationError')], string="Status")
    app_id = fields.Char(string="App Id")
    decline_rsn = fields.Char(string="Decline Reasons")
    validation_error = fields.Char(string="Validation Errors")
    est_credit_amount = fields.Float(string="Estimated Credit Amount")
    quick_check_deposit = fields.Float(string="Deposit")
    maximum_deal_amount = fields.Float(string="Maximum Deal Amount")

    def _get_url(self,test_key=False,prod_key=False):
        ir_config_obj = self.env['ir.config_parameter']
        mode = ir_config_obj.sudo().get_param('hire_purchase.mode')
        if mode:
            url = mode == 'test' and test_key or prod_key
            url = 'hire_purchase.'+url
            return ir_config_obj.sudo().get_param(url)

    def _prepare_request_headers(self,access_token):
        if access_token:
            return {
                'content-type': "application/json",
                'cache-control': "no-cache",
                'Authorization': 'Bearer ' + access_token
            }
    def create_quotation(self):
        view_id = self.env.ref('sale.view_order_form').id
        sale_order_obj = self.env['sale.order']
        context = dict(sale_order_obj._context)
        context.update(action_source='quick_check_offer_wizard')
        sale_order_id = sale_order_obj.with_context(context).create({
                            'partner_id': self.partner_id.id,
                            'hp_type':self.partner_id.hp_agreement_type.id or False,
                            'maximum_deal_amount':self.maximum_deal_amount,
                            'sale_type': "hire_purchase",
                        })
        self.sale_order_id = sale_order_id.id
        return {
            'name': _('Quotations'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sale.order',
            'view_id': view_id,
            'res_id': sale_order_id.id,
            'target': 'current',
            # 'context': {'default_maximum_deal_amount': self.maximum_deal_amount,}
            }

    def _check_missing_fields(self,object=False,fields=[]):
        if object and len(fields):
            fields_with_missing_values=""
            for field in fields:
                if isinstance(object[field],(date)) and not len(str(object[field])) or not object[field]:
                    fields_with_missing_values+= "\n {0}".format(object._fields[field].string)
            if len(fields_with_missing_values):
                raise UserError(_("Following fields are missing for "
                                  "{} :\n{}".format(object.display_name,
                                                                                      fields_with_missing_values)))

    def login_request(self):
        url = ''
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
        try:
            resp = requests.post(url + 'Token', headers={"Content-Type": 'x-www-form-urlencoded', }, data=body)
            return resp.json()
        except Exception as e:
            raise Warning(_(e))

    def _prepare_spouse_details(self,partner=False):
        if partner:
            return {
                "firstName": partner.spouse_name,
                "surname": partner.spouse_name or '',
                "titleCode": '',
                "genderCode": '',
                "ethnicTypeCode": '',
                "idNo": partner.spouse_id_no,
                "idType": '',
                "streetAddress": {
                    "addressLine1": partner.street or '',
                    "addressLine2": partner.street2 or '',
                    "suburb": partner.street2 or '',
                    "townCity": partner.city or '',
                    "postCode": partner.zip or '',
                    "provinceCode": partner.state_id.code or '',
                    "countryCode": partner.country_id.code or '',
                }
            }

    def _get_formatted_contact(self,contact):
        if contact:
            if contact[:3] == '+27':
                contact=contact[3:]
            return contact.replace(' ','')

    def _prepare_partner_data(self,partner=False,debit_order_date=False):
        partner_name = partner.name and partner.name.split(' ')
        income_expense = partner.income_expense_id
        spouse_details = []
        if partner.marital_status == 'MARRIED':
                spouse_details = self._prepare_spouse_details(partner)
        partner_bank = partner.bank_ids[0]
        return {
            "applicantDetail": {
                "firstName": partner_name[0] or '',
                "middleName": len(partner) == 3 and partner_name[1] or '',
                "surname": partner_name[-1] or '',
                "titleCode": partner.title.shortcut or '',
                "initials": partner.initials or '',
                "genderCode": partner.gender or '',
                "ethnicTypeCode": partner.ethnic_group or '',
                "idNo": partner.id_no or '',
                "idType": partner.id_type or '',
                "dob": str(partner.dob) or '',
                "age": 0,
                "phoneContactDetails": {
                    "homeNo": self._get_formatted_contact(partner.phone) or '',
                    "cellNo": self._get_formatted_contact(partner.mobile) or '',
                    "workNo": self._get_formatted_contact(partner.mobile) or ''
                },
                "maritalStatusCode": partner.marital_status or '',
                "maritalContractCode": partner.how_u_married or '',
                "streetAddress": {
                    "addressLine1": partner.street or '',
                    "addressLine2": partner.street2 or '',
                    "suburb": partner.street2 or '',
                    "townCity": partner.city or '',
                    "postCode":partner.zip or '',
                    "provinceCode": partner.state_id.code or '',
                    "countryCode": partner.country_id.code or '',
                    "monthsAtAddress": 15
                },
                "deliveryAddress": {
                    "addressLine1": partner.street or '',
                    "addressLine2": partner.street2 or '',
                    "suburb": partner.street2 or '',
                    "townCity": partner.city or '',
                    "postCode": partner.zip or '',
                    "provinceCode": partner.state_id.code or '',
                    "countryCode": partner.country_id.code or ''
                },
                "employmentDetails": {
                    "employerName": partner.emp_company_name or '',
                    "occupation": partner.occupation or '',
                    "monthsEmployed": partner.months_employed or '',
                    "department": partner.emp_department or '',
                    "employerAddress": {
                        "addressLine1": partner.emp_work_street or '',
                        "addressLine2": partner.emp_work_street2 or '',
                        "suburb": partner.emp_work_street2 or '',
                        "townCity": partner.emp_work_city or '',
                        "postCode": partner.emp_work_zip or '',
                        "provinceCode": partner.emp_work_state_id.code or '',
                        "countryCode": partner.emp_work_country_id.code or ''
                    },
                    "employmentStatusCode": "1"
                },
                "salaryPayDay": partner.salary_pay_date or ''
            },
            "spouseDetail": spouse_details,
            "noOfDependants": 1,
            "isSequestrated": False,
            "isAdminOrder": False,
            "isDebtReview": False,
            "ncaTeleMarketInd": False,
            "ncaOtherMediaIndSMS": False,
            "ncaMarketListInd": False,
            "debitOrderBankingDetail": {
                "bankNameCode": partner_bank.bank_id.short_code or '',
                "branchCodeCode": partner_bank.bank_id.bic or '',
                "accountTypeCode": partner_bank.account_type or '',
                "accountNumber": partner_bank.acc_number or '',
                "accountHolderName": partner_bank.acc_holder_name or '',
                "accountHolderInitials": partner_bank.partner_id.initials or '',
                "debitOrderDeductionDayCode": debit_order_date
            },
            "allowances": [
                {
                    "allowanceCode": "BAS",
                    "allowanceAmount": income_expense.gross_income,
                    "capturedAmount": income_expense.gross_income,
                    "description": "Basic Salary"
                },
                {
                    "allowanceCode": "SAL",
                    "allowanceAmount": income_expense.total_net_monthly_income,
                    "capturedAmount": income_expense.total_net_monthly_income,
                    "description": "Nett Salary"
                }
            ],
            "deductions": [
                {
                    "deductionCode": "GROC",
                    "deductionAmount": income_expense.food,
                    "capturedAmount": income_expense.food,
                },
                {
                    "deductionCode": "UTIL",
                    "deductionAmount": income_expense.electricity,
                    "capturedAmount": income_expense.electricity,
                }
            ]
        }

    def _prepare_product_data(self,order_line=[]):
        product_details = []
        for line in order_line:
            product_details.append({
                "modelName": line.name,
                "price": line.price_unit,
                "quantity": int(line.product_uom_qty),
                "referenceNo": line.id
            })
        return product_details

    def _prepare_create_application_data(self,deposit=False,term=False,sale_order=False,debit_date_code=False):
        if sale_order:
            return {
                "appNr": str(uuid.uuid4()),
                "dealAmt": sale_order.amount_total,
                "deposit":deposit,
                "contractPeriodCode":term ,
                "accountTypeCode": "ASTC",
                "primaryApplicant": self._prepare_partner_data(sale_order.partner_id,debit_date_code),
                "productModels": self._prepare_product_data(sale_order.order_line)
            }

    def check_missing_documents(self,AppNr=False,return_field='description'):
        if AppNr:
            url = self._get_url(test_key='test_document_missing_url',prod_key='prod_document_missing_url')
            if url:
                document_missing_resp = self._make_frontier_request(method="GET",url=url,params={'AppNr':AppNr})
                if document_missing_resp:
                    document_list = [doc[return_field] for doc in document_missing_resp if doc['linkedDocumentId'] == 0]
                    return len(document_list) and (", ".join(document_list)).strip(',') or False

    def check_application_status(self,AppNr=False,get_offers=False):
        if AppNr:
            url = self._get_url(test_key='application_status_test_url',prod_key='application_status_prod_url')
            if url:
                response =  self._make_frontier_request(method="GET",url=url,params={'AppNr':AppNr})
                return_response = {'status':response.get('status')}
                if response.get('pendingQueues',False) and len(response.get('pendingQueues',[])):
                    return_response.update({
                        'queue_code':response.get('pendingQueues')[0].get('queueCode'),
                        'queue_status':response.get('pendingQueues')[0].get('description')
                    })
                if response['status'].lower() == 'pendingofferacceptance' and get_offers == True:
                    return response.get('offers')
                if response.get('status','') == 'CompletedApproved' and len(response.get('offers',[])):
                    return_response.update(offers=response.get('offers'))
                return return_response

    def _make_frontier_request(self,url=False,method=False,params={},body=False,access_token=False,headers=False,**kwargs):
        try:
            if url:
                if not access_token:
                    access_token = self.login_request().get('access_token')
                if not headers:
                    headers = self._prepare_request_headers(access_token)
                app_request = requests.request(method, url, headers=headers, params=params,data=json.dumps(body))
                if app_request.status_code == 200:
                    if kwargs.get('is_upload_req',False) and app_request.text == '':
                        return True
                    if kwargs.get('is_application_taken_up',False) and app_request.text == '':
                        return True
                    return len(app_request.text) and app_request.json() or None
                if app_request.status_code == 404:
                    raise UserError(_(app_request.text.replace('\'','')))
                else:
                    raise UserError(_(app_request.json()['message']))
        except Exception as e:
            if kwargs.get('is_upload_req',False):
                e = "{0} : {1}".format(body['documentCode'],e)
            raise UserError(_(e))

    def _upload_hp_document(self,body=False):
        if body:
            url = self._get_url(test_key='upload_document_test_url',prod_key='upload_document_prod_url')
            if url:
                login_request = self.login_request()
                response = {}
                if login_request.get('access_token'):
                    headers = self._prepare_request_headers(login_request.get('access_token'))
                for each in body:
                    response[each['documentCode']] = self._make_frontier_request(method="POST", url=url, body=each,
                                                                              headers=headers,
                                                                              access_token=login_request.get(
                                                                                  'access_token'),is_upload_req = True)
                return response


    def _application_taken_up(self,body=False,access_token=False):
        if body:
            url = self._get_url(test_key='application_takenup_test_url',prod_key='application_takenup_prod_url')
            response = False
            if url:
                response = self._make_frontier_request(url=url, method="POST", body=body, is_application_taken_up=True,access_token=access_token)
                return response

    def _get_document_type(self):
        url = 'https://apps.octagon.co.za/frontieruat/api/V1/DocumentTypes'
        response = self._make_frontier_request(url=url,method="GET")
        return [resp.get('documentCode') for resp in response]

    def _application_edit(self,body=False,access_token=False):
        if body:
            url = self._get_url(test_key='application_edit_test_url',prod_key='application_edit_prod_url')
            response = False
            if url:
                response = self._make_frontier_request(url=url,body=body,method="put",access_token=access_token)
