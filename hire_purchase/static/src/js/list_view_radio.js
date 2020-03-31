odoo.define('hire_purchase.quick_check_listview_extended',function(require){
"use strict";
    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');
    var TreeViewRadio = AbstractField.extend({
        template:'hire_purchase.TreeViewRadio',
        events:{
            'change .quick_check_offer_radio':'_onRadioClick',
        },
        init:function(){
            var self = this
            this._super.apply(this, arguments);
        },
        _render:function(){
            var self = this
            var res = this._super.apply(this, arguments);
            self.$el.find('input')[0].id=self.dataPointID
            if(self.recordData.is_selected_offer)
                self.$el.find('input')[0].checked=true
            return res
        },
        _onRadioClick:function(){
            var self = this
            self._resetValues()
            self._setValue({'is_selected_offer':true})
         },
         _resetValues: function(){
            var self = this
            var allFieldWidgets = self.getParent().allFieldWidgets
            _.each(allFieldWidgets,function(record){
                record[0]._setValue(false)
            });

         }
    });
    field_registry.add('tree_view_radio',TreeViewRadio)
    return TreeViewRadio
});

odoo.define("'hire_purchase.quick_check_listview_render'",function(require){
    var ListRenderer = require('web.ListRenderer');
    ListRenderer.include({
        _registerModifiers:function(node, record, element, options){
            var self = this
            var res = this._super.apply(this, arguments);
            if(node.attrs.name == 'is_selected_offer' && element && element.$el){
                element.$el.removeClass('o_field_empty')
            }
            return res
         }
    });
})
