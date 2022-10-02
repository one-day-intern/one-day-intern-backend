from django.test import TestCase
from .services import utils


class GoogleAuthTest(TestCase):
    def test_parameterize_url_when_parameter_arguments_all_not_none(self):
        base_url = 'www.base_url/token?'
        parameter_arguments = {
            'client_id': '<client_id>',
            'client_secret': '<client_secret>',
            'code': '<auth_code>',
            'grant_type': '<grant_types>',
            'redirect_uri': '<redirect_uri>'
        }
        expected_url = 'www.base_url/token?client_id=<client_id>' \
                       '&client_secret=<client_secret>' \
                       '&code=<auth_code>&grant_type=<grant_types>' \
                       '&redirect_uri=<redirect_uri>&'
        resulted_url = utils.parameterize_url(base_url, parameter_arguments)
        self.assertEqual(resulted_url, expected_url)

    def test_parameterize_url_when_parameter_arguments_contain_none(self):
        base_url = 'www.base_url/token?'
        parameter_arguments = {
            'client_id': '<client_id>',
            'client_secret': '<client_secret>',
            'code': '<auth_code>',
            'grant_type': '<grant_types>',
            'redirect_uri': '<redirect_uri>',
            'valid': None
        }
        expected_url = 'www.base_url/token?client_id=<client_id>' \
                       '&client_secret=<client_secret>' \
                       '&code=<auth_code>&grant_type=<grant_types>' \
                       '&redirect_uri=<redirect_uri>&valid&'

        resulted_url = utils.parameterize_url(base_url, parameter_arguments)
        self.assertEqual(resulted_url, expected_url)


