from django.test import TestCase
from google.oauth2 import id_token
from unittest.mock import patch
from .exceptions.exceptions import (
    EmailNotFoundException,
    InvalidGoogleLoginException,
    InvalidGoogleIDTokenException,
    InvalidGoogleAuthCodeException
)
from .models import OdiUser, Assessee, Assessor, Company, AuthenticationService
from .services import utils, google_login
import requests


class GoogleAuthTest(TestCase):
    def setUp(self) -> None:
        self.dummy_user_data = {
            'email': 'assesseeregister234@gmail.com',
            'given_name': 'Householder',
            'family_name': 'Givens'
        }
        self.dummy_verify_id_response = {
            'iss': 'https://accounts.google.com',
            'azp': 'sample azp',
            'aud': 'sample aud',
            'sub': 'sample sub',
            'hd': 'ui.ac.id',
            'email': 'assessor@gmail.com',
            'email_verified': True,
            'at_hash': 'asdasda',
            'name': 'sample name',
            'picture': 'https://lh3.googleusercontent.com/a/ALm5wu2Sam1zn6zUtMWPxl9eO1Zt_y6HEi4sfHDPiuSk=s96-c',
            'given_name': 'given name',
            'family_name': 'family name',
            'locale': 'id',
            'iat': 1664700260,
            'exp': 1664703860
        }
        self.dummy_auth_token_response = {
            'access_token': 'sample access token',
            'expires_in': 3599,
            'refresh_token': 'sample refresh token',
            'scope': 'scopes',
            'token_type': 'Bearer',
            'id_token': 'sample_id_token'
        }

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

    def test_get_tokens_for_user(self):
        dummy_user = OdiUser.objects.create_user(email='email@gmail.com', password='Password123')
        tokens = google_login.get_tokens_for_user(dummy_user)
        self.assertTrue(isinstance(tokens, dict))
        self.assertIsNotNone(tokens.get('refresh'))
        self.assertIsNotNone(tokens.get('access'))

    @patch.object(Assessee, 'save')
    def test_create_assessee_from_data_using_google_auth(self, mocked_save):
        created_assessee = google_login.create_assessee_from_data_using_google_auth(self.dummy_user_data)
        mocked_save.assert_called_once()
        self.assertEqual(created_assessee.email, self.dummy_user_data['email'])
        self.assertEqual(created_assessee.first_name, self.dummy_user_data['given_name'])
        self.assertEqual(created_assessee.last_name, self.dummy_user_data['family_name'])

    def test_get_assessee_assessor_user_with_google_matching_data_when_assessor_exists(self):
        assessor_company = Company.objects.create_user(email='company@company.com', password='Password123')
        expected_assessor = Assessor(
            email=self.dummy_user_data['email'],
            first_name=self.dummy_user_data['given_name'],
            last_name=self.dummy_user_data['family_name'],
            associated_company=assessor_company,
            authentication_service=AuthenticationService.GOOGLE.value
        )
        expected_assessor.save()
        retrieved_assessor = google_login.get_assessee_assessor_user_with_google_matching_data(self.dummy_user_data)
        self.assertTrue(isinstance(retrieved_assessor, Assessor))
        self.assertEqual(retrieved_assessor.email, expected_assessor.email)
        self.assertEqual(retrieved_assessor.first_name, expected_assessor.first_name)
        self.assertEqual(retrieved_assessor.last_name, expected_assessor.last_name)

    def test_get_assessee_assessor_user_with_google_matching_data_when_assessee_exists(self):
        expected_assessee = Assessee(
            email=self.dummy_user_data['email'],
            first_name=self.dummy_user_data['given_name'],
            last_name=self.dummy_user_data['family_name'],
            authentication_service=AuthenticationService.GOOGLE.value
        )
        expected_assessee.save()
        retrieved_assessee = google_login.get_assessee_assessor_user_with_google_matching_data(self.dummy_user_data)
        self.assertTrue(isinstance(retrieved_assessee, Assessee))
        self.assertEqual(retrieved_assessee.email, expected_assessee.email)
        self.assertEqual(retrieved_assessee.first_name, expected_assessee.first_name)
        self.assertEqual(retrieved_assessee.last_name, expected_assessee.last_name)

    def test_get_assessee_assessor_with_google_matching_data_when_no_assessee_and_assessor_exist(self):
        expected_assessee = Assessee(
            email=self.dummy_user_data['email'],
            first_name=self.dummy_user_data['given_name'],
            last_name=self.dummy_user_data['family_name'],
            authentication_service=AuthenticationService.DEFAULT.value
        )
        expected_assessee.save()
        try:
            google_login.get_assessee_assessor_user_with_google_matching_data(self.dummy_user_data)
            self.fail('Exception not raised')
        except EmailNotFoundException as exception:
            self.assertEqual(
                str(exception),
                f'Assessor or Assessee registering with google login with {expected_assessee.email} email is not found.'
            )

    @patch.object(google_login, 'create_assessee_from_data_using_google_auth')
    def test_register_assessee_with_google_data_when_not_exist(self, mocked_create_assessee_google):
        google_login.register_assessee_with_google_data(self.dummy_user_data)
        mocked_create_assessee_google.assert_called_once()

    def test_register_assessee_with_google_data_when_assessee_already_register_through_default_service(self):
        existing_user = Assessee(
            email=self.dummy_user_data['email'],
            first_name=self.dummy_user_data['given_name'],
            last_name=self.dummy_user_data['family_name'],
            authentication_service=AuthenticationService.DEFAULT.value
        )
        existing_user.save()
        try:
            google_login.register_assessee_with_google_data(self.dummy_user_data)
            self.fail('Exception not raised')
        except InvalidGoogleLoginException as exception:
            self.assertEqual(str(exception), 'User is already registered through the One Day Intern login service.')

    @patch.object(id_token, 'verify_oauth2_token')
    def test_get_profile_from_id_token(self, mocked_google_verify_token):
        dummy_id_token = '4/0ARtbsJofQGXFATZ0yRqzXl9P7XiFQ_'
        mocked_google_verify_token.return_value = self.dummy_verify_id_response
        retrieved_identity_info = google_login.google_get_profile_from_id_token(dummy_id_token)
        self.assertDictEqual(self.dummy_verify_id_response, retrieved_identity_info)

    @patch.object(id_token, 'verify_oauth2_token')
    def test_get_profile_from_id_token_when_token_invalid(self, mocked_google_verify_token):
        dummy_response = self.dummy_verify_id_response.copy()
        dummy_response['sub'] = None
        dummy_id_token = '4/0ARtbsJofQGXFATZ0yRqzXl9P7XiFQ_'
        mocked_google_verify_token.return_value = dummy_response
        try:
            google_login.google_get_profile_from_id_token(dummy_id_token)
            self.fail('Exception not raised')
        except InvalidGoogleIDTokenException:
            pass

    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    @patch.object(utils, 'parameterize_url')
    def test_google_get_id_from_auth_code_when_valid(self, mocked_parameterize_url, mocked_post_request, mocked_json):
        dummy_auth_code = 'auth_code'
        dummy_redirect_uri = 'redirect_uri'
        mocked_parameterize_url.return_value = 'sample_google_token_verification_url'
        mocked_post_request.return_value = requests.Response()
        mocked_json.return_value = self.dummy_auth_token_response

        fetched_id_token = google_login.google_get_id_token_from_auth_code(dummy_auth_code, dummy_redirect_uri)
        self.assertEqual(fetched_id_token, self.dummy_auth_token_response['id_token'])

    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    @patch.object(utils, 'parameterize_url')
    def test_google_get_id_from_auth_code_when_invalid(self, mocked_parameterize_url, mocked_post_request, mocked_json):
        dummy_auth_code = 'auth_code'
        dummy_redirect_uri = 'redirect_uri'
        dummy_response_data = {}
        mocked_parameterize_url.return_value = 'sample_google_token_verification_url'
        mocked_post_request.return_value = requests.Response()
        mocked_json.return_value = dummy_response_data

        try:
            google_login.google_get_id_token_from_auth_code(dummy_auth_code, dummy_redirect_uri)
            self.fail('Exception not raised')
        except InvalidGoogleAuthCodeException:
            pass
