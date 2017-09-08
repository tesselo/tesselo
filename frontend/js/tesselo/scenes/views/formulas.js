define([
        'marionette'
    ], function(
        Marionette
    ){
    var FormulaChoiceView = Marionette.View.extend({
        template: _.template('<%= name %>'),
        className: 'btn btn-default btn-sm',
        tagName: 'button',
        events: {'click': 'toggle'},
        toggle: function(){
            if(!this.$el.hasClass('active')){
                this.$el.addClass('active').siblings().removeClass('active');
                this.trigger('formula-changed', this.model)
            }
        }
    });

    return Marionette.CollectionView.extend({
        className: 'btn-group',
        childView: FormulaChoiceView
    });
});

