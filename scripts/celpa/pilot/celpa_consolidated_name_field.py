import dbf

consolidated_file = "/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/consolidated.dbf"

type_dict = {
    0: 'Non forest',
    2: 'Eucalyptus',
    3: 'Eucalyptus',
    4: 'Pine',
    5: 'Other trees',
}

with dbf.Table(consolidated_file) as db:
    try:
        db.add_fields('Occupacao C(40)')
    except:
        print('Skipping field creation.')

    print(db)

    for record in dbf.Process(db):
        print(record)
        record.occupacao = type_dict[record.dn]
