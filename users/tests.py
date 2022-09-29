from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch
from .services import registration, utils
from .exceptions.exceptions import InvalidRegistrationException
from .models import OdiUser, Company
import json

EMAIL_IS_INVALID = 'Email is invalid'
EMAIL_MUST_NOT_BE_NULL = 'Email must not be null'
PASSWORD_MUST_NOT_BE_NULL = 'Password must not be null'
OK_REQUEST_STATUS_CODE = 200
BAD_REQUEST_STATUS_CODE = 400
REGISTER_COMPANY_URL = '/users/register-company/'
EXCEPTION_NOT_RAISED = 'Exception not raised'


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
        error_message = 'Password length must contain at least 1 uppercase character'
        validation_result = utils.validate_password('abcdefgh')

        self.assertFalse(validation_result['is_valid'])
        self.assertEqual(validation_result['message'], error_message)

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
        email = 'email@email'
        self.assertFalse(utils.validate_email(email))

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
        request_data['email'] = 'email@email'

        try:
            registration.validate_user_registration_data(request_data)
            self.fail('Exception not raised')
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
        exception_error_message = 'Company name must be more than 3 characters'
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


class ViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.registration_base_data = {
            'email': 'test_email@gmail.com',
            'password': 'Password1234',
            'confirmed_password': 'Password1234',
            'company_name': 'Dummy Company Name',
            'company_description': 'Dummy company description',
            'company_address': 'Dummy company address'
        }

    def fetch_with_data(self, registration_data, url_to_fetch):
        response = self.client.post(
            url_to_fetch,
            data=json.dumps(registration_data),
            content_type='application/json'
        )
        return response

    def test_register_company_when_complete(self):
        registration_data = self.registration_base_data.copy()
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, OK_REQUEST_STATUS_CODE)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertEqual(response_content['email'], registration_data['email'])
        self.assertEqual(response_content['company_name'], registration_data['company_name'])
        self.assertEqual(response_content['description'], registration_data['company_description'])
        self.assertEqual(response_content['address'], registration_data['company_address'])

    def test_register_company_when_email_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['email'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_MUST_NOT_BE_NULL)

        registration_data = self.registration_base_data.copy()
        registration_data['email'] = 'email@email'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], EMAIL_IS_INVALID)

    def test_register_company_when_password_is_invalid(self):
        registration_data = self.registration_base_data.copy()
        registration_data['password'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], PASSWORD_MUST_NOT_BE_NULL)

        registration_data = self.registration_base_data.copy()
        registration_data['password'] = 'password'
        expected_message = 'Password length must contain at least 1 uppercase character'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_company_with_invalid_company_name(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_name'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        expected_message = 'Company name must be more than 3 characters'
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_company_with_invalid_company_description(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_description'] = ''
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        expected_message = 'Company description must be more than 3 characters'
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)

    def test_register_company_with_invalid_company_address(self):
        registration_data = self.registration_base_data.copy()
        registration_data['company_address'] = 'JL'
        response = self.fetch_with_data(registration_data, REGISTER_COMPANY_URL)
        expected_message = 'Company address must be more than 3 characters'
        self.assertEqual(response.status_code, BAD_REQUEST_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['message'], expected_message)
