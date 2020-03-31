from odoo import fields, models, api, _
from datetime import date


class PartnerIncomeExpense(models.Model):
    _name = 'partner.income.expense'
    _description = "Partner Income Expense"


    def _compute_total(self):
        self.total_gross_salary = self.gross_income + self.overtime
        self.total_deduction = self.tax + self.uif + self. medical_aid + self.pf + self.other_deduction
        self.net_salary = self.total_gross_salary - self.total_deduction
        self.total_other_income = self.maintenance + self.rental_income + self.state_child + self.other_income
        self.total_net_monthly_income = self.net_salary + self.total_other_income
        self.sub_total =  self.rent + self.food + self.electricity + self.fuel + self.telephone + self.mobile + self.insurance \
                          + self.medical_cost + self.travel + self.education + self.savings + self.child_support + self. hps \
                          + self.other_payment + self.credit_card + self.car_finance + self.cloths + self.astra_furnish_pay + self.other_accounts
        self.total_monthly_expense = self.sub_total + self.buffer
        self.available_income = self.total_net_monthly_income - self.total_monthly_expense

    partner_id = fields.Many2one('res.partner')
    gross_income = fields.Float(string="Gross Income as per Payslip")
    overtime = fields.Float(string="Overtime and Commission")
    total_gross_salary = fields.Float(string="Total Gross Salary", compute='_compute_total')

    tax = fields.Float(string="Tax/Paye")
    uif = fields.Float(string="UIF")
    medical_aid = fields.Float(string="Medical Aid")
    pf = fields.Float(string="Pension/Provident Fund")
    other_deduction = fields.Float(string="Other Deductions")
    # gross_income = fields.Float(string="Gross Income as per Payslip")
    total_deduction = fields.Float(string="Total Deductions", compute='_compute_total')
    net_salary = fields. Float(string="Net salary", compute='_compute_total')

    maintenance = fields.Float(string="Maintenance")
    rental_income = fields.Float(string="Rental Income")
    state_child = fields.Float(string="State Child Grant")
    other_income = fields.Float(string="Other Income")
    total_other_income = fields.Float(string="Other Income Total", compute='_compute_total')
    total_net_monthly_income = fields.Float(string="Total Net Monthly Income", compute='_compute_total')

    rent = fields.Float(string="Rent or Bond")
    food = fields.Float(string="Food & Groceries")
    electricity = fields.Float(string="Electricity, Water & Rates")
    fuel = fields.Float(string="Car - Fuel and Maintenance")
    telephone = fields.Float(string="Telephone")
    mobile = fields.Float(string="Cellphone")
    insurance = fields.Float(string="Insurance")
    medical_cost = fields.Float(string="Medical Costs")
    travel = fields.Float(string="Travel (Bus, Taxi, Train)")
    education = fields.Float(string="Education (School, Creche)")
    savings = fields.Float(string="Savings")
    child_support = fields.Float(string="Maintenance/Child Support")
    other_payment = fields.Float(string="Other Payments")
    hps = fields.Float(string="HP Accounts (Micro, Bank)")
    credit_card = fields.Float(string="Credit Cards")
    car_finance = fields.Float(string="Car Finance")
    cloths = fields.Float(string="Clothing/Store Accounts")
    furniture = fields.Float(string="Furniture (NOT Astra Furnishers)")
    astra_furnish_pay = fields.Float(string="Astra Furnishers Payments")
    other_accounts = fields.Float(string="Other Accounts")
    buffer = fields.Float(string="Buffer (10% of expenses of R250)")
    sub_total = fields.Float(string="Sub Total", compute='_compute_total')
    total_monthly_expense = fields.Float(string="Total Monthly Expenses", compute='_compute_total')

    available_income = fields.Float(string="Available Disposable Income", compute='_compute_total')

    receive_marketing_material = fields.Selection([('y','Y'),('n','N')], string="Receive Marketing Material")
    marketing_by_email = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By Email")
    marketing_by_sms = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By SMS")
    marketing_by_telephone = fields.Selection([('y', 'Y'), ('n', 'N')], string="Marketing By Telephone")
    debt_administration_by_court = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever been placed under debt administration by court")
    declared_insolvent = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever declared insolvent")
    debt_rearrangement = fields.Selection([('y', 'Y'), ('n', 'N')], string="Ever Subject to debt-rearrangement")
    is_readonly = fields.Boolean(related="partner_id.is_readonly")

    @api.model
    def create(self,values):
        res = super(PartnerIncomeExpense, self).create(values)
        res.partner_id.write(dict(income=res.total_net_monthly_income, declared_expense=res.total_monthly_expense,
                                  income_expense_id=res.id))
        return res

    def write(self,vals):
        res = super(PartnerIncomeExpense,self).write(vals)
        for record in self:
            record.partner_id.write({'income':record.total_net_monthly_income,'declared_expense':record.total_monthly_expense})
            hp = self.env['account.hp'].search([('partner_id','=',record.partner_id.id),('state','=','draft')])
            if hp.id:
                hp.hp_application_edit()
        return res

    @api.model
    def default_get(self, fields):
        res = super(PartnerIncomeExpense,self).default_get(fields)
        res.update(dict(buffer=250,
                        receive_marketing_material ='y',
                        marketing_by_email ='y',
                        marketing_by_sms ='y',
                        marketing_by_telephone ='y'))
        return res
