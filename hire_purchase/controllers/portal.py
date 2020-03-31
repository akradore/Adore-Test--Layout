# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class PortalAccountHP(CustomerPortal):
    

    def _prepare_portal_layout_values(self):
        values = super(PortalAccountHP, self)._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        AccountHP = request.env['account.hp']
        hp_count = AccountHP.search_count([
        ])

        values.update({
            'hp_count': hp_count,
        })
        return values
    # ------------------------------------------------------------
    # My HPs
    # ------------------------------------------------------------
 
    def _hp_get_page_view_values(self, hp, access_token, **kwargs):
        values = {
            'page_name': 'hp',
            'hp': hp,
        }
        return self._get_page_view_values(hp, access_token, values, 'my_hp_history', False, **kwargs)
# 
    @http.route(['/my/hps', '/my/hps/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_hp(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        AccountHP = request.env['account.hp']
        domain = []
        searchbar_sortings = {
            'date': {'label': _('Apply Date'), 'order': 'apply_date desc'},
            'name': {'label': _('Reference'), 'order': 'name desc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        archive_groups = self._get_archive_groups('account.hp', domain)
        hp_count = AccountHP.search_count(domain)
        pager = portal_pager(
            url="/my/hps",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=hp_count,
            page=page,
            step=self._items_per_page
        )
        hps = AccountHP.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_hp_history'] = hps.ids[:100]
        values.update({
            'date': date_begin,
            'hps': hps,
            'page_name': 'hp',
            'pager': pager,
            'archive_groups': archive_groups,
            'default_url': '/my/hps',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("hire_purchase.portal_my_hps", values)
    
    
    @http.route(['/my/hps/<int:hp_id>'], type='http', auth="public", website=True)
    def portal_my_hp_detail(self, hp_id, access_token=None, report_type=None, download=False, **kw):
        try:
            invoice_sudo = self._document_check_access('account.hp', hp_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
 
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='account.account_invoices', download=download)
 
        values = self._hp_get_page_view_values(invoice_sudo, access_token, **kw)
        return request.render("account.portal_invoice_page", values)

        return request.render('doyenne_theme.portal_membership_page', values)
 
