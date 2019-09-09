def get_report_obj_str(obj):
    if obj.composite:
        target = 'Composite'
        target_id = obj.composite_id
    elif obj.predictedlayer:
        target = 'Predictedlayer'
        target_id = obj.predictedlayer_id
    else:
        return 'No layer specified'

    return 'AggLayer {} | {}{} {}'.format(
        obj.aggregationlayer_id,
        'Formula {} | '.format(obj.formula_id) if obj.formula_id else '',
        target,
        target_id,
    )
