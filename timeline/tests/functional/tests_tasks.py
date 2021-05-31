from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from django.core import mail
from freezegun import freeze_time
from mixer.backend.django import mixer

from market import models
from products import models as products
from lessons import models as lessons
from elk.utils.testing import ClassIntegrationTestCase, create_customer, \
    create_teacher
from market.models import Class
from timeline.tasks import notify_15min_to_class, notify_money_leak


class TestStartingSoonEmail(ClassIntegrationTestCase):
    @patch('market.signals.Owl')
    def test_single_class_pre_start_notification(self, Owl):
        entry = self._create_entry()
        c = self._buy_a_lesson()
        self._schedule(c, entry)

        with freeze_time('2032-09-13 15:46'):   # entry will start in 14 minutes
            for i in range(0, 10):  # run this 10 times to check for repietive emails — all notifications should be sent one time
                notify_15min_to_class()

        self.assertEqual(len(mail.outbox), 2)  # if this test fails, carefully check the timezone you are in

        out_emails = [outbox.to[0] for outbox in mail.outbox]

        self.assertIn(self.host.user.email, out_emails)
        self.assertIn(self.customer.user.email, out_emails)

    @patch('market.signals.Owl')
    def test_two_classes_pre_start_notification(self, Owl):
        self.lesson = mixer.blend('lessons.MasterClass', host=self.host, slots=5)

        other_customer = create_customer()
        first_customer = self.customer

        entry = self._create_entry()
        entry.slots = 5
        entry.save()

        c = self._buy_a_lesson()
        self._schedule(c, entry)

        self.customer = other_customer
        c1 = self._buy_a_lesson()
        self._schedule(c1, entry)
        with freeze_time('2032-09-13 15:46'):   # entry will start in 14 minutes
            for i in range(0, 10):  # run this 10 times to check for repietive emails — all notifications should be sent one time
                notify_15min_to_class()

        self.assertEqual(len(mail.outbox), 3)  # if this test fails, carefully check the timezone you are in

        out_emails = [outbox.to[0] for outbox in mail.outbox]

        self.assertIn(self.host.user.email, out_emails)
        self.assertIn(first_customer.user.email, out_emails)
        self.assertIn(other_customer.user.email, out_emails)

    def _prepare_notify_test_data(self):

        self.customer = create_customer()
        self.product = products.Product1.objects.get(pk=1)
        self.product.duration = timedelta(days=5)

        self.subscription = models.Subscription(
            customer=self.customer,
            product=self.product,
            buy_price=150,
        )
        self.subscription.save()

        teacher = create_teacher()
        lesson = mixer.blend(
            lessons.MasterClass,
            host=teacher,
            photo=mixer.RANDOM
        )
        entry = mixer.blend(
            'timeline.Entry',
            lesson=lesson,
            teacher=teacher,
            start=self.tzdatetime(2032, 12, 25, 12, 00)
        )

        self.klass = Class.objects.first()
        self.klass.timeline = entry

        self.klass.is_scheduled = True
        self.klass.timeline.is_finished = False
        self.klass.timeline.start = timezone.now() - timedelta(days=8)

        self.klass.save()
        self.klass.timeline.save()

    @patch('market.signals.Owl')
    def test_notify_money_leak_sends_email_to_corresponding_customers(self, Owl):
        self._prepare_notify_test_data()
        notify_money_leak()
        self.assertEqual(len(mail.outbox), 1)



