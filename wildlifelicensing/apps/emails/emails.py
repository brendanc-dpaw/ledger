import logging
import six
from six.moves.urllib.parse import urlparse, urlunparse
import mimetypes


from django.core.mail import EmailMultiAlternatives
from django.template import loader, Template, Context
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_text

from ledger.accounts.models import Document


logger = logging.getLogger('log')


def _render(template, context):
    if isinstance(context, dict):
        context = Context(context)
    if isinstance(template, six.string_types):
        template = Template(template)
    return template.render(context)


def hosts_reverse(name, args=None, kwargs=None):
    scheme, netloc, path, params, query, fragment = urlparse(reverse(name, args=args, kwargs=kwargs))
    if netloc.startswith(settings.DEFAULT_HOST + '.' + settings.PARENT_HOST):
        netloc = netloc.replace(settings.DEFAULT_HOST + '.', '', 1)
    return urlunparse((scheme, netloc, path, params, query, fragment))


class TemplateEmailBase(object):
    subject = ''
    html_template = 'wl/emails/base_email.html'
    # txt_template can be None, in this case a 'tag-stripped' version of the html will be sent. (see send)
    txt_template = 'wl/emails/base-email.txt'

    def send_to_user(self, user, context=None):
        return self.send(user.email, context=context)

    def send(self, to_addresses, from_address=None, context=None, attachments=None, cc=None, bcc=None):
        """
        Send an email using EmailMultiAlternatives with text and html.
        :param to_addresses: a string or a list of addresses
        :param from_address: if None the settings.DEFAULT_FROM_EMAIL is used
        :param context: a dictionary or a Context object used for rendering the templates.
        :param attachments: a list of (filepath, content, mimetype) triples
               (see https://docs.djangoproject.com/en/1.9/topics/email/)
               or Documents
        :param bcc:
        :param cc:
        :return:
        """
        # The next line will throw a TemplateDoesNotExist if html template cannot be found
        html_template = loader.get_template(self.html_template)
        # render html
        html_body = _render(html_template, context)
        if self.txt_template is not None:
            txt_template = loader.get_template(self.txt_template)
            txt_body = _render(txt_template, context)
        else:
            txt_body = strip_tags(html_body)

        # build message
        if isinstance(to_addresses, six.string_types):
            to_addresses = [to_addresses]
        if attachments is None:
            attachments = []
        if attachments is not None and not isinstance(attachments, list):
            attachments = list(attachments)

        if attachments is None:
            attachments = []

        # Convert Documents to (filename, content, mime) attachment
        _attachments = []
        for attachment in attachments:
            if isinstance(attachment, Document):
                filename = str(attachment)
                content = attachment.file.read()
                mime = mimetypes.guess_type(attachment.filename)[0]
                _attachments.append((filename, content, mime))
            else:
                _attachments.append(attachment)
        msg = EmailMultiAlternatives(self.subject, txt_body, from_email=from_address, to=to_addresses,
                                     attachments=_attachments, cc=cc, bcc=bcc)
        msg.attach_alternative(html_body, 'text/html')
        try:
            msg.send(fail_silently=False)
            return msg
        except Exception as e:
            logger.exception("Error while sending email to {}: {}".format(to_addresses, e))
            return None
