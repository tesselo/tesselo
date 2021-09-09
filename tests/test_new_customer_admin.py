import datetime

from django.contrib.auth.models import Group, User
from django.test import TestCase
from guardian.shortcuts import get_objects_for_group
from raster_aggregation.models import AggregationLayer

from auth_admin.tasks import create_new_customer_objects, upgrade_group
from auth_admin.utils import NewCustomerData, NewUserData, UpgradeTestGroupData
from raster_api.models import ReadOnlyToken, TesseloUserAccount
from sentinel.models import Composite, CompositeBuild


class NewCustomerAdminTests(TestCase):
    def setUp(self):
        self.agglayer = AggregationLayer.objects.create(name="Road Runners Road")
        create_new_customer_objects(
            NewCustomerData(
                org_name="ACME",
                country_code="US",
                date_start=datetime.date(1920, 8, 1),
                date_end=datetime.date(1921, 3, 31),
                aggregation_layer_id=self.agglayer.id,
                cloud_percentage=90,
                use_sentinel1=True,
                use_sentinel2=False,
                user_ids=[],
                project_name="Explosive Tennis Balls",
            )
        )

    def test_create_new_customer_objects(self):

        # Group has been created.
        grp = Group.objects.first()
        self.assertEqual(grp.name, "ACME TEST")
        # Composites have been created.
        self.assertEqual(Composite.objects.count(), 8)
        self.assertEqual(
            Composite.objects.first().name,
            "US - Explosive Tennis Balls - ACME - 1920-08",
        )
        self.assertEqual(
            Composite.objects.last().name,
            "US - Explosive Tennis Balls - ACME - 1921-03",
        )
        # Group has access to composites.
        self.assertEqual(len(get_objects_for_group(grp, "sentinel.view_composite")), 8)
        # Composite build is set up.
        self.assertEqual(CompositeBuild.objects.count(), 8)
        self.assertTrue(CompositeBuild.objects.first().include_sentinel_1)
        self.assertFalse(CompositeBuild.objects.first().include_sentinel_2)
        self.assertEqual(
            CompositeBuild.objects.first().aggregationlayer.id, self.agglayer.id
        )

    def test_upgrade_group_no_users(self):
        upgrade_group(
            UpgradeTestGroupData(
                test_group_id=Group.objects.first().id,
                users_data=[],
            )
        )
        self.assertTrue(Group.objects.get(name="ACME PRODUCTION"))
        self.assertEqual(User.objects.exclude(username="AnonymousUser").count(), 0)

    def test_upgrade_group_with_users(self):
        user_data = [
            NewUserData(
                first_name="Wile E.",
                last_name="Coyote",
                email="coyote@acme.com",
                create_token=True,
                language="EN",
            ),
            NewUserData(
                first_name="Road",
                last_name="Runner",
                email="rr@acme.com",
                create_token=False,
                language="EN",
            ),
        ]
        upgrade_group(
            UpgradeTestGroupData(
                test_group_id=Group.objects.first().id,
                users_data=user_data,
            )
        )
        self.assertTrue(Group.objects.get(name="ACME PRODUCTION"))
        # Users were created.
        self.assertEqual(User.objects.exclude(username="AnonymousUser").count(), 2)
        coyote = User.objects.get(email="coyote@acme.com")
        runner = User.objects.get(email="rr@acme.com")
        self.assertEqual(coyote.username, coyote.email)
        # Read only token were created.
        self.assertTrue(ReadOnlyToken.objects.filter(user=coyote))
        self.assertFalse(ReadOnlyToken.objects.filter(user=runner))
        # Account was created.
        account = TesseloUserAccount.objects.get(user=coyote)
        self.assertTrue(account.read_only)
        self.assertEqual(
            account.profile,
            {"baselayers": "BW_OpenStreetMap,OpenStreetMap,Lines,Labels"},
        )
