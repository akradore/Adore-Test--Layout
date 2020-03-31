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
from odoo import fields, api, models
from datetime import date

class PartnerHP(models.AbstractModel):
    _name = 'report.hire_purchase.partner_hp'
    _description = "Report hire_purchase partner_hp"
    s=0.0
    _capital=0.0
    _interest=0.0
    _subtotal=0.0

    def _get_report_values(self, docids, data=None):
        hp = self.env['account.hp'].browse(docids)
        docargs = {
            'doc_ids': docids,
            'doc_model': 'account.hp',
            'data': data,
            'docs': hp,
            'time': time,
            'get_hp':self.__get_hp__,
            'ending_date' : self.__ending_date__,
            'installment': self.__installment__,
            'get_capital': self.__get_capital__,
            'get_interest':self.__get_interest__,
            'get_subtotal':self.__get_subtotal__,
        }
        return docargs

    def __get_hp__(self, partner_id):

        tc = self.env['account.hp']
        ids = tc.search(self._cr, self._uid, [('partner_id','=',partner_id)])
        res = []
        for hp in tc.browse(self._cr, self._uid, ids, {'partner_id':partner_id}):
            res.append(hp)
        return res

    def __installment__(self,install):

        self._capital=self._capital+ install.capital
        self._interest= self._interest+install.interest
        self._subtotal= self._subtotal + install.capital + install.interest
        return install.total

    def __get_capital__(self,hp):
        self.cr.execute("SELECT SUM(capital) from account_hp_installment where \
                        account_hp_installment.hp_id=" +str(hp.id))
        return self.cr.fetchone()[0] or 0.0

    def __get_interest__(self,hp):
        self.cr.execute("SELECT SUM(interest) from account_hp_installment where \
                        account_hp_installment.hp_id=" +str(hp.id))
        return self.cr.fetchone()[0] or 0.0

    def __get_subtotal__(self,hp):
        self.cr.execute("SELECT SUM(total) from account_hp_installment where \
                        account_hp_installment.hp_id=" +str(hp.id))
        return self.cr.fetchone()[0] or 0.0

    def __ending_date__(self,hp):

        start_date = hp.approve_date
        total_inst = hp.total_installment
        i = 366
        j = 12
        lang_code = self.env.context.get('lang') or self.env.user.lang
        lang = self.env['res.lang'].search([('code', '=', lang_code)])
        if j == total_inst:
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
        return end_date
