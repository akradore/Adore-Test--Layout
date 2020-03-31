#!/usr/bin/env python
# -*- encoding: utf-8 -*-


{
    'name' : 'Hire Purchase',
    "version" : "14.30",
    'category': 'Finance',
    'summary': "Hire Purchase",
    "depends" : ["base","sale_management", "account","account_accountant","crm","stock"],
    "author" : "Strategic Dimensions",
    "description": """Hire Purchase System
    * Integrated to Accounting System
    * Usefull for any type of HP Account
    * Clean Varification Process for Proofs
    * Workflow for Account Approval/Rejection 2
    * Reports related to the Account, Documents
    * Dynamic Interest Rates Calculation
    """,
    "website" : "http://www.strategicdimensions.co.za",
    "init_xml" : [],
    "demo" : [
#         "demo/loan_demo.xml"
    ],
    "data" : [
        "security/hp_account_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template.xml",
        "data/hp_classifications_data.xml",
        "data/hp_default_stages.xml",
        "data/hp_default_period.xml",
        "data/hp_proof_type.xml",
        "data/ir_cron.xml",
        "views/hp_account_config.xml",
        "views/stores_view.xml",
        "views/hp_extended_view.xml",
        "views/hp_asset.xml",
        "views/hp_payment_view.xml",
        "wizard/payment_receipt_wizard.xml",
        "wizard/approve_offers_wizard.xml",
        "wizard/deposit_hp_payment.xml",
        "views/hp_account_view.xml",
        "views/hp_dashboard.xml",
        "views/hptype_view.xml",
        "views/hp_sequence.xml",
        "report/reports.xml",
        "views/hp_scheduler.xml",
        "views/classifications_view.xml",
        "views/hp_stages_view.xml",
        "views/main_hp_view.xml",
        "wizard/wiz_download_report_view.xml",
        "views/hp_portal_template.xml",
        "views/partner_income_expense.xml",
        "views/res_partner.xml",
        "wizard/quickcheck_wizard.xml",
        "views/sale_view.xml",
        "views/hp_charges.xml",
        "views/res_users.xml",
        "views/account_move.xml",
        "views/res_config_settings.xml",
        "views/hp_account_settings.xml",
        "wizard/wizard_disbursement_view.xml",
        "report/account_hp_report.xml",
        "report/report_payment_receipt.xml",
        "report/payment_receipt_report_view.xml",
        "report/hp_info.xml",
        "report/merge_letter.xml",
        "report/sale_report_template.xml",

#         "views/loan_workflow.xml",
#         "views/loan_wizard.xml",
#         "views/cheque_workflow.xml",

    ],
    'qweb': [
        "static/src/xml/widget.xml"
    ],
    'price':25000,
    'currency':'ZAR',
    "active": False,
    "installable": True,
    # 'images': ['images/main_screenshot.png'],
}
