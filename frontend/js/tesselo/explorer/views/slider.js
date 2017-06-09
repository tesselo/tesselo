define([
        'marionette',
        'nouislider',
        'text!templates/picker.html'
    ], function(
        Marionette,
        noUiSlider,
        template
    ){
    return Marionette.View.extend({
        template: false,
        className: 'slider-element',
        onAttach: function(){
            // Create opacity slider.
            var slider = noUiSlider.create(this.el, {
                start: 100,
                orientation: 'vertical',
                behaviour: 'tap-drag',
                step: 5,
                tooltips: false,
                range: {
                    'min': [0],
                    'max': [100]
                }
            });
            var _this = this;
            slider.on('update', function(values, handle){
                _this.trigger('slider-update', parseInt(values[0]));
            });
        }
    });
});

