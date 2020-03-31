
# !/usr/bin/env python
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
from odoo import fields ,models ,api, _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from datetime import date
import math
import json
import webbrowser

class AccountHPProofType(models.Model):
    _name ="account.hp.proof.type"
    _description = "Account HP Proof Type"

    name = fields.Char('Proof Type Name' ,size=64 ,required=True)
    shortcut = fields.Char("Shortcut" ,size=32 ,required=True)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        acc_hp_proof_obj = self.env['account.hp.hptype']
        acc_proof_ids = []
#         if self._context and self._context.has_key('loan_type'):
        if self._context and 'hp_type' in self._context:
            for record in acc_hp_proof_obj.browse(int(self._context['hp_type'])).prooftypes:
                if record.name:
                    acc_proof_ids.append(record.id)
            args.append(['id', 'in', acc_proof_ids])
        return super(AccountHPProofType, self)._search(args, offset=offset, limit=limit, order=order ,count=count, access_rights_uid=access_rights_uid)


class AccountHPProof(models.Model):
    _name ='account.hp.proof'
    _description = "Account HP Proof"

    proof_name = fields.Char('Proof name' ,size=256 ,)
    hp_id = fields.Many2one('account.hp', 'HP' ,)
    note = fields.Text('Proof Note')
    document = fields.Binary('Proof Document')
    file_name = fields.Char(string="Filename")
    type = fields.Many2one('account.hp.proof.type' ,'Type')
    upload_status = fields.Boolean(string="Upload Status", default=False)
    state =  fields.Selection(
        [
            ('draft' ,'Draft'),
            ('apply' ,'Under Verification'),
            ('done' ,'Verified'),
            ('cancel' ,'Cancel')
        ] ,'State', readonly=True, index=True ,default = 'draft')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    attachment_url = fields.Char(string="Attachment URL",)

    @api.onchange('hp_id','type')
    def onchange_proofs(self):
        if self.type.id:
            self.proof_name = self.type.display_name
        elif len(self.hp_id.mapped('proof_id.id')):
            return {'domain' :{'type' :[('id' ,'not in', self.mapped('hp_id.proof_id.type.id'))]}}


    def apply_varification(self):
        for record in self:
            record.state = 'apply'

    def proof_varified(self):
        for record in self:
            if record.hp_id.id and not record.hp_id.controller_id.id:
                raise ValidationError(_("Please Assign Controller & Verify Documents "))
            record.state = 'done'

    def proof_canceled(self):
        for record in self:
            if record.hp_id.id and not record.hp_id.controller_id.id:
                raise ValidationError(_("Please Assign Controller & Verify Documents "))
        self.state = 'cancel'

    def _prepare_attachment(self ,datas=False,file_name=''):
        return self.env['ir.attachment'].create({
            'name': self.file_name or file_name,
            'datas': datas or self.document,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })

    @api.model
    def create(self, values):
        if self.type.browse(values.get('type')).shortcut == 'PIC' and values.get('file_name').split('.')[
            -1].lower() not in ['png', 'jpg']:
            raise UserError(_("Only image file is allowed for Customer's Photo"))

        if values.get('document') and values.get('file_name'):
            attachment = self._prepare_attachment(values.get('document'), values.get('file_name'))
            values.update({'attachment_id': attachment.id, 'attachment_url': attachment.local_url, 'state': 'apply'})
            values.update(file_name=self.update_file_name(values.get('file_name')))
        res = super(AccountHPProof, self).create(values)
        if res.type.shortcut.lower() == 'sca':
            res.state = 'done'
        return res

    def update_file_name(self,file_name=False):
        if file_name:
            file_name = file_name.split('.')
            file_name [-1] = '.'+(file_name[-1].lower() == 'jpg' and 'jpeg' or file_name[1])
            return "".join(file_name)

    def write(self ,values):
        for record in self:
            if record.type.shortcut == 'PIC' and (record.file_name or '').split('.')[-1].lower() not in ['png','jpg','jpeg']:
                raise UserError(_("Only image file is allowed for Customer's Photo"))

            if values.get('document' ,False):
                if record.attachment_id.id:
                    record.attachment_id.datas = values.get('document')
                    record.attachment_id.name = values.get('file_name')
                else:
                    attachment = record._prepare_attachment(values.get('document'),values.get('file_name'))
                    record.attachment_id = attachment.id
                    record.attachment_url = attachment.local_url
                values.update(state='apply')
            file_name = values.get('file_name',False)
            if file_name:
                values.update(file_name = record.update_file_name(values.get('file_name')))
        return super(AccountHPProof ,self).write(values)


    def unlink(self):
        for record in self:
            if record.attachment_id.id:
                record.attachment_id.unlink()
        return super(AccountHPProof ,self).unlink()
