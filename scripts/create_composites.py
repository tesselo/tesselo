import calendar
import datetime

from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms, remove_perm
from isoweek import Week

from django.contrib.auth.models import User
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

"""
Invite or exclude users and groups from having view, change, or delete
permissions on this object.
"""

invitee = 22
invitee = User.objects.get(id=invitee)
for composite in Composite.objects.all():
    assign_perm('{perm}_{model}'.format(perm='view', model='composite'), invitee, composite)
    assign_perm('{perm}_{model}'.format(perm='change', model='composite'), invitee, composite)
    for wlayer in composite.compositebands.all():
        assign_perm('{perm}_rasterlayer'.format(perm='view'), invitee, wlayer.rasterlayer)
        assign_perm('{perm}_rasterlayer'.format(perm='change'), invitee, wlayer.rasterlayer)
