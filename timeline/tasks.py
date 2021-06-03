from datetime import timedelta

from elk.celery import app as celery
from mailer.owl import Owl
from market.models import Class
from timeline.signals import class_starting_student, class_starting_teacher


@celery.task
def notify_15min_to_class():
    for i in Class.objects.starting_soon(timedelta(minutes=30)).filter(pre_start_notifications_sent_to_teacher=False).distinct('timeline'):
        for other_class_with_the_same_timeline in Class.objects.starting_soon(timedelta(minutes=30)).filter(timeline=i.timeline):
            """
            Set all other starting classes as notified either.
            """
            other_class_with_the_same_timeline.pre_start_notifications_sent_to_teacher = True
            other_class_with_the_same_timeline.save()
        class_starting_teacher.send(sender=notify_15min_to_class, instance=i)

    for i in Class.objects.starting_soon(timedelta(minutes=30)).filter(pre_start_notifications_sent_to_student=False):
        i.pre_start_notifications_sent_to_student = True
        i.save()
        class_starting_student.send(sender=notify_15min_to_class, instance=i)


@celery.task
def notify_money_leak():
    for c in Class.objects.to_remind():
        owl = Owl(
            template='mail/class/teacher/scheduled.html',
            ctx={
                'c': c,
            },
            to=[c.customer.customer_email],
            timezone=c.customer.user.crm.timezone,
        )
        owl.attach('elk-class.ics',
                   content=c.timeline.as_ical(for_whom='student'))
        owl.send()
