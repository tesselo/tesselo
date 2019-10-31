def get_report_obj_str(obj):
    return 'Aggs {}, Comps {}, Forms {}, Preds {}'.format(
        obj.aggregationlayers.count(),
        obj.composites.count(),
        obj.formulas.count(),
        obj.predictedlayers.count(),
    )
