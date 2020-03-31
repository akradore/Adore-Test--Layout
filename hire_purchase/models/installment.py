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
from odoo import fields,models,api
from datetime import date
import math
from dateutil.relativedelta import relativedelta


class AccountHPInstallment(models.Model):
    _name = 'account.hp.installment'
    _description = "Account HP Installment"

    @api.depends('due_principal','due_interest','due_fees', 'due_gpi', 'due_cli')
    def calculate_installment_due(self):
        for line in self:
            line.installment_due = line.due_principal + line.due_interest + line.due_fees + line.due_gpi + line.due_cli
        
    name = fields.Char('Description',size=64 )
    hp_id = fields.Many2one('account.hp', 'HP')
    capital = fields.Float('Principal', digits=(12, 2))
    initiation_fee = fields.Float('Initiation Fee', digits=(12, 2))
    interest = fields.Float('Interest', digits=(12, 2))
    total = fields.Float('Installment', digits=(12, 2),)
    partner_id = fields.Many2one('res.partner','Customer')
    fees = fields.Float("Fees", digits=(12, 2),)
    gpi = fields.Float("GPI", digits=(12, 2), )
    cli = fields.Float("CLI", digits=(12, 2), )
    date = fields.Date("Date")
    old_disburse_amt = fields.Float("Old Disburse Amount")
    is_paid_installment = fields.Boolean("Is paid")
    due_principal = fields.Float("Principal Due")
    due_interest = fields.Float("Interest Due")
    due_fees = fields.Float("Fee Due")
    due_gpi = fields.Float("GPI Due")
    due_cli = fields.Float("CLI Due")
    installment_due = fields.Float("Installment Due",compute='calculate_installment_due')
    state = fields.Selection([
            ('draft','Draft'),
            ('open','Open'),
            ('partial_paid','Partial Paid'),
            ('paid','Paid'),
        ],'State', readonly=False, index=True, default='draft')
    outstanding_prin = fields.Float("Outstanding Principal", digits=(12, 2))
    outstanding_int = fields.Float("Outstanding Interest", digits=(12, 2))
    outstanding_fees = fields.Float("Outstanding Fees", digits=(12, 2))
    outstanding_gpi = fields.Float("Outstanding GPI", digits=(12, 2))
    outstanding_cli = fields.Float("Outstanding CLI", digits=(12, 2))
    fee_lines = fields.One2many('fees.lines', 'installment_id', 'Fees Line')
    late_fee = fields.Float("Late Fee")
    
    local_principle = fields.Float('Local Principal', digits=(12, 2),default = 0.0)
    local_interest = fields.Float('Local Interest', digits=(12, 2),default = 0.0)
    local_fees = fields.Float("Local Fees", digits=(12, 2),default = 0.0)
    move_id = fields.Many2one('account.move', "Move")
    paid_prin = fields.Float('Paid Capital')
    paid_int = fields.Float('Paid Interest')
    paid_fees = fields.Float('Paid Fees')
    paid_fees_tx = fields.Float('Paid Fees Tax')
    paid_late_fee = fields.Float('Paid Late Fees')
    paid_late_fee_tx = fields.Float('Paid Late Fees Tax')
    is_post = fields.Boolean('Fees Post Done')
    
    
    @api.depends('outstanding_prin') 
    def onchange_principle(self):
        self.write({'local_principle':self.local_principle+self._context.get('prin')})
        
    @api.depends('outstanding_int') 
    def onchange_interest(self):
        self.write({'local_interest':self.local_interest+self._context.get('int')})
        
    @api.depends('outstanding_fees') 
    def onchange_fees(self):
        self.write({'local_fees':self.local_fees+self._context.get('fee')})

    @api.model
    def post_cron(self):
        date_start =  date.today() + relativedelta(days=-1)
        rec_ids = self.env['account.hp.installment'].search([('date','=',str(date_start))])
        for each in rec_ids:
            each.post()


    def post(self):
        journal_id = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        partner = self.hp_id.partner_id
        analytic_account = self.env['account.analytic.account'].search([('code','=',self.hp_id.hp_id)])
        for type_line in self.hp_id.hp_type.hp_component_ids:
            price = 0.0
            create_invoice = True
            product = type_line.product_id
            if type_line.type == 'initiation_fee' and self.initiation_fee:
                price = self.initiation_fee
                ref = "Initiation Fee"
            elif type_line.type == 'int_rate' and self.interest:
                price = self.interest
                ref = 'Interest'
            elif type_line.type == 'fees' and self.fees:
                price = self.fees
                ref = 'Fees'
            elif type_line.type == 'insurance_fees' and type_line.insurance_fee_type == 'gpi' and self.gpi:
                price = self.gpi
                ref = 'GPI'
            elif type_line.type == 'insurance_fees' and type_line.insurance_fee_type == 'cli' and self.cli:
                price = self.cli
                ref = 'CLI'
            else:
                create_invoice = False
            if create_invoice:
                invoice_lines ={
                    'product_id':product.id,
                    'name':product.name,
                    'account_id':type_line.gl_code,
                    'quantity':1,
                    'analytic_account_id':analytic_account.id,
                    'price_unit':price,
                    'tax_ids':[(6,0,type_line.tax_id.ids)],
                }
                move_id = self.env['account.move'].create({
                    'partner_id':self.hp_id.partner_id.id,
                    'journal_id': journal_id.id,
                    'type':'out_invoice',
                    'invoice_date':date.today(),
                    'ref': "{0}-{1}-{2}".format(ref, self.name.upper(), self.hp_id.display_name),
                    'sale_type': self.hp_id.sale_order_id.sale_type,
                    'store_id': self.hp_id.store_id.id,
                    'invoice_line_ids':[(0,0,invoice_lines)]
                })
                move_id.line_ids.write({'acc_hp_id':self.hp_id.id,'hp_instalment_id':self.id})
                move_id.post()
        self.is_post = True
        self.state = 'open'


class HPInstallmentPeriod(models.Model):
    _name = 'hp.installment.period'
    _description = "HP Account installment period"
    
    name = fields.Char('Period Name', size=64, required=True)
    period = fields.Integer('HP Account Period(months)', required = True)
    
    
class PaymentScheduleLine(models.Model):
    
    _name = 'payment.schedule.line'
    _description = "payment schedule Lines"
    
    name = fields.Char('Description',size=64 )
    hp_id = fields.Many2one('account.hp', 'HP')
    capital = fields.Float('Principal', digits=(12, 2),)
    interest = fields.Float('Interest', digits=(12, 2),)
    total = fields.Float('Installment', digits=(12, 2),)
    partner_id = fields.Many2one('res.partner','Customer')
    fees = fields.Float("Fees", digits=(12, 2),)
    gpi = fields.Float("GPI", digits=(12, 2), )
    cli = fields.Float("CLI", digits=(12, 2), )
    date = fields.Date("Date")
    old_disburse_amt = fields.Float("Old Disburse Amount")
    is_paid_installment = fields.Boolean("Is paid")
    installment_id = fields.Many2many('account.hp.installment',string="Installment Line Id")
    
    
class Fees_lines(models.Model):
    _name  = 'fees.lines'
    _description = "Fees Lines"
    
    name = fields.Char("Type")
    product_id = fields.Many2one('product.product', "Product")
    base = fields.Float("Base")
    tax = fields.Float("Tax")
    base_paid = fields.Float("Base Paid")
    tax_paid = fields.Float("Tax Paid")
    installment_id = fields.Many2one('account.hp.installment', 'Installment Id')
    is_paid = fields.Boolean("Is Paid")
    
    
