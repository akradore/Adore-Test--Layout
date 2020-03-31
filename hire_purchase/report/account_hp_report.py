# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models


class AccountHPReport(models.Model):
    _name = "account.hp.report"
    _description = "HP Detail Statistics"
    _auto = False

    hp_id = fields.Char('HP Number', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Partner', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', 'Salesperson', readonly=True)
    hp_amt = fields.Float('Amount', readonly=True)
    approve_amount = fields.Float('Disbursement Amount', readonly=True)
    country_id = fields.Many2one('res.country', 'Partner Country', readonly=True)
    approve_date = fields.Date('Approve Date', readonly=True)
    duration = fields.Integer('Terms Duration', readonly=True)
    principle = fields.Float('Principle Amount', readonly=True)
    total_disbursed = fields.Float('Disbursed Amount', readonly=True)
    payment_freq = fields.Selection([('monthly','Monthly'), ('quarterly','Quarterly'), ('half_yearly','Half-Yearly'),('yearly','Yearly')], "Payment Frequency", readonly=True)
    state = fields.Selection([
                           ('draft', 'Apply'),
                           ('apply', 'HP Sanctioned'),
                           ('partial', 'Partially Disbursed'),
                           ('approved', 'HP Disbursed'),
                           ('done', 'Closed'),
                           ('cancel', 'Reject'),
                        ], 'State', readonly=True )
    
    def _select(self):
        select_str = """

            SELECT min(al.id) as id,
            al.partner_id,
            al.company_id,
            al.hp_id,
            al.approve_date,
            al.approve_amount,
            al.req_amt,
            al.hp_amt,
            al.payment_freq,
            al.user_id,
            al.state,
            partner.country_id,
            sum(ail.capital) as principle
        """
        return select_str

    def _from(self):
        from_str = """
                account_hp_installment ail
                      join account_hp al on (ail.hp_id=al.id)
                      join res_partner partner on al.partner_id = partner.id
        """
        return from_str

    def _group_by(self):
        group_by_str = """
            GROUP BY ail.hp_id,
            al.partner_id,
            al.company_id,
            al.hp_id,
            al.approve_date,
            al.req_amt,
            al.approve_amount,
            al.hp_amt,
            al.payment_freq,
            al.user_id,
            al.state,
            partner.country_id

        """
        return group_by_str

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """CREATE or REPLACE VIEW %s as (
            %s
            FROM ( %s )
            %s
            )""" % (self._table, self._select(), self._from(), self._group_by())
        self.env.cr.execute(query)
        
        


