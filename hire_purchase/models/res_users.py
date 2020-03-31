from odoo import models,fields,api,_
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'


    store_team_id = fields.Many2one(
        'stores', "User's Stores",
        help='Stores the user is member of. Used to compute the members of a Stores through the inverse one2many')
    override_code = fields.Char(string="Overrider Code",)

    def get_logged_name(self):
        user = self.env['res.users'].browse(self._context.get('uid'))
        name = ''
        if user:
            name = user.partner_id.display_name if user.partner_id else user.name
        return name

    @api.constrains('override_code')
    def _check_ovverider_code(self):
        existing_code = self.search([('override_code','=',self.override_code),('id','!=',self.id)]) or []
        if len(existing_code):
            raise ValidationError(_("This ovveride code is already assigned"))