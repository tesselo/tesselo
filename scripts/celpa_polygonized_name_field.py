import dbf

consolidated_file = "/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/polygonized/sentinel-predicted-svm.dbf"

type_dict = {
    0: 'Non forest',
    2: 'Eucalyptus',
    3: 'Eucalyptus',
    4: 'Pine',
    5: 'Other trees',
}
print('Creating named field for tree type prediction.')
with dbf.Table(consolidated_file) as db:
    try:
        db.add_fields('Occupacao C(40)')
    except:
        print('Skipping field creation.')

    print(db)

    for record in dbf.Process(db):
        record.occupacao = type_dict[record.dn]

consolidated_file = "/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/polygonized/sentinel-fonfo-predicted-rf.dbf"

type_dict = {
    1: 'Non forest',
    2: 'Forest',
}
print('Creating named field for FoNFo prediction.')
with dbf.Table(consolidated_file) as db:
    try:
        db.add_fields('Occupacao C(40)')
    except:
        print('Skipping field creation.')

    print(db)

    for record in dbf.Process(db):
        record.occupacao = type_dict[record.dn]
