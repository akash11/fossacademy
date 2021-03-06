import requests

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage

from celery.task import Task

from l10n.models import localize_email

class SendNotifications(Task):
    """Send email notification to the users specified by ``profiles``."""
    name = 'notifications.tasks.SendNotifications'

    def run(self, profiles, subject_template, body_template, context, reply_token=None, sender=None, **kwargs):
        log = self.get_logger(**kwargs)
        subjects, bodies = localize_email(subject_template,
            body_template, context)

        from_name = "P2PU Notifications"
        if sender:
            from_name = sender
            
        from_email = "{0} <{1}>".format(from_name, settings.DEFAULT_FROM_EMAIL)
        if reply_token:
            from_email = "{0} <reply+{1}@{2}>".format(from_name, reply_token,
                settings.REPLY_EMAIL_DOMAIN)
            
        for profile in profiles:
            if profile.deleted:
                continue
            subject = subjects[profile.preflang]
            body = bodies[profile.preflang]
            log.debug("Sending email to user %d with subject %s" % (
                profile.user.id, subject,))
            email = EmailMessage(subject, body, from_email, [profile.user.email])
            email.send()
            #profile.user.email_user(subject, body, from_email)


class PostNotificationResponse(Task):
    """ Send a post to the response URL specified by the token """
    name = 'notifications.tasks.PostNotificationResponse'

    def run(self, token, user, text, **kwargs):
        #CS whole token passed in, but only url is used
        #!! internal API key is posted to callback, wont work for external apps!
        #!! should send data as json request?
        log = self.get_logger(**kwargs)
        log.debug("PostNotificationResponse: invoking callback") 

        data = {
            'api-key': settings.INTERNAL_API_KEY,
            'from': user.username,
            'text': text,
        }

        url = token.response_callback
        if token.response_callback.find('http') != 0:
            host_name = Site.objects.get_current().domain
            url = "https://{0}{1}".format(host_name, token.response_callback)

        try:
            results = requests.post(url, data=data)
        except requests.exceptions.RequestException as error:
            log.error("calling internal API failed. URL: {0}, message: ".format(url, error.message))
