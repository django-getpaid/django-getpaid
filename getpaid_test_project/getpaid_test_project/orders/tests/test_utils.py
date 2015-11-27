# coding: utf8
from mock import patch, Mock

from django.test import TestCase

from getpaid import utils


class UtilsTestCase(TestCase):

    def test_get_domain_request(self):
        req = Mock(META={'HTTP_HOST': 'example1.com'})

        self.assertEquals('example1.com', utils.get_domain(request=req))

    @patch.object(utils, 'settings')
    def test_get_domain_site_url(self, patch_settings):
        patch_settings.SITE_URL = 'example2.com'

        self.assertEquals('example2.com', utils.get_domain())

    @patch.object(utils, 'settings')
    @patch.object(utils, 'Site')
    def test_get_domain_site_new_django(self, patch_site, patch_settings):
        patch_settings.SITE_URL = None

        with patch.object(utils, 'django') as patch_django:
            patch_django.VERSION = (1, 8)
            domain = utils.get_domain()

        self.assertEquals(domain,
                          patch_site.objects.get_current.return_value.domain)
        patch_site.objects.get_current.assert_called_once_with(request=None)

    @patch.object(utils, 'settings')
    @patch.object(utils, 'Site')
    def test_get_domain_site_old_django(self, patch_site, patch_settings):
        patch_settings.SITE_URL = None

        with patch.object(utils, 'django') as patch_django:
            patch_django.VERSION = (1, 6)
            domain = utils.get_domain()

        self.assertEquals(domain,
                          patch_site.objects.get_current.return_value.domain)
        patch_site.objects.get_current.assert_called_once_with()
