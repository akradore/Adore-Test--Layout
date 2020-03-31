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
import odoo
from odoo import fields
from datetime import date
import datetime
from odoo import fields, api, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

class hp_details(models.AbstractModel):
    _name = 'report.hire_purchase.hp_info'
    _description = "hire_purchase.hp_info"
     
    s=0.0
    _capital=0.0
    _interest=0.0
    _subtotal=0.0

    @api.model
    def _get_report_values(self, docids, data=None):
        hp = self.env['account.hp'].browse(docids)
        docargs = {
            'doc_ids': docids,
            'doc_model': 'account.hp',
            'data': data,
            'docs': hp,
            'time': time,
            'amount_total' : self.__amount_total__,
            'ending_date' : self.__ending_date__(docids),
            'get_capital': self.__get_capital__,
            'get_interest':self.__get_interest__,
            'get_subtotal':self.__get_subtotal__,
        }
        return docargs

    def __amount_total__(self,install):
        self._capital = self._capital + install.capital
        self._interest = self._interest + install.interest
        self._subtotal= self._subtotal + install.capital + install.interest
        self.s = self.s + install.total
        return self.s

    def __get_capital__(self,install):
        return self._capital

    def __get_interest__(self,install):
        return self._interest

    def __get_subtotal__(self,install):
        return self._subtotal

    def __ending_date__(self, id ):
        hp_search =self.env['account.hp'].search([("id","in",id)])
        start_date = hp_search[0].approve_date
        total_inst = hp_search[0].total_installment
        date = ""
        end_date = ""
        i = 366
        j = 12
        lang_code = self.env.context.get('lang') or self.env.user.lang
        lang = self.env['res.lang'].search([('code', '=', lang_code)], limit=1)
        if j == total_inst and start_date:
            if start_date:
                d = start_date
                date_1 = datetime.date.strftime(d, str(lang.date_format))
                end_date = datetime.datetime.strptime(date_1, str(lang.date_format)) + datetime.timedelta(days=i)
                end_date = datetime.date.strftime(end_date, str(lang.date_format))
        else:
            while j < total_inst:
                j = j + 12
                i = i + 365
                if start_date:
                    d = start_date
                    date_1 = datetime.date.strftime(d, str(lang.date_format))
                    end_date = datetime.datetime.strptime(date_1, str(lang.date_format)) + datetime.timedelta(days=i)
                    end_date = datetime.date.strftime(end_date, str(lang.date_format))
        if end_date:
            date = end_date
        return date
