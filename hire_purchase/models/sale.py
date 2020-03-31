import requests
import json
from odoo.exceptions import UserError, ValidationError, Warning
from odoo import api, fields, models, _
from datetime import datetime, date


class account_payment(models.Model):
    _inherit = "account.payment"

    @api.onchange('currency_id')
    def _onchange_currency(self):
        if self._context.get('from_sale_order'):
            order_id = self.env['sale.order'].browse(self._context.get('active_id'))
            self.amount = order_id.amount_total
        else:
            self.amount = abs(
                self._compute_payment_amount(self.invoice_ids, self.currency_id, self.journal_id, self.payment_date))
        if self.journal_id:  # TODO: only return if currency differ?
            return

        # Set by default the first liquidity journal having this currency if exists.
        domain = [('type', 'in', ('bank', 'cash')), ('currency_id', '=', self.currency_id.id)]
        if self.invoice_ids:
            domain.append(('company_id', '=', self.invoice_ids[0].company_id.id))
        journal = self.env['account.journal'].search(domain, limit=1)
        if journal:
            return {'value': {'journal_id': journal.id}}

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_default_store(self):
        return self.env['stores']._get_default_team_id()

    sale_type = fields.Selection([('cash', 'Cash'),
                                  ('lay_by', 'Lay-By'),
                                  ('hire_purchase', 'Hire Purchase')],
                                   string='Sale Type' ,default='cash', required=True)
    store_id = fields.Many2one('stores', string='Store', change_default=True, default=_get_default_store)
    partner_credit = fields.Monetary(related='partner_id.credit', string='Partner Credit')
    is_partner_credit = fields.Boolean(string="Is Partner Credit", compute='_compute_is_credit')
    maximum_deal_amount = fields.Float(string="Maximum Deal Amount")
    hp_count = fields.Integer(string="Number of HP Accounts", compute='_compute_HP')
    hp_ids = fields.One2many('account.hp', 'sale_order_id', string='Account HP')
    hp_approved = fields.Boolean(string='HP Approved', compute='_compute_HP')
    hp_type = fields.Many2one('account.hp.hptype', 'Agreement Type', track_visibility='onchange')
    hp_period = fields.Many2one('hp.installment.period', 'HP Period', track_visibility='onchange')
    is_gpi = fields.Boolean(string='Goods Protection Insurance')
    is_cli = fields.Boolean(string='Credit Life Insurance', default=True)

    hp_amt = fields.Float(related='hp_ids.hp_amt', string='Amount ', digits=(12, 2), required=True, track_visibility='onchange')
    month = fields.Integer(related='hp_ids.month', string='Tenure (Months)', track_visibility='onchange')
    int_rate = fields.Float(related='hp_ids.int_rate', string='Interest Rate', digits=(12, 2), default=1, track_visibility='onchange')
    emi_cal = fields.Float(related='hp_ids.emi_cal', string='Calculated Monthly EMI', readonly=True)
    tot_amt = fields.Float(related='hp_ids.tot_amt', string='Total Amount with Interest', readonly=True)
    flat_pa = fields.Float(related='hp_ids.flat_pa', string='Flat Interest Rate PA', readonly=True)
    flat_pm = fields.Float(related='hp_ids.flat_pm', string='Flat Interest Rate PM', readonly=True)
    tot_int_amt = fields.Float(related='hp_ids.tot_int_amt', string='Total Interest Amount', readonly=True)
    yr_int_amt = fields.Float(related='hp_ids.yr_int_amt', string='Yearly Interest Amount', readonly=True)

    flat_emi_cal = fields.Float(related='hp_ids.flat_emi_cal', string='Calculated FLat Monthly  EMI', readonly=True)
    flat_tot_amt = fields.Float(related='hp_ids.flat_tot_amt', string='Total Flat Amount with  Interest', readonly=True)
    flat_pa1 = fields.Float(related='hp_ids.flat_pa1', string='Flat Interest Rate PA1', readonly=True)
    flat_pm1 = fields.Float(related='hp_ids.flat_pm1', string='Flat Interest Rate  PM1', readonly=True)
    flat_tot_int_amt = fields.Float(related='hp_ids.flat_tot_int_amt', string='Total Flat Interest  Amount', readonly=True)
    flat_yr_int_amt = fields.Float(related='hp_ids.flat_yr_int_amt', string='Yearly Flat Interest  Amount', readonly=True)

    approved_deposit = fields.Float(string="Approved Deposit",)
    deposit_overrider_reason= fields.Char(string="Deposit Overrider Reason",)
    deposit_approval_code = fields.Char(string="Deposit Approval Code",)
    override_type = fields.Selection(string="Deposit Override Type", selection=[('head_office', 'Head Office'),
                                                                                ('store_manager', 'Store Manager'),])

    @api.depends('amount_total', 'partner_credit', 'hp_ids', 'sale_type')
    def _compute_is_credit(self):
        for record in self:
            record.is_partner_credit = False
            if record.sale_type in ['cash', 'lay_by'] and record.amount_total <= (record.partner_credit * -1):
                record.is_partner_credit = True
            elif record.sale_type == 'hire_purchase':
                record.hp_type = record.partner_id.id and record.partner_id.hp_agreement_type.id or False
                if record._origin.hp_ids.deposit_amt and record._origin.hp_ids.deposit_amt <= (record.partner_credit * -1):
                    record.is_partner_credit = True

    @api.depends('hp_ids')
    def _compute_HP(self):
        for each in self:
            hps = each.mapped('hp_ids')
            each.hp_count = len(hps)
            each.hp_approved = any([line for line in each.hp_ids if line.state == 'apply'])

    def action_sale_register_payment(self):
        partner_id = self.partner_id.parent_id.id if self.partner_id.parent_id else self.partner_id.id
        view_id = self.env.ref('hire_purchase.inherit_view_account_payment_form').id
        payment_method = self.env.ref('account.account_payment_method_manual_in').id
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.payment',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'from_sale_order' : True,
                'default_payment_type': 'inbound',
                'default_partner_id': partner_id,
                'default_payment_method_id': payment_method,
                'default_communication': self.name,
            }
        }
    #     return self.env['account.payment'] \
    #         .with_context(active_ids=self.ids, active_model='sale.order', active_id=self.id) \
    #         .action_register_payment()
    #
    # def action_register_payment(self):
    #     print("self======>",self.env.context)
    #     active_ids = self.env.context.get('active_ids')
    #     print("active_ids========>", active_ids)
    #     if not active_ids:
    #         return ''


    def submit_hp_application(self):
            '''
                Opens the form view of hp.loan to create it,and pass on the context fields defined
            '''
            if self.id:
                view_id = self.env.ref('hire_purchase.account_hp_form').id
                return {
                    'name': _('HP Account Application'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'account.hp',
                    'view_id': view_id,
                    'views': [(view_id, 'form')],
                    'target': 'current',
                    'context': {
                        'default_name': self.name,
                        'default_partner_id': self.partner_id.id,
                        'default_apply_date': date.today(),
                        'default_return_type': 'cash',
                        'default_payment_freq': 'monthly',
                        'default_user_id': self.user_id.id,
                        'default_repayment_basis': 'sanctioned_amt',
                        'default_comapny_id': self.company_id.id,
                        'default_store_id': self.store_id.id,
                        'default_req_amt': self.amount_total,
                        'default_hp_type': self.hp_type.id,
                        'default_hp_period': self.hp_period.id,
                        'default_is_gpi': self.is_gpi,
                        'default_is_cli': self.is_cli,
                        'default_sale_order_id': self.id,
                    }
                }

    def action_view_HP(self):
        '''
             Opens the tree view of hp.loan to show HP Account Records
        '''
        self.ensure_one()
        action = self.env.ref('hire_purchase.action_all_hp_accounts').read()[0]
        loans = self.mapped('hp_ids')
        if len(loans) > 1:
            action['domain'] = [('sale_order_id', '=', self.id)]
        elif loans:
            action['views'] = [(self.env.ref('hire_purchase.account_hp_form').id, 'form')]
            action['res_id'] = loans.id
        return action

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update({'sale_type': self.sale_type,
                    'store_id': self.store_id.id})
        return res

    @api.onchange('store_id')
    def onchange_store(self):
        for record in self:
            warehouse = False
            if record.store_id.id and len(record.store_id.store_warehouse_ids):
                 warehouse = record.store_id.store_warehouse_ids.mapped('warehouse_id')[0]
            record.warehouse_id = warehouse
        return {
            'domain':{
                'warehouse_id':[('id','in',self.store_id.mapped('store_warehouse_ids.warehouse_id.id'))]
            }
        }

    @api.onchange('company_id')
    def onchange_company(self):
        for record in self:
            if record.store_id.id and len(record.store_id.store_warehouse_ids):
                record.warehouse_id = record.store_id.store_warehouse_ids.mapped('warehouse_id')[0]

    def onchange_method(self):
        self.field_name = ''
    def open_deposite_form(self):
        if not len(self.order_line.ids):
            raise ValidationError(_("Please add order line"))
        if self.amount_total > self.maximum_deal_amount:
            raise ValidationError(_("Please ensure that the Order total is less than the Maximum Deal Amount"))
        if not self.delivery_set:
            raise ValidationError(_(
                "With all HP sales it is compulsory that Astra do the delivery. Please add delivery to the quotation."))

        view_id = self.env.ref('hire_purchase.quickcheck_offer_deposite_wizard_form_view').id

        return {
            'name': _('QuickCheck Offer Deposite'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'quickcheck.offer.result',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_order_amount': self.amount_total,
                'default_deposit_slider':self.hp_type.id and int(self.hp_type.deposit_percentage) or 0,
            }
        }


    def write(self,values):
        if values.get('date_order',False) and self.date_order != False:
            values.pop('date_order')
        return super(SaleOrder,self).write(values)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def default_get(self, fields):
        res = super(SaleOrderLine, self).default_get(fields)
        store_id = self.env['stores'].browse(self._context.get('store_id', False))
        analytic_tag = []
        if store_id.analytic_tag_id.id and store_id:
            analytic_tag = [store_id.analytic_tag_id.id]
        res.update({'analytic_tag_ids': [(6, 0, analytic_tag)]})
        return res
