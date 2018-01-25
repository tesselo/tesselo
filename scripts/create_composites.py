import calendar
import datetime

from isoweek import Week

from sentinel.models import Composite

for year in range(2014, 2019):
    print('Months ---------------------')
    for month in range(1, 13):
        mo = calendar.monthrange(year, month)[1]
        start = datetime.date(year, month, 1)
        end = datetime.date(year, month, mo)
        print(start, end)
        if not Composite.objects.filter(min_date=start, max_date=end, official=True).exists():
            Composite.objects.create(
                name='{0} {1}'.format(start.strftime('%B'), start.strftime('%Y')),
                min_date=start,
                max_date=end,
                official=True,
            )
    print('Weeks ---------------------')
    for week in Week.weeks_of_year(year):
        start = week.days()[0]
        end = week.days()[-1]
        print(start, end)
        if not Composite.objects.filter(min_date=start, max_date=end, official=True).exists():
            Composite.objects.create(
                name='Week {0} {1}'.format(week.week, start.strftime('%Y')),
                min_date=start,
                max_date=end,
                official=True,
            )



# s.post(api + composite, json={
#
# })
