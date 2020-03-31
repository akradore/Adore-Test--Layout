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
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError

acct_form = '''<?xml version="1.0"?>
<form string="Select period">
    <field name="cus_pay_acc" select="1"/>
    <newline/>
    <field name="parent_emp_pay_acc" select="1"/>
    <newline/>
    <field name="int_acc" select="1"/>
    <newline/>
    <field name="bank_acc" select="1"/>
    <newline/>
    <field name="proc_fee" select="1"/>
    <newline/>   
 </form>'''

acct_fields = {
    'cus_pay_acc': {'string': 'Customer HP Account', 'type': 'char', 'required': 'True', 'size':'200' },
    'parent_emp_pay_acc': {'string': 'Parent HP Account', 'type': 'many2one', 'relation': 'account.account', 'domain':"[('type','=','other')]",'required': 'True','help':'This is parent account for Employee Payable Account' },
    'int_acc':{'string': 'Interest Account', 'type': 'many2one', 'relation': 'account.account', 'domain':"[('type','=','other')]",'required': 'True' },
    'bank_acc': {'string': 'Bank Account', 'type': 'many2one', 'relation': 'account.account', 'domain':"[('type','=','other')]",'required': 'True'},
    'proc_fee': {'string': 'Processing fee Account', 'type': 'many2one', 'relation': 'account.account', 'domain':"[('type','=','other')]",'required': 'True'},
}

class wizard_cus_acct(models.TransientModel): 
    _description = "wizard_cus_acct"

    def get_defaults(self, data):
        user = self.env['account.hp']
        data['form']['cus_pay_acc'] = user.hp_id
        return data['form']
    
    def create_cus_acct(self, data):
        cname = data['form']['cus_pay_acc']
        par_cname = data['form']['parent_emp_pay_acc']
        dname = data['form']['int_acc']
        bnk_acc = data['form']['bank_acc']
        prc_fee = data['form']['proc_fee'] 

        account = self.env['account.account']
        type = self.env['account.account.type']
        user = self.env['account.hp']
        
        lia_id = type.search[('code','=','liability')]
        exp_id = type.search[('code','=','expense')]
        ass_id = type.search[('code','=','asset')]
        inc_id = type.search[('code','=','income')]
        
        hp_id = user.read([data['id']], ['hp_id'])[0]['hp_id']
        name = user.read([data['id']], ['partner_id'])[0]['partner_id']

        credit_id = account.create( {
            'code': name[1] + '/' + hp_id,
            'name':cname,
            'parent_id':par_cname,
            'type':'other',
            'reconcile':True,
            'user_type':ass_id[0]
            })
        user.write(data['id'],{'cus_pay_acc' :credit_id, 'int_acc' : dname, 'bank_acc' : bnk_acc,'proc_fee':prc_fee})
        return {}
    
    states = {
        'init': {
            'actions': [get_defaults],
            'result': {'type':'form', 'arch':acct_form, 'fields':acct_fields, 'state':[('create','Create'),('end','Cancel','gtk-cancel')]}
        },
        'create': {
            'actions': [create_cus_acct],
            'result': {'type':'state','state':'end'}
        }
    }
wizard_cus_acct()