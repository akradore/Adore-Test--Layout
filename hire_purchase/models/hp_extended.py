from odoo import fields, models, api, _

class HPAccountExtended(models.TransientModel):
    _name = "hp.extended"
    _description = "Extended HP Account period"

    date = fields.Date('Date', default=fields.Date.today())
    period_id = fields.Many2one('hp.installment.period', 'HP Account Period')

    def extend_period(self):
        for hp in self._context['active_ids']:
            hp_id = self.env['account.hp'].browse(hp)
            if hp_id.hp_period.id != self.period_id.id:
                hp_id.hp_period = self.period_id.id
                hp_id.total_installment = self.period_id.period

                wizard_id = self.env['hp.disbursement.wizard'].create({
                    'disbursement_amt': hp_id.hp_amount,
                    'name': 'Extended Period',
                    'date': self.date,
                })
                wizard_id.with_context({'is_extended': True, 'active_id': hp_id.id, 'date': self.date}).approve_hp()

        return