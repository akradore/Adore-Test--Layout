from odoo import fields, api, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mode = fields.Selection([('prod', 'Production'), ('test', 'Test')], string="Mode", default='test')
    production_url = fields.Char(string=" Production Environment URL" ,)
    test_url = fields.Char(string="Testing Environment URL",)
    test_username = fields.Char(string="Test API Username")
    test_password = fields.Char(string="Test API Password")
    prod_username = fields.Char(string="PROD API Username")
    prod_password = fields.Char(string="PROD API Password")
    qc_api = fields.Boolean(string="QuickCheck (QC) API")
    qc_app_prod_url = fields.Char(string="QC App PROD URL",)
    qc_app_test_url = fields.Char(string="QC App Test URL",)
    qc_offer_prod_url = fields.Char(string="QC Offer PROD URL",)
    qc_offer_test_url = fields.Char(string="QC Offer Test URL",)


    test_create_application_url = fields.Char(string="Create Application Test URL",)
    prod_create_application_url = fields.Char(string="Create Application PROD URL",)

    calculation_done_by = fields.Selection(string="HP Calculations Done By", selection=[('frontier', 'Frontier'), ('hp_app', 'HP App'), ],default="frontier")

    test_document_missing_url = fields.Char(string="Document Missing Test URL",)
    prod_document_missing_url = fields.Char(string="Document Missing PROD URL",)

    application_status_test_url = fields.Char(string="Application Status Test URL",)
    application_status_prod_url = fields.Char(string="Application Status PROD URL",)

    upload_document_test_url = fields.Char(string="Upload Document Test URL", )
    upload_document_prod_url = fields.Char(string="Upload Document PROD URL", )

    application_takenup_test_url = fields.Char(string="Application taken up Test URL", )
    application_takenup_prod_url = fields.Char(string="Application taken up PROD URL", )

    application_edit_test_url = fields.Char(string="Application Edit Test URL", )
    application_edit_prod_url = fields.Char(string="Application Edit PROD URL", )

    is_auto_create_inst_lines = fields.Boolean(string="Auto Create Instalment Lines",default=True)

    @api.model
    def default_get(self,fields):
        res = super(ResConfigSettings, self).default_get(fields)
        res.update({
            'production_url':'https://apps.octagon.co.za/frontier/',
            'test_url':'https://apps.octagon.co.za/frontieruat/',
            'qc_app_prod_url':"https://apps.octagon.co.za/frontier/api/V1/QuickCheck",
            'qc_app_test_url':"https://apps.octagon.co.za/frontieruat/api/V1/QuickCheck",
            'qc_offer_prod_url':"https://apps.octagon.co.za/frontier/api/V1/QuickCheckOffer",
            'qc_offer_test_url':"https://apps.octagon.co.za/frontieruat/api/V1/QuickCheckOffer",
            'test_create_application_url':"https://apps.octagon.co.za/frontieruat/api/V1/Application",
            'prod_create_application_url':"https://apps.octagon.co.za/frontier/api/V1/Application",
            'prod_document_missing_url':"https://apps.octagon.co.za/frontier/api/V1/DocumentsRequired",
            'test_document_missing_url':"https://apps.octagon.co.za/frontieruat/api/V1/DocumentsRequired",
            'application_status_test_url':"https://apps.octagon.co.za/frontieruat/api/V1/ApplicationStatus",
            'application_status_prod_url':"https://apps.octagon.co.za/frontier/api/V1/ApplicationStatus",
            'upload_document_test_url' :"https://apps.octagon.co.za/frontieruat/api/V1/DocumentUpload",
            'upload_document_prod_url' :"https://apps.octagon.co.za/frontier/api/V1/DocumentUpload",
            'application_takenup_test_url' :"https://apps.octagon.co.za/frontieruat/api/V1/ApplicationTakeup",
            'application_takenup_prod_url' :"https://apps.octagon.co.za/frontier/api/V1/ApplicationTakeup",
            'application_edit_test_url' :"https://apps.octagon.co.za/frontieruat/api/V1/ApplicationEdit",
            'application_edit_prod_url' :"https://apps.octagon.co.za/frontier/api/V1/ApplicationEdit",         
        })
        return res


    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        param_obj = self.env['ir.config_parameter']
        res.update({
            'mode': param_obj.sudo().get_param('hire_purchase.mode'),
            'production_url': param_obj.sudo().get_param('hire_purchase.production_url'),
            'test_url': param_obj.sudo().get_param('hire_purchase.test_url'),
            'test_username': param_obj.sudo().get_param('hire_purchase.test_username'),
            'test_password': param_obj.sudo().get_param('hire_purchase.test_password'),
            'prod_username': param_obj.sudo().get_param('hire_purchase.prod_username'),
            'prod_password': param_obj.sudo().get_param('hire_purchase.prod_password'),
            'qc_api': param_obj.sudo().get_param('hire_purchase.qc_api'),
            'qc_app_prod_url': param_obj.sudo().get_param('hire_purchase.qc_app_prod_url'),
            'qc_app_test_url': param_obj.sudo().get_param('hire_purchase.qc_app_test_url'),
            'qc_offer_prod_url': param_obj.sudo().get_param('hire_purchase.qc_offer_prod_url'),
            'qc_offer_test_url': param_obj.sudo().get_param('hire_purchase.qc_offer_test_url'),
            'test_create_application_url': param_obj.sudo().get_param('hire_purchase.test_create_application_url'),
            'prod_create_application_url': param_obj.sudo().get_param('hire_purchase.prod_create_application_url'),
            'prod_document_missing_url': param_obj.sudo().get_param('hire_purchase.prod_document_missing_url'),
            'test_document_missing_url': param_obj.sudo().get_param('hire_purchase.test_document_missing_url'),
            'application_status_test_url': param_obj.sudo().get_param('hire_purchase.application_status_test_url'),
            'application_status_prod_url': param_obj.sudo().get_param('hire_purchase.application_status_prod_url'),
            'upload_document_test_url': param_obj.sudo().get_param('hire_purchase.upload_document_test_url'),
            'upload_document_prod_url': param_obj.sudo().get_param('hire_purchase.upload_document_prod_url'),
            'calculation_done_by': param_obj.sudo().get_param('hire_purchase.calculation_done_by'),
            'application_takenup_test_url': param_obj.sudo().get_param('hire_purchase.application_takenup_test_url'),
            'application_takenup_prod_url': param_obj.sudo().get_param('hire_purchase.application_takenup_prod_url'),
            'application_edit_test_url': param_obj.sudo().get_param('hire_purchase.application_edit_test_url'),
            'application_edit_prod_url': param_obj.sudo().get_param('hire_purchase.application_edit_prod_url'),
            'is_auto_create_inst_lines': param_obj.sudo().get_param('hire_purchase.is_auto_create_inst_lines'),
        })
        return res

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        param_obj = self.env['ir.config_parameter']
        param_obj.sudo().set_param('hire_purchase.mode', self.mode)
        param_obj.sudo().set_param('hire_purchase.production_url', self.production_url)
        param_obj.sudo().set_param('hire_purchase.test_url', self.test_url)
        param_obj.sudo().set_param('hire_purchase.test_username', self.test_username)
        param_obj.sudo().set_param('hire_purchase.test_password', self.test_password)
        param_obj.sudo().set_param('hire_purchase.prod_username', self.prod_username)
        param_obj.sudo().set_param('hire_purchase.prod_password', self.prod_password)
        param_obj.sudo().set_param('hire_purchase.qc_api', self.qc_api)
        param_obj.sudo().set_param('hire_purchase.qc_app_prod_url', self.qc_app_prod_url)
        param_obj.sudo().set_param('hire_purchase.qc_app_test_url', self.qc_app_test_url)
        param_obj.sudo().set_param('hire_purchase.qc_offer_prod_url', self.qc_offer_prod_url)
        param_obj.sudo().set_param('hire_purchase.qc_offer_test_url', self.qc_offer_test_url)
        param_obj.sudo().set_param('hire_purchase.test_create_application_url', self.test_create_application_url)
        param_obj.sudo().set_param('hire_purchase.prod_create_application_url', self.prod_create_application_url)
        param_obj.sudo().set_param('hire_purchase.test_document_missing_url', self.test_document_missing_url)
        param_obj.sudo().set_param('hire_purchase.prod_document_missing_url', self.prod_document_missing_url)
        param_obj.sudo().set_param('hire_purchase.prod_create_application_url', self.prod_create_application_url)
        param_obj.sudo().set_param('hire_purchase.application_status_test_url', self.application_status_test_url)
        param_obj.sudo().set_param('hire_purchase.application_status_prod_url', self.application_status_prod_url)
        param_obj.sudo().set_param('hire_purchase.upload_document_test_url', self.upload_document_test_url)
        param_obj.sudo().set_param('hire_purchase.upload_document_prod_url', self.upload_document_prod_url)
        param_obj.sudo().set_param('hire_purchase.calculation_done_by', self.calculation_done_by)
        param_obj.sudo().set_param('hire_purchase.application_takenup_test_url', self.application_takenup_test_url)
        param_obj.sudo().set_param('hire_purchase.application_takenup_prod_url', self.application_takenup_prod_url)
        param_obj.sudo().set_param('hire_purchase.application_edit_test_url', self.application_edit_test_url)
        param_obj.sudo().set_param('hire_purchase.application_edit_prod_url', self.application_edit_prod_url)
        param_obj.sudo().set_param('hire_purchase.is_auto_create_inst_lines', self.is_auto_create_inst_lines)
        return res

