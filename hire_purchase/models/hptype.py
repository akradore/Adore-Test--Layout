#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


import time
import datetime
# from openerp import pooler
# from openerp.osv import osv
from odoo import fields,models,api
from datetime import date
import math
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class account_hptype(models.Model):
    _name = "account.hp.hptype"
    _description = "Account HP Type "

    name = fields.Char('Type Name', size=32,required=True)
    prooftypes = fields.One2many('account.hptype.prooflines', 'hp_type', 'Proof')
    hp_component_ids = fields.One2many('hp.component.line', 'hp_type_id', 'Component Line')
    calculation = fields.Selection(
        [
            ('flat','Flat'),
            ('reducing','Reducing'),
            ('cnt_prin','Constant Principal')
        ],'Calculation Method',required=True,default = 'reducing')
    interestversion_ids = fields.One2many('account.hp.hptype.interestversion','hptype_id','Interest Versions')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    account_id = fields.Many2one('account.account', string="Excess Payment Account")
    deposit_percentage = fields.Float(string='Deposit %')
    store_deposit_limit = fields.Float(string="Store Deposit % Limit",)
    initiation_fee = fields.Float(string='Initiation Fee %')
    finance_charges = fields.Float(string='Finance Charges %')
    is_default_type = fields.Boolean(string="Default Agreement",)

    def write(self,values):
        res = super(account_hptype,self).write(values)
        if values.get('is_default_type',False):
            records = self.search([('id','!=',self.id)])
            records.write({'is_default_type':False})
        return res


class account_hp_prooftypes(models.Model):
    _name = "account.hptype.prooflines"
    _description = "account hptype prooflines"

    name = fields.Many2one('account.hp.proof.type','Proof Type Name',size=64,required=True)
    shortcut = fields.Char("Shortcut",size=32)
    is_mandatory = fields.Boolean("Is Mandatory")
    hp_type = fields.Many2one('account.hp.hptype')

    @api.onchange('name')
    def onchange_name(self):
        res = {'shortcut': self.name.shortcut}
        return {'value':res}

class account_hp_hptype_interestversion(models.Model):
    _name='account.hp.hptype.interestversion'
    _description = "Account HP HPtype Interestversion"

    name = fields.Char('Name',size=32,required=True)
    hptype_id = fields.Many2one('account.hp.hptype','Agreement Type')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    active = fields.Boolean('Active',default = True )
    interestversionline_ids = fields.One2many('account.hp.hptype.interestversionline','interestversion_id','Current Interest Version')
    sequence = fields.Integer('Sequence',size=32)

    _order = 'sequence'

class account_loan_loantype_interestversionline(models.Model):
    _name='account.hp.hptype.interestversionline'
    _description = "Account HP HPtype interestversion line"

    name = fields.Char('Interest ID',size=32,required=True)
    interestversion_id = fields.Many2one('account.hp.hptype.interestversion','Loan Interest Id')
    min_month = fields.Integer('Minimum Month',size=32)
    max_month = fields.Integer('Maximum Month',size=32)
    min_amount = fields.Float('Minimum Amount', digits=(10,2))
    max_amount = fields.Float('Maximum Amount', digits=(10,2))
    rate = fields.Float('Rate',digits=(10,2))
    sequence = fields.Integer('Sequence',size=32)

    _order = 'sequence'


class HPComponentLine(models.Model):

    _name = 'hp.component.line'
    _description = "HP component interestversion"

    product_id = fields.Many2one('product.product', string="Product")
    type = fields.Selection(
        [('principal', 'Principal'), ('int_rate', 'Interest Rate'), ('fees', 'Fees'), ('late_fee', 'Late Fee'),
         ('initiation_fee','Initiation Fee'),('insurance_fees', 'Insurance Fees')], string="Component Type")
    insurance_fee_type = fields.Selection([('gpi', 'Goods Protection Insurance'), ('cli', 'Credit Life Insurance')])
    gl_code = fields.Many2one('account.account',string="GL Code")
    tax_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])
    amount_select = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fix', 'Fixed Amount'),
        ('code', 'Python Code'),
    ], string='Amount Type', index=True, required=True, default='fix', help="The computation method for the rule amount.")
    amount_percentage_base = fields.Many2many('product.product', string='Percentage based on', help='result will be affected to a variable')
    quantity = fields.Float(default=1.0, string="Quantity")
    amount_percentage = fields.Float(string='Percentage (%)', digits='Product Unit of Measure')
    amount_fix = fields.Float(string='Fixed Amount', digits='Product Price')
    amount_python_compute = fields.Text(string='Python Code')
    hp_type_id = fields.Many2one('account.hp.hptype')
    grace_period = fields.Integer("Grace Period(Month)")
    sequence = fields.Integer("Sequence")
    product_amt = fields.Float("Product Amount")
    tax_amount = fields.Float("Tax Amount")
    outstanding_product_amt = fields.Float('Outstanding Product Amt.')
    out_st = fields.Float("Outstanding")
    tenure = fields.Selection([('month', 'Month'), ('tenure', 'Loan Tenure'), ('per_year', 'Per Year')], "Fee Period",  default="month",)

    def _get_product_accounts(self):
        return {
            'income': self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id,
            'expense': self.product_id.property_account_expense_id or self.product_id.categ_id.property_account_expense_categ_id
        }

    def _compute_tax_id(self):
        for line in self:
            # If company_id is set, always filter taxes by the company
            taxes = line.product_id.taxes_id
            line.tax_id = taxes
            accounts = self._get_product_accounts()
            if accounts:
                line.gl_code = accounts['income']

    @api.onchange('product_id')
    def product_id_change(self):

        result = {}
        self._compute_tax_id()
        return result

    @api.onchange('amount_percentage_base')
    def product_id_onchange(self):
        res = []
        for o in self.hp_type_id.hp_component_ids:
            if self._origin.id != o.id:
                res.append(o.product_id.id)
        return {'domain':{'amount_percentage_base':[('id','in', res)]}}

    def _compute_rule(self):
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix, float(safe_eval(self.quantity)), 100.0
            except:
                raise UserError(_('Wrong quantity defined for salary rule %s (%s).') % (self.name, self.code))
        elif self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base)),
                        float(safe_eval(self.quantity)),
                        self.amount_percentage)
            except:
                raise UserError(_('Wrong percentage base or quantity defined for salary rule %s (%s).') % (self.name, self.code))