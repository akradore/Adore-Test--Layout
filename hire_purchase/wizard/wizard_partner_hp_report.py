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
import time

hp_form = '''<?xml version="1.0"?>
<form string="Select partner">
    <field name="partner_id"/>
</form>'''

hp_fields = {
    'partner_id': {'string':'Partner', 'type':'many2one', 'relation': 'res.partner', 'required':True},
}

class wizard_report(models.TransientModel):
    _description = "Wizard Report"
    states = {
        'init': {
            'actions': [],
            'result': {'type':'form', 'arch':hp_form, 'fields':hp_fields, 'state':[('end','Cancel'),('report','Print HP Report.')]}
        },
        'report': {
            'actions': [],
            'result': {'type':'print', 'report':'account.partner.hp', 'state':'end'}
        }
    }
wizard_report()