from __future__ import unicode_literals

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext

try:
    from urllib.parse import urlparse
except ImportError:
    # Python < 3
    from urlparse import urlparse

from cms.utils.page import get_all_pages_from_path
from cms.utils.urlutils import admin_reverse, relative_url_regex


class ExtraURLValidator(URLValidator):
    """
    Same as URLValidator but supports more schemes!
    """
    schemes = URLValidator.schemes + [
        'sftp', 'webdav', 'webdavs', 'afp', 'smb', 'git', 'svn', 'hg',
        'mailto', 'tel'
    ]

    tel_re = r'^[0-9\+\#\*\-\.\(\)]+$'

    def __call__(self, value):
        try:
            super(ExtraURLValidator, self).__call__(value)
        except ValidationError:
            parsed = urlparse(value)
            if parsed.scheme == "tel" and re.match(self.tel_re, parsed.netloc):
                pass
            else:
                raise


def validate_relative_url(value):
    RegexValidator(regex=relative_url_regex)(value)


def validate_url(value):
    try:
        # Validate relative urls first
        validate_relative_url(value)
    except ValidationError:
        # Fallback to absolute urls
        ExtraURLValidator()(value)


def validate_url_uniqueness(site, path, language, exclude_page=None):
    """ Checks for conflicting urls
    """
    if '/' in path:
        validate_url(path)

    path = path.strip('/')
    pages = get_all_pages_from_path(site, path, language)
    pages = pages.select_related('publisher_public')

    if exclude_page:
        pages = pages.exclude(pk=exclude_page.pk)

        if exclude_page.publisher_public_id:
            pages = pages.exclude(pk=exclude_page.publisher_public_id)

    try:
        conflict_page = pages[0]
    except IndexError:
        return True

    if conflict_page.publisher_is_draft:
        page_id = conflict_page.pk
    else:
        # rare case where draft points to one url
        # and live points to another which conflicts.
        # Use the draft ID because public page is not editable.
        page_id = conflict_page.publisher_public_id

    if conflict_page.is_page_type:
        change_url = admin_reverse('cms_pagetype_change', args=[page_id])
    else:
        change_url = admin_reverse('cms_page_change', args=[page_id])

    conflict_url = '<a href="%(change_url)s" target="_blank">%(page_title)s</a>' % {
        'change_url': change_url,
        'page_title': force_text(conflict_page),
    }

    if exclude_page:
        message = ugettext('Page %(conflict_page)s has the same url \'%(url)s\' as current page "%(instance)s".')
    else:
        message = ugettext('Page %(conflict_page)s has the same url \'%(url)s\' as current page.')
    message = message % {'conflict_page': conflict_url, 'url': path, 'instance': exclude_page}
    raise ValidationError(mark_safe(message))
