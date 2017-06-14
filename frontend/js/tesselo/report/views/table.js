define([
        'marionette',
        'text!../templates/table.html'
], function(
    marionette,
    tableTemplate
    ){

    const RowView = marionette.View.extend({
        tagName: 'tr',
        template: _.template('<td><%- name %></td><% _.each(ordered_values, function(val) { %> <td><%- val%></td> <% }) %>')
    });

    const TableBody = marionette.CollectionView.extend({
        tagName: 'tbody',
        childView: RowView
    });

    const TableView = marionette.View.extend({
        tagName: 'table',
        className: 'table table-hover',
        template: _.template(tableTemplate),

        regions: {
            body: {
                el: 'tbody',
                replaceElement: true
            }
        },

        onAttach: function() {
            this.showChildView('body', new TableBody({
                collection: this.collection
            }));
        }
    });

    return TableView;
});
