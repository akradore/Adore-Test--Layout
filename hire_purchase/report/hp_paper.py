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

class HPPaper(models.AbstractModel):
    _name = 'report.hire_purchase.merge_letter'
    _description = "report.hire_purchase.merge_letter"

    @api.model
    def _get_report_values(self, docids, data=None):
        hp = self.env['account.hp'].browse(docids)
        docargs = {
            'doc_ids': docids,
            'doc_model': 'account.hp',
            'data': data,
            'docs': hp,
            'time': time,
            'merge' : self.__parse_paragraph__,
        }
        return docargs

    def __parse_paragraph__(self,content,hp):

        fetchval={
            '{p_name}':hp.name or '',
            '{p_hp_amount}':str(hp.hp_amount) or '',
            '{p_hp_period}':str(hp.hp_period) or '',
            '{p_process_fee}':str(hp.process_fee) or '',
            '{p_apply_date}':str(hp.apply_date) or '',
            '{p_approve_date}':str(hp.approve_date) or '',
            '{p_approve_amount}':str(hp.approve_amount) or '',
            '{p_contact}': str(hp.partner_id.name) + '\n' + str(hp.partner_id.street) + '\n ' + str(hp.partner_id.street2) + '\n ' + str(hp.partner_id.city) + '\n' + str(hp.partner_id.zip) or '',
        }
        for key in fetchval :
            content=content.replace(key,fetchval.get(key))
        return content;

