import calendar
import datetime
from typing import List

import structlog
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist
from guardian.exceptions import WrongAppError
from guardian.shortcuts import assign_perm, get_objects_for_group
from tesselo.slack import SlackClient
from zappa.asynchronous import task

from auth_admin.utils import NewCustomerData, NewUserData, UpgradeTestGroupData
from raster_api.models import ReadOnlyToken, TesseloUserAccount
from sentinel.models import Composite, CompositeBuild

log = structlog.get_logger(__name__)


def _create_test_group(data: NewCustomerData):
    """
    Creates and return a test group, adding one or more staff users.
    """
    group = Group.objects.create(name=f"{data.org_name} TEST")
    users = User.objects.filter(pk__in=data.user_ids)
    for user in users:
        if user.is_staff:
            group.user_set.add(user)
        else:
            log.info(
                f"Ignoring non staff user for the {data.org_name} test group", user=user
            )

    return group


def _composite_name_start(data: NewCustomerData):
    """
    Composite name standardization attempt (C.N.S.A.).
    """
    if data.project_name:
        return f"{data.country_code} - {data.project_name} - {data.org_name}"
    return f"{data.country_code} - {data.org_name}"


def _create_composites(data: NewCustomerData):
    """
    Creates and return monthly composites between to dates using C.N.S.A.
    """
    composites = []
    first_year = data.date_start.year
    last_year = data.date_end.year

    for year in range(first_year, last_year + 1):
        if year == first_year:
            range_month_start = data.date_start.month
        else:
            range_month_start = 1

        if year == last_year:
            range_month_end = data.date_end.month
        else:
            range_month_end = 12

        for month in range(range_month_start, range_month_end + 1):
            day = calendar.monthrange(year, month)[1]
            if month == data.date_end.month and day > data.date_end.day:
                day = data.date_end.day
            start = datetime.date(year, month, 1)
            end = datetime.date(year, month, day)
            composites.append(
                Composite.objects.create(
                    name=f'{_composite_name_start(data)} - {start.year}-{start.strftime("%m")}',
                    min_date=start,
                    max_date=end,
                )
            )
    return composites


def _create_composite_builds(composites: List[Composite], data: NewCustomerData):
    """
    Links composites with the aggregation layer and the desired sentinel versions.
    """
    for composite in composites:
        CompositeBuild.objects.create(
            composite=composite,
            aggregationlayer_id=data.aggregation_layer_id,
            include_sentinel_1=data.use_sentinel1,
            include_sentinel_2=data.use_sentinel2,
        )


def _invite_to_composites(composites: List[Composite], group: Group):
    """
    Gives view permissions to composites for a certain group.
    """
    for composite in composites:
        assign_perm("view_composite", group, composite)


def _notify_composite_builds(data: NewCustomerData, server_uri: str):
    """
    Sends a message to slack with the call to action to trigger
    the composite builds and end the first step of new customer flow.
    """
    search_uri = f"{server_uri}admin/sentinel/compositebuild/?q="
    search_uri += (
        f"{_composite_name_start(data).replace(' ', '%20')}&status__exact=Unprocessed"
    )

    client = SlackClient()
    client.send_to_techies(f"New composite builds for {data.org_name} available")
    client.send_to_techies("Please review and run if everything seems okay.")
    client.send_to_techies(search_uri)


@task
def create_new_customer_objects(data: NewCustomerData, server_uri=None):
    """
    New customer flow, first part.
    """
    group = _create_test_group(data)
    composites = _create_composites(data)
    _create_composite_builds(composites, data)
    _invite_to_composites(composites, group)
    _notify_composite_builds(data, server_uri)


def _copy_group_permissions(test_group: Group, prod_group: Group):
    """
    Copies all object permissions from the list of desired permissions
    from the test group to the production group.
    """
    permissions = [
        "sentinel.view_composite",
        "sentinel.view_rasterlayer",
    ]
    for permission in permissions:
        try:
            objects = get_objects_for_group(group=test_group, perms=[permission])
        except (WrongAppError, ObjectDoesNotExist):
            # Django guardian will raise this Exception if there are no objects
            # related with https://github.com/django-guardian/django-guardian/issues/487
            log.info(
                "Upgrade Group: we couldn't find objects with "
                f"{permission} permission for {test_group.name}"
            )
        else:
            for obj in objects:
                assign_perm(permission, prod_group, obj)


def _create_users(users_data: List[NewUserData]):
    """
    Create users for the production group, their user account objects and
    token if needed.

    Returns a list of freshly created users.
    """
    users = []
    default_profile = {
        "baselayers": "BW_OpenStreetMap,OpenStreetMap,Lines,Labels"
    }
    for u_data in users_data:
        user = User.objects.create(
            username=u_data.email,
            first_name=u_data.first_name,
            last_name=u_data.last_name,
            email=u_data.email,
        )
        TesseloUserAccount.objects.create(
            user=user,
            read_only=True,
            profile=default_profile,
        )
        if u_data.create_token:
            # We are not notifying the users for now, so just create the token
            ReadOnlyToken.objects.create(user=user)
        users.append(user)

    return users


def _create_production_group(test_group, users):
    """
    A production group is like a TEST group, but with PRODUCTION in the name.
    """
    group_name = test_group.name.replace("TEST", "PRODUCTION")
    group = Group.objects.create(name=group_name)
    for user in users:
        group.user_set.add(user)

    return group


def _notify_group_creation(group):
    """
    Notify the team on slack about the end of the P1 New customer process.
    """
    client = SlackClient()
    client.send_to_techies(f"I just created the group {group.name}")
    client.send_to_techies("I could send the read only tokens and the emails now,")
    client.send_to_techies("but I prefer if you do it for now, human.")


@task
def upgrade_group(data: UpgradeTestGroupData):
    """
    New customer flow, second part.
    """
    test_group = Group.objects.get(pk=int(data.test_group_id))
    users = _create_users(data.users_data)
    prod_group = _create_production_group(test_group, users)
    _copy_group_permissions(test_group, prod_group)
    _notify_group_creation(prod_group)
