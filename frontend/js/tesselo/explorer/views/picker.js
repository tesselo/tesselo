define([
        'marionette',
        'text!../templates/picker.html'
    ], function(
        Marionette,
        template
    ){
    var ColorChoiceView = Marionette.View.extend({
        template: _.template(template),
        className: 'list-group-item',
        events: {'click': 'toggle'},
        toggle: function(){
            if(this.$el.hasClass('selected')){
                this.$el.removeClass('selected').siblings().addClass('active');
            } else {
                this.$el.addClass('selected').addClass('active').siblings().removeClass('active');
                this.trigger('colors-changed')
            }
        }
    });

    return Marionette.CollectionView.extend({
        className: 'list-group',
        childView: ColorChoiceView,
        initialize: function(){
            _.bindAll(this, 'setColor');
        },
        onRender: function(){
            var color = this.options.color ? this.options.color : 'RdYlGn';
            this.setColor(color);
        },
        setColor: function(color){
            this.children.filter(function(view){ return view.model.get('name') == color; })[0].$el.addClass('active').addClass('selected');
        }
    });
});
