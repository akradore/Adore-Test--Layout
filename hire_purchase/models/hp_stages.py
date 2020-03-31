from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval


class LoanStages(models.Model):
    _name = 'hp.stages'
    _description = 'HP Stage'
    _order = 'sequence, id'
    

    name = fields.Char(string='Stage Name', required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=1)
    legend_priority = fields.Char(
        string='Starred Explanation', translate=True,
        help='Explanation text to help users using the star on tasks or issues in this stage.')
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda s: _('Blocked'), translate=True, required=True,
        help='Override the default value displayed for the blocked state for kanban selection, when the HP is in that stage.')
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda s: _('Ready for Next Stage'), translate=True, required=True,
        help='Override the default value displayed for the done state for kanban selection, when the HP is in that stage.')
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda s: _('In Progress'), translate=True, required=True,
        help='Override the default value displayed for the normal state for kanban selection, when the HP is in that stage.')
    mail_template_id = fields.Many2one('mail.template', string='Email Template', domain=[('model', '=', 'account.hp')],
                        help="If set an email will be sent to the customer when the Loan reaches this step.")
    fold = fields.Boolean(string='Folded in Kanban',
                    help='This stage is folded in the kanban view when there are no records in that stage to display.')
    
    state = fields.Selection([
               ('draft', 'Application Review'),
               ('apply', 'Application Approved'),
               ('partial', 'Partially Disbursed'),
               ('approved', 'Disbursed'),
               ('done', 'Closed'),
               ('cancel', 'Declined'),
                ], 'HP State', index=True)
    