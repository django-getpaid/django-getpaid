# coding: utf8
from mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from getpaid import utils


class UtilsTestCase(TestCase):
    @override_settings(GETPAID_SITE_DOMAIN='example1.com')
    def test_get_domain_getpaid_const(self):
        self.assertEquals('example1.com', utils.get_domain())

    @patch.object(utils, 'reverse')
    @patch.object(utils, 'get_domain')
    def test_build_absolute_url_args_kwargs(self, patch_domain, patch_reverse):
        patch_reverse.return_value = '/path'
        patch_domain.return_value = 'domain'
        args = ('asd', 'qwe')
        kwargs = {'pk', 1}

        url = utils.build_absolute_uri(
            'test',
            reverse_args=args,
            reverse_kwargs=kwargs)

        self.assertEquals(url, 'https://domain/path')
        patch_reverse.assert_called_once_with('test', args=args, kwargs=kwargs)

    @patch.object(utils, 'reverse')
    @patch.object(utils, 'get_domain')
    def test_build_absolute_url_pass_domain(self, patch_domain, patch_reverse):
        patch_reverse.return_value = '/path'

        url = utils.build_absolute_uri('test', domain='domain2')

        self.assertEquals(url, 'https://domain2/path')
        self.assertFalse(patch_domain.called)

    @patch.object(utils, 'reverse')
    def test_build_absolute_url_add_slash(self, patch_reverse):
        patch_reverse.return_value = 'path'

        url = utils.build_absolute_uri('test', domain='domain3')

        self.assertEquals(url, 'https://domain3/path')

    @patch.object(utils, 'reverse')
    def test_build_absolute_url_scheme(self, patch_reverse):
        patch_reverse.return_value = 'path'

        url = utils.build_absolute_uri('test', domain='domain', scheme='ftp')

        self.assertEquals(url, 'ftp://domain/path')
