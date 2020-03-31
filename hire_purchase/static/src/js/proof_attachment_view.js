odoo.define('hire_purchase.proof_attachment_preview',function(require){
"use strict";
    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');
    var core = require('web.core')
    var qweb = core.qweb
    var attachment_preview = AbstractField.extend({
        template:'hire_purchase.attachment_preview_template',
        events:{
            'click .attachment_preview_btn':'_onPreviewClick',
        },
        init: function () {
            this._super.apply(this, arguments);
            var self = this
        },
        _onPreviewClick: function(event){
            event.preventDefault()
            var self = this
            var attachment_name = self.recordData.attachment_id.data.display_name
            attachment_name = attachment_name.split('.')[1]
            var modal = qweb.render('attachment_preview_modal',{attachment_url:this.recordData.attachment_url,attch_type:attachment_name})
            $(modal).modal()
            return false
        }
    })
    field_registry.add('attachment_preview',attachment_preview)
    return attachment_preview
});