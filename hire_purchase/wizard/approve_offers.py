from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ApproveOffers(models.TransientModel):
    _name = 'approve.offers'
    _description = "Offers to approve application"

    offer_ids = fields.One2many("hp.offer", inverse_name="approve_offers_id", string = "Offers")
    hp_account_id = fields.Many2one("account.hp", string="Account HP",)
    cancel_reason = fields.Char(string="Reason for Cancel", )
    hp_application_status = fields.Char(string="Application Status",)
    hp_queue_code= fields.Char(string="Queue Code",)
    hp_queue_description = fields.Char(string="Queue Description", )


    def cancel_hp(self):
        status = self._context.get('api_action',False)
        if not status:
            raise UserError(_("Application takenup status not found"))

        if status == 'cancel':
            stage = 'hp_to_cancelled'
        elif status == 'decline':
            stage = 'hp_to_declined'
        api_status = 'Declined'

        req_data = self.hp_account_id._prepare_application_take_up(status=api_status,reason=self.cancel_reason)
        cancel_state = self.env.ref('hire_purchase.{0}'.format(stage)).id or False
        response = self.env['frontier.api.calls']._application_taken_up(body=req_data)

        if response:
            self.hp_account_id.write({'stage_reason': self.cancel_reason,'state': 'cancel','stage_id':cancel_state})

    def approve_hp_application(self):
        offer = self.offer_ids.filtered(lambda x:x.is_selected_offer)
        if not len(offer):
            raise UserError(_("Please select an offer"))
        context = self._context
        account_hp = self.env[context.get('active_model')].browse(context.get('active_id'))
        hp_period = self.env['hp.installment.period'].search([('period','=',offer.term)]).id
        account_hp.write({
            'selected_offer_id':offer.offer_id,
            'interest_rate':offer.interest_rate,
            'interest':offer.interest,
            'hp_period':hp_period,
            'initiation_fee':offer.initiation_fee,
        })
        account_hp.installment_id.unlink()
        account_hp.add_installment_line(offer=offer)
        installment_dates = account_hp.installment_id.sorted('date').mapped('date')
        if len(installment_dates):
            values = {"contract_term":offer.term,
                     "sale_value_inc":account_hp.sale_order_id.amount_total,
                     "contract_value_inc":(account_hp.sale_order_id.amount_total - (account_hp.deposit_amt + account_hp.initiation_fee)),
                     "approve_finance_charges":(account_hp.finance_charges * offer.term),
                     "monthly_service_fee":account_hp.finance_charges,
                     "first_payment_date":installment_dates[0],
                     "final_payment_date":installment_dates[-1],
                     "monthly_service_fee":account_hp.finance_charges,
                     "monthly_insurance_cost":offer.insurance_amt,
                     "total_monthly_instalment":offer.instalment,
                     "first_payment_date":installment_dates[0],
                     "final_payment_date":installment_dates[-1],
            }
            account_hp.write(values)
        account_hp.stage_id = self.env.ref('hire_purchase.hp_to_contract_deposit').id or account_hp.stage_id.id
        account_hp.sale_order_id.hp_approved = True
