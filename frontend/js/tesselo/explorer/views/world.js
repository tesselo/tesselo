define([
        'marionette'
    ], function(
        Marionette
    ){
    var WorldChoiceView = Marionette.View.extend({
        template: _.template('<%= name %>'),
        className: 'list-group-item',
        events: {'click': 'toggle'},
        toggle: function(){
            if(this.$el.hasClass('active')){
                this.$el.siblings().removeClass('hidden');
            } else {
                this.$el.addClass('active').siblings().removeClass('active').addClass('hidden');
                this.trigger('world-changed', this.model)
            }
        }
    });

    return Marionette.CollectionView.extend({
        className: 'list-group',
        childView: WorldChoiceView
    });
});

