from odoo import api, fields, models, _


class Stores(models.Model):
    _name = "stores"
    _description = "Stores"

    name = fields.Char('Store Name', required=True, translate=True)
    store_code = fields.Char('Store Code', required=True)
    active = fields.Boolean(default=True,
                            help="If the active field is set to false, it will allow you to hide the Sales Team without removing it.")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env['res.company']._company_default_get('stores'))
    currency_id = fields.Many2one(
        "res.currency", related='company_id.currency_id',
        string="Currency", readonly=True)
    user_id = fields.Many2one('res.users', string='Store Manager')
    analytic_tag_id = fields.Many2one('account.analytic.tag', string='Analytic Tag')
    member_ids = fields.One2many('res.users', 'store_team_id', string='Channel Members')
    partner_id = fields.Many2one('res.partner', string='Store Location')
    store_warehouse_ids = fields.Many2many('store.warehouse',string="Warehouse")
    payment_ids = fields.One2many("account.journal", "store_id", string="Payment")

    @api.model
    def create(self, vals):
        res = super(Stores, self).create(vals)
        analytic_id = self.env['account.analytic.tag'].search([('name', '=', res.name)])
        if not analytic_id:
            analytic_id = self.env['account.analytic.tag'].create({'name': res.name})
        res.analytic_tag_id = analytic_id
        return  res

    def write(self, vals):
        res = super(Stores, self).write(vals)
        if vals.get('name'):
            analytic_id = self.env['account.analytic.tag'].search([('name', '=', vals.get('name'))])
            if not analytic_id:
                analytic_id = self.env['account.analytic.tag'].create({'name': vals.get('name')})
            self.analytic_tag_id = analytic_id
        return res

    @api.model
    # @api.returns('self', lambda value: value.id if value else False)
    def _get_default_team_id(self, user_id=None):
        if not user_id:
            user_id = self.env.uid
        company_id = self.with_user(user_id).env.user.company_id.id
        team_id = self.env['stores'].sudo().search([
                ('member_ids', '=', user_id),
            '|', ('company_id', '=', False), ('company_id', 'child_of', [company_id])], limit=1)
        if not team_id:
            default_team_id = self.env['stores'].search([],limit=1)
            if default_team_id:
                team_id = default_team_id
        return team_id if team_id else False
