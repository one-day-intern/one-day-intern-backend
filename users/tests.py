from django.contrib.auth import get_user_model
from django.test import TestCase
from google.oauth2 import id_token
from unittest.mock import patch
from .services import registration, utils, google_login
from one_day_intern.exceptions import (
    InvalidRegistrationException,
    EmailNotFoundException,
    InvalidGoogleLoginException,
    InvalidGoogleIDTokenException,
    InvalidGoogleAuthCodeException
)
from rest_framework.test import APIClient
from .models import OdiUser, Assessee, Assessor, Company, AuthenticationService, CompanyOneTimeLinkCode
from .services.registration import validate_user_assessor_registration_data, generate_one_time_code
from http import HTTPStatus
import json
import requests
import uuid


INVALID_EMAIL = 'email@email'
TEST_COMPANY_NAME = 'Dummy Company Name'
TEST_COMPANY_DESCRIPTION = 'Dummy company description'
TEST_COMPANY_ADDRESS = 'Dummy company address'
REQUEST_CONTENT_TYPE = 'application/json'

EMAIL_IS_INVALID = 'Email is invalid'
EMAIL_MUST_NOT_BE_NULL = 'Email must not be null'
PASSWORD_MUST_NOT_BE_NULL = 'Password must not be null'
PASSWORD_INVALID_NO_UPPER = 'Password length must contain at least 1 uppercase character'
EXCEPTION_NOT_RAISED = 'Exception not raised'

REGISTER_COMPANY_URL = '/users/register-company/'
REGISTER_ASSESSEE_URL = '/users/register-assessee/'
REGISTER_ASSESSOR_URL = '/users/register-assessor/'
GENERATE_ONE_TIME_CODE_URL = '/users/generate-code/'
GET_USER_INFO_URL = '/users/get-info/'


class OdiUserTestCase(TestCase):
    def setUp(self) -> None:
        self.user_model = get_user_model()

    def test_create_complete_user(self):
        email = 'complete@email.com'
        password = 'mypassword'

        with patch.object(self.user_model, 'save') as mocked_save:
            new_user = self.user_model.objects.create_user(email=email, password=password)

            self.assertTrue(isinstance(new_user, OdiUser))
            self.assertEqual(new_user.email, email)
            self.assertTrue(new_user.check_password(raw_password=password))
            self.assertFalse(new_user.is_staff)
            self.assertFalse(new_user.is_superuser)
            mocked_save.assert_called_once()

    def test_create_user_with_no_email(self):
        email = ''
        password = 'mypassword'

        with self.assertRaises(ValueError):
            with patch.object(self.user_model, 'save') as mocked_save:
                self.user_model.objects.create_user(email=email, password=password)
                mocked_save.assert_not_called()


class OdiSuperUserTestCase(TestCase):
    def setUp(self) -> None:
        self.user_model = get_user_model()

    def test_superuser_complete(self):
        email = 'superuser@email.com'
        password = 'password'
        dummy_user = OdiUser(email=email)
        dummy_user.set_password(password)

        with patch.object(self.user_model.objects, 'create_user') as mocked_object_manager:
            with patch.object(self.user_model, 'save') as mocked_save:
                mocked_object_manager.return_value = dummy_user
                new_superuser = self.user_model.objects.create_superuser(email=email, password=password)

                self.assertEqual(new_superuser.email, email)
                self.assertTrue(new_superuser.check_password(password))
                self.assertTrue(new_superuser.is_staff)
                self.assertTrue(new_superuser.is_admin)
                self.assertTrue(new_superuser.is_superuser)
                mocked_save.assert_called_once()


class UtilityTestCase(TestCase):
    def test_validate_password_when_valid(self):
        validation_result = utils.validate_password('Pass1234')

        self.assertTrue(validation_result['is_valid'])
        self.assertIsNone(validation_result['message'])

    def test_validate_password_when_length_is_less(self):
        error_message = 'Password length must be at least 8 characters'
        validation_result = utils.validate_password('123')

        self.assertFalse(validation_result['is_valid'])
        self.assertEqual(validation_result['message'], error_message)

    def test_validate_password_when_no_uppercase(self):
        validation_result = utils.validate_password('abcdefgh')

        self.assertFalse(validation_result['is_valid'])
        self.assertEqual(validation_result['message'], PASSWORD_INVALID_NO_UPPER)

    def test_validate_password_when_no_lowercase(self):
        error_message = 'Password length must contain at least 1 lowercase character'
        validation_result = utils.validate_password('A12345678')

        self.assertFalse(validation_result['is_valid'])
        self.assertEqual(validation_result['message'], error_message)

    def test_validate_password_when_no_number(self):
        error_message = 'Password length must contain at least 1 number character'
        validation_result = utils.validate_password('Password')

        self.assertFalse(validation_result['is_valid'])
        self.assertEqual(validation_result['message'], error_message)

    def test_validate_email_when_valid(self):
        email = 'valid_email@email.com'
        self.assertTrue(utils.validate_email(email))

    def test_validate_email_when_empty(self):
        email = ''
        self.assertFalse(utils.validate_email(email))

    def test_validate_email_when_invalid(self):
        self.assertFalse(utils.validate_email(INVALID_EMAIL))

    def test_validate_date_format_when_valid(self):
        date_str = '2022-09-26T15:29:30.506Z'
        self.assertTrue(utils.validate_date_format(date_str))

        date_str = '2022-09-26'
        self.assertTrue(utils.validate_date_format(date_str))

    def test_validate_date_format_when_invalid(self):
        date_str = ''
        self.assertFalse(utils.validate_date_format(date_str))

        date_str = '2022-26'
        self.assertFalse(utils.validate_date_format(date_str))

    def test_get_date_from_valid_date_string(self):
        date_str = '2021-08-16T15:29:30.506Z'
        date = utils.get_date_from_string(date_str)

        self.assertEqual(date.day, 16)
        self.assertEqual(date.month, 8)
        self.assertEqual(date.year, 2021)

    def test_sanitize_request_data_when_not_empty(self):
        expected_result = {'name': 'Sample Name', 'age': 27}
        request_data = {'name': 'Sample Name     ', 'age': 27}
        utils.sanitize_request_data(request_data)
        self.assertDictEqual(request_data, expected_result)

    def test_sanitize_request_data_when_empty(self):
        expected_result = {}
        request_data = {}
        utils.sanitize_request_data(request_data)
        self.assertDictEqual(request_data, expected_result)


class UserRegistrationTest(TestCase):
    def setUp(self) -> None:
        self.base_request_data = {
            'email': 'user@email.com',
            'password': 'Password123',
            'confirmed_password': 'Password123'
        }

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_data_when_request_is_valid(self, mocked_validate_email,
                                                                   mocked_validate_password):
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }

        request_data = self.base_request_data.copy()

        try:
            registration.validate_user_registration_data(request_data)
        except Exception as exception:
            self.fail(f'{exception} is raised.')

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_email_is_missing(self, mocked_validate_email, mocked_validate_password):
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }

        request_data = self.base_request_data.copy()
        request_data['email'] = ''

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), EMAIL_MUST_NOT_BE_NULL)

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_password_is_missing(self, mocked_validate_email, mocked_validate_password):
        expected_error_message = 'Password must not be null'
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }

        request_data = self.base_request_data.copy()
        request_data['password'] = ''
        request_data['confirmed_password'] = ''

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_password_does_not_match_confirmation(self, mocked_validate_email,
                                                                                  mocked_validate_password):
        expected_error_message = 'Password must match password confirmation'
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }

        request_data = self.base_request_data.copy()
        request_data['password'] = 'Password123'
        request_data['confirmed_password'] = 'passWord123'

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_email_is_invalid(self, mocked_validate_email, mocked_validate_password):
        mocked_validate_email.return_value = False
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }

        request_data = self.base_request_data.copy()
        request_data['email'] = INVALID_EMAIL

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), EMAIL_IS_INVALID)

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_password_is_invalid(self, mocked_validate_email, mocked_validate_password):
        expected_error_message = 'Password length must contain at least 1 number character'
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': False,
            'message': expected_error_message
        }

        request_data = self.base_request_data.copy()
        request_data['password'] = 'Password'
        request_data['confirmed_password'] = 'Password'

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_user_is_already_registered_with_same_email(self,
                                                                                        mocked_validate_email,
                                                                                        mocked_validate_password):
        request_data = self.base_request_data.copy()
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }
        OdiUser.objects.create_user(email=request_data['email'], password=request_data['password'])

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), f'Email {request_data["email"].lower()} is already registered')

    @patch.object(utils, 'validate_password')
    @patch.object(utils, 'validate_email')
    def test_validate_user_registration_when_user_is_already_registered_with_different_email_case(
            self, mocked_validate_email, mocked_validate_password):
        request_data = self.base_request_data.copy()
        request_data['email'] = request_data['email'].upper()
        mocked_validate_email.return_value = True
        mocked_validate_password.return_value = {
            'is_valid': True,
            'message': None
        }
        OdiUser.objects.create_user(email=self.base_request_data['email'], password=request_data['password'])

        try:
            registration.validate_user_registration_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), f'Email {request_data["email"].lower()} is already registered')


class CompanyRegistrationTest(TestCase):
    def setUp(self) -> None:
        self.base_request_data = {
            'email': 'company@email.com',
            'password': 'Password123',
            'company_name': 'PT Indonesia Sejahtera',
            'company_description': 'PT Indonesia Sejahtera adalah sebuah PT',
            'company_address': 'JL. PPL Jaya'
        }

        self.expected_company = Company(
            email=self.base_request_data.get('email'),
            password=self.base_request_data.get('Password123'),
            company_name=self.base_request_data.get('company_name'),
            description=self.base_request_data.get('company_description'),
            address=self.base_request_data.get('company_address'),
        )

    def test_validate_user_company_registration_data_when_company_is_valid(self):
        request_data = self.base_request_data.copy()

        try:
            registration.validate_user_company_registration_data(request_data)
        except InvalidRegistrationException as exception:
            self.fail(f'{exception} is raised.')

    def test_validate_user_company_registration_data_when_company_name_is_not_valid(self):
        exception_error_message = 'Company name must be of minimum 3 characters and maximum of 50 characters'
        request_data_missing_name = self.base_request_data.copy()
        request_data_missing_name['company_name'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_name = self.base_request_data.copy()
        request_data_short_name['company_name'] = 'PT'

        try:
            registration.validate_user_company_registration_data(request_data_short_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_long_name = self.base_request_data.copy()
        request_data_long_name['company_name'] = 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz'

        try:
            registration.validate_user_company_registration_data(request_data_short_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_company_registration_data_when_company_description_is_not_valid(self):
        exception_error_message = 'Company description must be more than 3 characters'
        request_data_missing_description = self.base_request_data.copy()
        request_data_missing_description['company_description'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_description)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_description = self.base_request_data.copy()
        request_data_short_description['company_description'] = 'PT'

        try:
            registration.validate_user_company_registration_data(request_data_short_description)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_company_registration_data_when_company_address_is_invalid(self):
        exception_error_message = 'Company address must be more than 3 characters'
        request_data_missing_address = self.base_request_data.copy()
        request_data_missing_address['company_address'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_address)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_address = self.base_request_data.copy()
        request_data_short_address['company_address'] = 'JL'

        try:
            registration.validate_user_company_registration_data(request_data_short_address)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    @patch.object(Company.objects, 'create_user')
    def test_save_company_from_request_data(self, mocked_create_user):
        request_data = self.base_request_data.copy()
        mocked_create_user.return_value = self.expected_company

        saved_company = registration.save_company_from_request_data(request_data)

        mocked_create_user.assert_called_once()
        self.assertEqual(saved_company, self.expected_company)

    @patch.object(registration, 'save_company_from_request_data')
    @patch.object(registration, 'validate_user_company_registration_data')
    @patch.object(registration, 'validate_user_registration_data')
    def test_register_company(self, mocked_validate_user_registration_data,
                              mocked_validate_user_company_registration_data,
                              mocked_save_company_from_request_data):

        request_data = self.base_request_data.copy()
        mocked_validate_user_registration_data.return_value = None
        mocked_validate_user_company_registration_data.return_value = None
        mocked_save_company_from_request_data.return_value = self.expected_company

        dummy_company = registration.register_company(request_data)

        mocked_validate_user_registration_data.assert_called_once()
        mocked_validate_user_company_registration_data.assert_called_once()
        mocked_save_company_from_request_data.assert_called_once()
        self.assertEqual(dummy_company, self.expected_company)


class AssesseeRegistrationTest(TestCase):
    def setUp(self) -> None:
        self.base_request_data = {
            'email': 'assessee461@gmail.com',
            'password': 'testPassword1234',
            'confirmed_password': 'testPassword1234',
            'first_name': 'Anastasia',
            'last_name': 'Yuliana',
            'phone_number': '+628127572466',
            'date_of_birth': '1994-09-30T10:37:35.849Z'
        }

        self.expected_assessee = Assessee(
            email=self.base_request_data.get('email'),
            password=self.base_request_data.get('password'),
            first_name=self.base_request_data.get('first_name'),
            last_name=self.base_request_data.get('last_name'),
            phone_number=self.base_request_data.get('phone_number'),
            date_of_birth=self.base_request_data.get('date_of_birth')
        )

    def test_validate_user_assessee_registration_data_when_assessee_is_valid(self):
        request_data = self.base_request_data.copy()

        try:
            registration.validate_user_assessee_registration_data(request_data)
        except InvalidRegistrationException as exception:
            self.fail(f'{exception} is raised.')

    def test_validate_user_assessee_registration_data_when_assessee_first_name_is_not_valid(self):
        exception_error_message = 'Assessee first name must not be null'
        request_data_missing_name = self.base_request_data.copy()
        request_data_missing_name['first_name'] = ''

        try:
            registration.validate_user_assessee_registration_data(request_data_missing_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_assessee_registration_data_when_assessee_last_name_is_not_valid(self):
        exception_error_message = 'Assessee last name must not be null'
        request_data_missing_name = self.base_request_data.copy()
        request_data_missing_name['last_name'] = ''

        try:
            registration.validate_user_assessee_registration_data(request_data_missing_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_assessee_registration_data_when_assessee_phone_number_is_not_valid(self):
        exception_error_message = 'Assessee phone number must not be null'
        request_data_missing_phone_number = self.base_request_data.copy()
        request_data_missing_phone_number['phone_number'] = ''

        try:
            registration.validate_user_assessee_registration_data(request_data_missing_phone_number)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_assessee_registration_data_when_date_of_birth_is_invalid(self):
        exception_error_message = 'Assessee date of birth must not be null'
        request_data_missing_dob = self.base_request_data.copy()
        request_data_missing_dob['date_of_birth'] = ''

        try:
            registration.validate_user_assessee_registration_data(request_data_missing_dob)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        exception_error_message = 'Invalid date of birth format'
        request_data_invalid_dob = self.base_request_data.copy()
        request_data_invalid_dob['date_of_birth'] = '08-29-1990'

        try:
            registration.validate_user_assessee_registration_data(request_data_invalid_dob)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    @patch.object(Assessee.objects, 'create_user')
    def test_save_assessee_from_request_data(self, mocked_create_user):
        request_data = self.base_request_data.copy()
        mocked_create_user.return_value = self.expected_assessee

        saved_assessee = registration.save_assessee_from_request_data(request_data)

        mocked_create_user.assert_called_once()
        self.assertEqual(saved_assessee, self.expected_assessee)

    def test_register_assessee(self):
        request_data = self.base_request_data.copy()
        with patch.object(registration, 'validate_user_registration_data') as mocked_validate_user_registration_data:
            with patch.object(registration, 'validate_user_assessee_registration_data') \
                    as mocked_validate_user_assessee_registration_data:
                with patch.object(registration, 'save_assessee_from_request_data') \
                        as mocked_save_assessee_from_request_data:
                    mocked_validate_user_registration_data.return_value = None
                    mocked_validate_user_assessee_registration_data.return_value = mocked_validate_user_assessee_registration_data
                    mocked_save_assessee_from_request_data.return_value = self.expected_assessee

                    dummy_assessee = registration.register_assessee(request_data)

                    mocked_validate_user_registration_data.assert_called_once()
                    mocked_validate_user_assessee_registration_data.assert_called_once()
                    mocked_save_assessee_from_request_data.assert_called_once()
                    self.assertEqual(dummy_assessee, self.expected_assessee)


class ViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.registration_base_data = {
            'email': 'test_email_views_test_case@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': TEST_COMPANY_NAME,
            'company_description': TEST_COMPANY_DESCRIPTION,
            'company_address': TEST_COMPANY_ADDRESS
        }

    def fetch_with_data(self, registration_data, url_to_fetch):
        response = self.client.post(
            url_to_fetch,
            data=json.dumps(registration_data),
            content_type=REQUEST_CONTENT_TYPE
        )
        return response

    def test_register_company_when_complete(self):
        registration_data = self.registration_base_data.copy()
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertEqual(response_content['email'], registration_data['email'])
        self.assertEqual(response_content['company_name'], registration_data['company_name'])
        self.assertEqual(response_content['description'], registration_data['company_description'])
        self.assertEqual(response_content['address'], registration_data['company_address'])

    def test_register_company_when_company_already_registered(self):
        expected_message = 'Email test_email_views_test_case@gmail.com is already registered'
        registration_data = self.registration_base_data.copy()
        registration_data['email'] = 'test_emaiL_views_test_case@gmail.com'
        self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)

        registration_data = self.registration_base_data.copy()
        registration_data['email'] = 'test_emaIl_views_test_case@gmail.com'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_company_when_company_already_registered_but_different_email_case(self):
        expected_message = 'Email test_email_views_test_case@gmail.com is already registered'
        registration_data = self.registration_base_data.copy()
        registration_data['email'] = 'test_email_views_test_case@gmail.com'
        self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)

        registration_data = self.registration_base_data.copy()
        registration_data['email'] = 'test_email_views_test_case@gmaiL.com'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def base_test_register_company_when_invalid(self, registration_data, expected_message, expected_status_code):
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, expected_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_company_when_email_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['email'] = ''
        self.base_test_register_company_when_invalid(
            registration_data,
            EMAIL_MUST_NOT_BE_NULL,
            HTTPStatus.BAD_REQUEST
        )

        registration_data = self.registration_base_data.copy()
        registration_data['email'] = INVALID_EMAIL
        self.base_test_register_company_when_invalid(
            registration_data,
            EMAIL_IS_INVALID,
            HTTPStatus.BAD_REQUEST
        )

    def test_register_company_when_password_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['password'] = ''
        self.base_test_register_company_when_invalid(
            registration_data,
            PASSWORD_MUST_NOT_BE_NULL,
            HTTPStatus.BAD_REQUEST
        )

        registration_data = self.registration_base_data.copy()
        registration_data['password'] = 'password'
        self.base_test_register_company_when_invalid(
            registration_data,
            PASSWORD_INVALID_NO_UPPER,
            HTTPStatus.BAD_REQUEST
        )

    def test_register_company_with_invalid_company_name(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_name'] = ''
        expected_message = 'Company name must be of minimum 3 characters and maximum of 50 characters'
        self.base_test_register_company_when_invalid(
            registration_data,
            expected_message,
            HTTPStatus.BAD_REQUEST
        )

    def test_register_company_with_invalid_company_description(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_description'] = ''
        expected_message = 'Company description must be more than 3 characters'
        self.base_test_register_company_when_invalid(
            registration_data,
            expected_message,
            HTTPStatus.BAD_REQUEST
        )

    def test_register_company_with_invalid_company_address(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_address'] = 'JL'
        expected_message = 'Company address must be more than 3 characters'
        self.base_test_register_company_when_invalid(
            registration_data,
            expected_message,
            HTTPStatus.BAD_REQUEST
        )


class AssessorRegistrationTest(TestCase):
    def setUp(self) -> None:
        base_company_data = {
            'email': 'test_email_assessor_registration@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': TEST_COMPANY_NAME,
            'company_description': TEST_COMPANY_DESCRIPTION,
            'company_address': TEST_COMPANY_ADDRESS
        }

        self.client.post(
            REGISTER_COMPANY_URL,
            data=base_company_data,
            content_type=REQUEST_CONTENT_TYPE
        )

        self.company = Company.objects.get(email="test_email_assessor_registration@gmail.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            GENERATE_ONE_TIME_CODE_URL,
            content_type=REQUEST_CONTENT_TYPE
        )

        response_content = json.loads(response.content)
        self.one_time_code = response_content['code']

        self.base_request_data = {
            'email': 'assessor_registration@gmail.com',
            'password': 'testPassword1234',
            'confirmed_password': 'testPassword1234',
            'first_name': 'Abdul',
            'last_name': 'Jonathan',
            'phone_number': '+628127572735',
            'employee_id': 'AWZ123',
            'one_time_code': self.one_time_code,
        }

        self.expected_assessor = Assessor(
            email=self.base_request_data.get('email'),
            password=self.base_request_data.get('password'),
            first_name=self.base_request_data.get('first_name'),
            last_name=self.base_request_data.get('last_name'),
            phone_number=self.base_request_data.get('phone_number'),
            employee_id=self.base_request_data.get('employee_id'),
            associated_company=self.company,
        )

    def test_validate_user_assessor_registration_data_when_assessor_is_valid(self):
        request_data = self.base_request_data.copy()

        try:
            registration.validate_user_assessor_registration_data(request_data)
        except InvalidRegistrationException as exception:
            self.fail(f'{exception} is raised.')

    def test_validate_assessor_registration_data_with_invalid_first_name(self):
        exception_error_message = 'Assessor first name must not be null'
        request_data_missing_name = dict(self.base_request_data.copy())
        request_data_missing_name['first_name'] = ''

        try:
            validate_user_assessor_registration_data(request_data_missing_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_assessor_registration_data_with_invalid_phone_number(self):
        exception_error_message = 'Assessor phone number must not be null'
        request_data_missing_phone_number = dict(self.base_request_data.copy())
        request_data_missing_phone_number['phone_number'] = ''

        try:
            validate_user_assessor_registration_data(request_data_missing_phone_number)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_assessor_registration_data_with_invalid_one_time_code(self):
        exception_error_message = 'Registration code must not be null'
        request_data_missing_code = dict(self.base_request_data.copy())
        request_data_missing_code['one_time_code'] = ''

        try:
            validate_user_assessor_registration_data(request_data_missing_code)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        exception_error_message = 'Registration code is invalid'
        request_data_invalid_code = dict(self.base_request_data.copy())
        request_data_invalid_code['one_time_code'] = str(uuid.uuid4())

        try:
            validate_user_assessor_registration_data(request_data_invalid_code)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        exception_error_message = 'Registration code is expired'
        request_data_expired_code = dict(self.base_request_data.copy())

        self.client.post(
            REGISTER_ASSESSOR_URL,
            data=json.dumps(request_data_expired_code),
            content_type=REQUEST_CONTENT_TYPE
        )

        try:
            validate_user_assessor_registration_data(request_data_expired_code)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    @patch.object(Assessor.objects, 'create_user')
    def test_save_assessor_from_request_data(self, mocked_create_user):
        request_data = self.base_request_data.copy()
        mocked_create_user.return_value = self.expected_assessor

        saved_assessor = registration.save_assessor_from_request_data(request_data)

        mocked_create_user.assert_called_once()
        self.assertEqual(saved_assessor, self.expected_assessor)

    @patch.object(registration, 'save_assessor_from_request_data')
    @patch.object(registration, 'validate_user_assessor_registration_data')
    @patch.object(registration, 'validate_user_registration_data')
    def test_register_assessor(self, mocked_validate_user_registration_data,
                               mocked_validate_user_assessor_registration_data,
                               mocked_save_assessor_from_request_data):

        request_data = self.base_request_data.copy()
        mocked_validate_user_registration_data.return_value = None
        mocked_validate_user_assessor_registration_data.return_value = None
        mocked_save_assessor_from_request_data.return_value = self.expected_assessor

        dummy_assessor = registration.register_assessor(request_data)

        mocked_validate_user_registration_data.assert_called_once()
        mocked_validate_user_assessor_registration_data.assert_called_once()
        mocked_save_assessor_from_request_data.assert_called_once()
        self.assertEqual(dummy_assessor, self.expected_assessor)


class AssessorViewsTestCase(TestCase):
    def setUp(self) -> None:
        base_company_data = {
            'email': 'test_email_assessor_views@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': TEST_COMPANY_NAME,
            'company_description': TEST_COMPANY_DESCRIPTION,
            'company_address': TEST_COMPANY_ADDRESS
        }

        self.client.post(
            REGISTER_COMPANY_URL,
            data=base_company_data,
            content_type=REQUEST_CONTENT_TYPE
        )

        self.company = Company.objects.get(email="test_email_assessor_views@gmail.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            GENERATE_ONE_TIME_CODE_URL,
            content_type=REQUEST_CONTENT_TYPE
        )

        response_content = json.loads(response.content)
        self.one_time_code = response_content['code']

        self.base_registration_data = {
            'email': 'assessor_views_test@gmail.com',
            'password': 'testPassword1234',
            'confirmed_password': 'testPassword1234',
            'first_name': 'Abdul',
            'last_name': 'Jonathan',
            'phone_number': '+6281275725881',
            'employee_id': 'AWZ123',
            'one_time_code': self.one_time_code,
        }

    def fetch_with_data(self, registration_data, url_to_fetch):
        response = self.client.post(
            url_to_fetch,
            data=json.dumps(registration_data),
            content_type=REQUEST_CONTENT_TYPE
        )
        return response

    def test_register_assessor_when_complete(self):
        registration_data = self.base_registration_data.copy()
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertEqual(response_content['first_name'], registration_data['first_name'])
        self.assertEqual(response_content['last_name'], registration_data['last_name'])
        self.assertEqual(response_content['phone_number'], registration_data['phone_number'])
        self.assertEqual(response_content['employee_id'], registration_data['employee_id'])
        self.assertEqual(response_content['company_id'], str(self.company.company_id))

    def test_register_assessor_when_email_is_invalid(self):
        registration_data = self.base_registration_data.copy()
        registration_data['email'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_MUST_NOT_BE_NULL)

        registration_data = self.base_registration_data.copy()
        registration_data['email'] = INVALID_EMAIL
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_IS_INVALID)

    def test_register_assessor_when_password_is_invalid(self):
        registration_data = self.base_registration_data.copy()
        registration_data['password'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], PASSWORD_MUST_NOT_BE_NULL)

        registration_data = self.base_registration_data.copy()
        registration_data['password'] = 'password'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], PASSWORD_INVALID_NO_UPPER)

    def test_register_assessor_with_invalid_first_name(self):
        registration_data = self.base_registration_data.copy()
        registration_data['first_name'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        expected_message = 'Assessor first name must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_assessor_with_invalid_phone_number(self):
        registration_data = self.base_registration_data.copy()
        registration_data['phone_number'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        expected_message = 'Assessor phone number must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_assessor_with_invalid_one_time_code(self):
        registration_data = self.base_registration_data.copy()
        registration_data['one_time_code'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        expected_message = 'Registration code must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

        registration_data = self.base_registration_data.copy()
        registration_data['one_time_code'] = str(uuid.uuid4())
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        expected_message = 'Registration code is invalid'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

        registration_data = self.base_registration_data.copy()
        self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)

        response = self.fetch_with_data(registration_data, REGISTER_ASSESSOR_URL)
        expected_message = 'Email assessor_views_test@gmail.com is already registered'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)


class AssesseeViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.registration_base_data = {
                'email': 'assessee985@gmail.com',
                'password': 'testPassword1234',
                'confirmed_password': 'testPassword1234',
                'first_name': 'Anastasia',
                'last_name': 'Yuliana',
                'phone_number': '+6281275725990',
                'date_of_birth': '1994-09-30T10:37:35.849Z'
            }

    def fetch_with_data(self, registration_data, url_to_fetch):
        response = self.client.post(
            url_to_fetch,
            data=json.dumps(registration_data),
            content_type='application/json'
        )
        return response

    def test_register_assessee_when_complete(self):
        registration_data = self.registration_base_data.copy()
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertEqual(response_content['email'], registration_data['email'])
        self.assertEqual(response_content['first_name'], registration_data['first_name'])
        self.assertEqual(response_content['last_name'], registration_data['last_name'])
        self.assertEqual(response_content['phone_number'], registration_data['phone_number'])
        self.assertEqual(response_content['date_of_birth'], '1994-09-30')

    def test_register_assessee_when_email_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['email'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_MUST_NOT_BE_NULL)

        registration_data = self.registration_base_data.copy()
        registration_data['email'] = INVALID_EMAIL
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_IS_INVALID)

    def test_register_assessee_when_password_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['password'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], PASSWORD_MUST_NOT_BE_NULL)

        registration_data = self.registration_base_data.copy()
        registration_data['password'] = 'password'
        expected_message = 'Password length must contain at least 1 uppercase character'
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_assessee_with_invalid_first_name(self):
        registration_data = self.registration_base_data.copy()
        registration_data['first_name'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        expected_message = 'Assessee first name must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_assessee_with_invalid_phone_number(self):
        registration_data = self.registration_base_data.copy()
        registration_data['phone_number'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        expected_message = 'Assessee phone number must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_assessee_with_invalid_date_of_birth(self):
        registration_data = self.registration_base_data.copy()
        registration_data['date_of_birth'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        expected_message = 'Assessee date of birth must not be null'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

        registration_data = self.registration_base_data.copy()
        registration_data['date_of_birth'] = '09-1994-30T10:37:35.849Z'
        response = self.fetch_with_data(registration_data, REGISTER_ASSESSEE_URL)
        expected_message = 'Invalid date of birth format'
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)


class GenerateOneTimeCodeTest(TestCase):
    def setUp(self) -> None:
        base_company_data = {
            'email': 'test_email_generate_otc@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': TEST_COMPANY_NAME,
            'company_description': TEST_COMPANY_DESCRIPTION,
            'company_address': TEST_COMPANY_ADDRESS
        }

        self.client.post(
            REGISTER_COMPANY_URL,
            data=base_company_data,
            content_type=REQUEST_CONTENT_TYPE
        )

        self.company = Company.objects.get(email="test_email_generate_otc@gmail.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

    def test_generate_one_time_code_when_company_is_valid(self):
        company_email = self.company.email

        try:
            generate_one_time_code(company_email)
        except InvalidRegistrationException as exception:
            self.fail(f'{exception} is raised.')

    def test_generate_one_time_code_when_company_is_invalid(self):
        company_email = "fakeemail@gmail.co"
        exception_error_message = 'Company with email fakeemail@gmail.co is not found'

        try:
            generate_one_time_code(company_email)
            self.fail(EXCEPTION_NOT_RAISED)
        except EmailNotFoundException as exception:
            self.assertEqual(str(exception), exception_error_message)


class OneTimeCodeViewsTestCase(TestCase):
    def setUp(self) -> None:
        registration_data = {
            'email': 'test_email_otc_views@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': TEST_COMPANY_NAME,
            'company_description': TEST_COMPANY_DESCRIPTION,
            'company_address': TEST_COMPANY_ADDRESS
        }

        self.client.post(
            '/users/register-company/',
            data=json.dumps(registration_data),
            content_type=REQUEST_CONTENT_TYPE
        )

    def test_generate_assessor_one_time_code_when_complete_status_200(self):
        self.company = Company.objects.get(email="test_email_otc_views@gmail.com")
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

        response = self.client.post(
            GENERATE_ONE_TIME_CODE_URL,
            content_type=REQUEST_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        response_content = json.loads(response.content)
        one_time_code = CompanyOneTimeLinkCode.objects.get(code=response_content['code'])
        associated_company = one_time_code.associated_company

        self.assertTrue(len(response_content) > 0)
        self.assertEqual(associated_company, self.company)


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
            self.fail(EXCEPTION_NOT_RAISED)
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
            self.fail(EXCEPTION_NOT_RAISED)
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
            self.fail(EXCEPTION_NOT_RAISED)
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
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidGoogleAuthCodeException:
            pass


class GoogleLoginViewTest(TestCase):
    def setUp(self) -> None:
        self.dummy_response_data_from_auth_code = {
            'access_token': 'sample access token',
            'expires_in': 3599,
            'refresh_token': 'sample refresh token',
            'scope': 'scopes',
            'token_type': 'Bearer',
            'id_token': 'sample_id_token'
        }
        self.dummy_response_user_profile_data_from_id_token = {
            'iss': 'https://accounts.google.com',
            'azp': 'sample azp',
            'aud': 'sample aud',
            'sub': 'sample sub',
            'email': 'assessee1372@gmail.com',
            'email_verified': True,
            'at_hash': 'asdasda',
            'name': 'sample name',
            'picture': 'https://lh3.googleusercontent.com/a/ALm5wu2Sam1zn6zUtMWPxl9eO1Zt_y6HEi4sfHDPiuSk=s96-c',
            'given_name': 'SampleAssesseeFirstName',
            'family_name': 'SampleAssesseeLastName',
            'locale': 'id',
            'iat': 1664700260,
            'exp': 1664703860
        }
        self.assessor_company = Company.objects.create_user(email='company@company.com', password='Password123')
        self.assessee_google_registration_url = '/users/google/oauth/register/assessee/?code=<sample_code>'
        self.google_login_url = '/users/google/oauth/login/?code=<sample_code>'

    def create_and_save_assessor_data(self, authentication_service):
        expected_assessor = Assessor(
            email=self.dummy_response_user_profile_data_from_id_token['email'],
            first_name=self.dummy_response_user_profile_data_from_id_token['given_name'],
            last_name=self.dummy_response_user_profile_data_from_id_token['family_name'],
            associated_company=self.assessor_company,
            authentication_service=authentication_service
        )
        expected_assessor.save()

    @patch.object(id_token, 'verify_oauth2_token')
    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    def test_serve_google_register_assessee_callback_when_can_be_registered(self, mocked_post,
                                                                            mocked_json, mocked_verify_oauth2_token):
        mocked_post.return_value = requests.Response()
        mocked_json.return_value = self.dummy_response_data_from_auth_code
        mocked_verify_oauth2_token.return_value = self.dummy_response_user_profile_data_from_id_token
        response = self.client.get(self.assessee_google_registration_url)
        response_cookies = response.client.cookies
        self.assertIsNotNone(response_cookies.get('accessToken'))
        self.assertIsNotNone(response_cookies.get('refreshToken'))

    @patch.object(id_token, 'verify_oauth2_token')
    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    def test_serve_google_register_assessee_callback_when_can_not_be_registered(self,
                                                                                mocked_post, mocked_json,
                                                                                mocked_verify_oauth2_token):
        assessee = Assessee(
            email=self.dummy_response_user_profile_data_from_id_token['email'],
            first_name=self.dummy_response_user_profile_data_from_id_token['given_name'],
            last_name=self.dummy_response_user_profile_data_from_id_token['family_name'],
            authentication_service=AuthenticationService.DEFAULT
        )
        assessee.save()

        mocked_post.return_value = requests.Response()
        mocked_json.return_value = self.dummy_response_data_from_auth_code
        mocked_verify_oauth2_token.return_value = self.dummy_response_user_profile_data_from_id_token
        response = self.client.get(self.assessee_google_registration_url)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('message'))
        self.assertEqual(
            response_content['message'], 'User is already registered through the One Day Intern login service.'
        )

    @patch.object(id_token, 'verify_oauth2_token')
    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    def test_serve_google_login_callback(self, mocked_post, mocked_json, mocked_verify_oauth2_token):
        self.create_and_save_assessor_data(AuthenticationService.GOOGLE.value)
        mocked_post.return_value = requests.Response()
        mocked_json.return_value = self.dummy_response_data_from_auth_code
        mocked_verify_oauth2_token.return_value = self.dummy_response_user_profile_data_from_id_token
        response = self.client.get(self.google_login_url)
        response_cookies = response.client.cookies
        self.assertIsNotNone(response_cookies.get('accessToken'))
        self.assertIsNotNone(response_cookies.get('refreshToken'))

    @patch.object(id_token, 'verify_oauth2_token')
    @patch.object(requests.Response, 'json')
    @patch.object(requests.Session, 'post')
    def test_serve_google_login_callback_when_not_exist(self, mocked_post, mocked_json, mocked_verify_oauth2_token):
        self.create_and_save_assessor_data(AuthenticationService.DEFAULT.value)
        mocked_post.return_value = requests.Response()
        mocked_json.return_value = self.dummy_response_data_from_auth_code
        mocked_verify_oauth2_token.return_value = self.dummy_response_user_profile_data_from_id_token
        response = self.client.get(self.google_login_url)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('message'))
        self.assertEqual(
            response_content['message'],
            'Assessor or Assessee registering with google login with '
            f'{self.dummy_response_user_profile_data_from_id_token["email"]} email is not found.'
        )


class UserInfoViewTestCase(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company@email.com',
            password='Password123',
            company_name='PT Indonesia Sejahtera',
            description='PT Indonesia Sejahtera adalah sebuah PT',
            address='JL. PPL Jaya'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor_info@gmail.com',
            password='testPassword1234',
            first_name='Abdul',
            last_name='Jonathan',
            phone_number='+62812757251480',
            employee_id='AWZ123',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee = Assessee.objects.create_user(
            email='assessee1487@gmail.com',
            password='testPassword1234',
            first_name='Anastasia',
            last_name='Yuliana',
            phone_number='+6281275721491',
            date_of_birth='1994-09-30'
        )

    def test_serve_get_user_info_when_user_is_company(self):
        client = APIClient()
        client.force_authenticate(self.company)
        response = client.get(GET_USER_INFO_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('company_id'))
        self.assertEqual(response_content.get('email'), self.company.email)
        self.assertEqual(response_content.get('company_name'), self.company.company_name)
        self.assertEqual(response_content.get('description'), self.company.description)
        self.assertEqual(response_content.get('address'), self.company.address)

    def test_serve_get_user_info_when_user_is_assessor(self):
        client = APIClient()
        client.force_authenticate(self.assessor)
        response = client.get(GET_USER_INFO_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('first_name'), self.assessor.first_name)
        self.assertEqual(response_content.get('last_name'), self.assessor.last_name)
        self.assertEqual(response_content.get('phone_number'), self.assessor.phone_number)
        self.assertEqual(response_content.get('employee_id'), self.assessor.employee_id)
        self.assertEqual(response_content.get('company_id'), str(self.company.company_id))

    def test_serve_get_user_info_when_user_is_assessee(self):
        client = APIClient()
        client.force_authenticate(self.assessee)
        response = client.get(GET_USER_INFO_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('email'), self.assessee.email)
        self.assertEqual(response_content.get('first_name'), self.assessee.first_name)
        self.assertEqual(response_content.get('last_name'), self.assessee.last_name)
        self.assertEqual(response_content.get('phone_number'), self.assessee.phone_number)
        self.assertEqual(response_content.get('date_of_birth'), self.assessee.date_of_birth)