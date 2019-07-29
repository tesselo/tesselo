import datetime
from unittest.mock import patch

from raster_aggregation.models import AggregationLayer

from django.test import TestCase
from sentinel.models import Composite, CompositeBuild, CompositeBuildSchedule
from sentinel.tasks import push_scheduled_composite_builds


def mock_composite_build_callback(cbuild_id, initiate, rebuild):
    CompositeBuild.objects.filter(id=cbuild_id).update(status=CompositeBuild.FINISHED)


@patch('sentinel.tasks.ecs.composite_build_callback', mock_composite_build_callback)
class SentinelCompositeScheduleTest(TestCase):

    def setUp(self):
        self.agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        self.composite = Composite.objects.create(
            name='The World',
            official=True,
            min_date=datetime.datetime.now() - datetime.timedelta(days=7),
            max_date=datetime.datetime.now() + datetime.timedelta(days=7),
        )
        self.composite2 = Composite.objects.create(
            name='The World 2',
            official=True,
            min_date=datetime.datetime.now() - datetime.timedelta(days=7),
            max_date=datetime.datetime.now() + datetime.timedelta(days=7),
        )
        self.build = CompositeBuild.objects.create(
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        self.build2 = CompositeBuild.objects.create(
            composite=self.composite2,
            aggregationlayer=self.agglayer,
        )
        self.schedule = CompositeBuildSchedule.objects.create(
            interval=CompositeBuildSchedule.WEEKLY,
            delay_build_days=datetime.datetime.now().weekday(),
        )
        self.schedule.compositebuilds.set([self.build, self.build2])

    def test_composite_scheduling(self):
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 2)
        self.schedule.refresh_from_db()
        self.assertIn('Pushing composite builds.', self.schedule.log)
        self.assertIn('Pushing composite build {}'.format(self.build.id), self.schedule.log)

    def test_composite_scheduling_not_the_right_day(self):
        self.schedule.delay_build_days += 1
        self.schedule.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 0)
        self.schedule.refresh_from_db()
        self.assertIn('Not the right day to run this weekly schedule.', self.schedule.log)

    def test_composite_scheduling_past(self):
        self.composite.max_date = self.composite.min_date
        self.composite.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.get(id=self.build.id).status, CompositeBuild.UNPROCESSED)
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 1)

    def test_composite_scheduling_future(self):
        self.composite.min_date = datetime.datetime.now() + datetime.timedelta(days=100)
        self.composite.max_date = datetime.datetime.now() + datetime.timedelta(days=107)
        self.composite.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.get(id=self.build.id).status, CompositeBuild.UNPROCESSED)
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 1)

    def test_composite_scheduling_already_processing(self):
        self.build.status = CompositeBuild.PENDING
        self.build.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.get(id=self.build.id).status, CompositeBuild.PENDING)

    def test_composite_scheduling_monthly_match(self):
        self.schedule.interval = CompositeBuildSchedule.MONTHLY
        self.schedule.delay_build_days = datetime.datetime.now().day - 1
        self.schedule.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 2)

    def test_composite_scheduling_monthly_not_match(self):
        self.schedule.interval = CompositeBuildSchedule.MONTHLY
        self.schedule.delay_build_days = datetime.datetime.now().day + 1
        self.schedule.save()
        push_scheduled_composite_builds()
        self.assertEqual(CompositeBuild.objects.filter(status=CompositeBuild.FINISHED).count(), 0)
        self.schedule.refresh_from_db()
        self.assertIn('Not the right day to run this monthly schedule.', self.schedule.log)
