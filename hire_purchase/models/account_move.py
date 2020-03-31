from odoo import fields, models, api, _
from datetime import date
import datetime


class AccountMove(models.Model):
    _inherit = 'account.move'

    store_id = fields.Many2one('stores', string='Store')
    sale_type = fields.Selection([('cash', 'Cash'),
                                  ('lay_by', 'Lay-By'),
                                  ('hire_purchase', 'Hire Purchase')],
                                 string='Sale Type')
    hp_count = fields.Integer(string="HP Account", compute='_compute_HP')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.store_id and res.store_id.analytic_tag_id:
            for line in res.line_ids:
                line.update({'analytic_tag_ids': [(6, 0, [res.store_id.analytic_tag_id.id])]})
        return res

    def _compute_HP(self):
        self.ensure_one()
        sale_line_ids = self.invoice_line_ids.mapped('sale_line_ids')
        sale_order_id = self.env['sale.order'].search([('order_line', 'in', sale_line_ids.ids)])
        if sale_order_id:
            hps = sale_order_id.mapped('hp_ids')
            self.hp_count = len(hps)
        else:
            self.hp_count = 0

    def action_open_hp_records(self):
        self.ensure_one()
        sale_line_ids = self.invoice_line_ids.mapped('sale_line_ids')
        sale_order_id = self.env['sale.order'].search([('order_line', 'in', sale_line_ids.ids)])
        if sale_order_id:
            action = self.env.ref('hire_purchase.action_all_hp_accounts').read()[0]
            loans = sale_order_id.mapped('hp_ids')
            if len(loans) > 1:
                action['domain'] = [('id', 'in', sale_order_id.mapped('hp_ids').ids)]
            elif loans:
                action['views'] = [(self.env.ref('hire_purchase.account_hp_form').id, 'form')]
                action['res_id'] = loans.id
            return action
        return False



class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    acc_hp_id = fields.Many2one('account.hp', 'Customer')
    hp_instalment_id = fields.Many2one('account.hp.installment','Instalment')

    # @api.model
    # def create(self, vals):
    #     res = super(AccountMoveLine, self).create(vals)
    #     print("res=======>", res)
        # analytic_tag = []
        # if self.move_id.store_id and self.move_id.store_id.analytic_tag_id.id:
        #     analytic_tag = [self.move_id.store_id.analytic_tag_id.id]
        #     print("analytic_tag==========>", analytic_tag)
        # res.update({'analytic_tag_ids': [(6, 0, analytic_tag)]})
        # print("res======>", res)
        # return res
