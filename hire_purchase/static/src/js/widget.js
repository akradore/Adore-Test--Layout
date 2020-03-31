odoo.define('aspl_float_slider.widget', function(require) {
    "use strict";
    var core = require('web.core');
    var widget = require('web.basic_fields');
    var fieldRegistry = require('web.field_registry');
    var FieldRange = widget.FieldFloat.extend({
        template : 'FieldRange',
        events:{
            'change input[type="range"]':'_onChange',
            'click .button-plus':'_addValue',
            'click .button-minus': '_minusValue',
            },
        init: function () {
            this._super.apply(this, arguments);
            var self = this
        },
        _getValue : function() {
           return this.$('input').val();
          },
        _onChange : function() {
          if (!this.$silent) {
            var default_min = this.record.context["default_deposit_slider"]
            if( parseInt(this._getValue()) < default_min){
                this.$el.find('input').val(default_min)
                this._setValue(this._getValue())
                return
            }
            if (this.mode === 'edit' && this.$('input').val() !== '') {
                 this._setValue(this._getValue());
                    }
             }
          },
        _addValue:function(){
            var self = this
            this.$el.find('#myRange').val(parseInt(this.$el.find('#myRange').val() )+1)
            this._onChange()
        },
        _minusValue:function(){
            var self = this
            this.$el.find('#myRange').val(this.$el.find('#myRange').val() - 1)
            this._onChange()
        },
        _render : function() {
            var show_value = this.value;
            var $input = this.$el.find('input');
            var $span = this.$el.find('.notification_val');
            $input.mousemove(function(e) {
              if (e.buttons == 1) {
                 $span.html($input.val());
              }
            });
               $span.html(show_value);
               $input.val(show_value);
          },

    });
    fieldRegistry.add('range', FieldRange);
    return {
       FieldRange : FieldRange
    };
});
