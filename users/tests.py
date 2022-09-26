from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch
from .services import registration
from .exceptions.exceptions import InvalidRegistrationException
from .models import OdiUser, Company
from .services import utils

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
        email = 'email@email.com'
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
    def test_validate_user_registration_data_when_request_is_valid(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                mocked_validate_email.return_value = True
                mocked_validate_password.return_value = {
                    'is_valid': True,
                    'message': None
                }

                request_data = {
                    'email': 'email@email.com',
                    'password': 'Password123',
                    'confirmed_password': 'Password123'
                }

                try:
                    registration.validate_user_registration_data(request_data)
                except Exception as exception:
                    self.fail(f'{exception} is raised.')

    def test_validate_user_registration_when_email_is_missing(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                expected_error_message = 'Email must not be null'
                mocked_validate_email.return_value = True
                mocked_validate_password.return_value = {
                    'is_valid': True,
                    'message': None
                }

                request_data = {
                    'email': '',
                    'password': 'Password123',
                    'confirmed_password': 'Password123'
                }

                try:
                    registration.validate_user_registration_data(request_data)
                    self.fail(EXCEPTION_NOT_RAISED)
                except InvalidRegistrationException as exception:
                    self.assertEqual(str(exception), expected_error_message)

    def test_validate_user_registration_when_password_is_missing(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                expected_error_message = 'Password must not be null'
                mocked_validate_email.return_value = True
                mocked_validate_password.return_value = {
                    'is_valid': True,
                    'message': None
                }

                request_data = {
                    'email': 'email@email.com',
                    'password': '',
                    'confirmed_password': ''
                }

                try:
                    registration.validate_user_registration_data(request_data)
                    self.fail(EXCEPTION_NOT_RAISED)
                except InvalidRegistrationException as exception:
                    self.assertEqual(str(exception), expected_error_message)

    def test_validate_user_registration_when_password_does_not_match_confirmation(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                expected_error_message = 'Password must match password confirmation'
                mocked_validate_email.return_value = True
                mocked_validate_password.return_value = {
                    'is_valid': True,
                    'message': None
                }

                request_data = {
                    'email': 'email@email.com',
                    'password': 'Password123',
                    'confirmed_password': 'passWord123'
                }

                try:
                    registration.validate_user_registration_data(request_data)
                    self.fail(EXCEPTION_NOT_RAISED)
                except InvalidRegistrationException as exception:
                    self.assertEqual(str(exception), expected_error_message)

    def test_validate_user_registration_when_email_is_invalid(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                expected_error_message = 'Email is invalid'
                mocked_validate_email.return_value = False
                mocked_validate_password.return_value = {
                    'is_valid': True,
                    'message': None
                }

                request_data = {
                    'email': 'email@email.com',
                    'password': 'Password123',
                    'confirmed_password': 'Password123'
                }

                try:
                    registration.validate_user_registration_data(request_data)
                    self.fail('Exception not raised')
                except InvalidRegistrationException as exception:
                    self.assertEqual(str(exception), expected_error_message)

    def test_validate_user_registration_when_password_is_invalid(self):
        with patch.object(utils, 'validate_email') as mocked_validate_email:
            with patch.object(utils, 'validate_password') as mocked_validate_password:
                expected_error_message = 'Password length must contain at least 1 number character'
                mocked_validate_email.return_value = True
                mocked_validate_password.return_value = {
                    'is_valid': False,
                    'message': expected_error_message
                }

                request_data = {
                    'email': 'email@email.com',
                    'password': 'Password',
                    'confirmed_password': 'Password'
                }

                try:
                    registration.validate_user_registration_data(request_data)
                    self.fail(EXCEPTION_NOT_RAISED)
                except InvalidRegistrationException as exception:
                    self.assertEqual(str(exception), expected_error_message)


class CompanyRegistrationTest(TestCase):
    def setUp(self) -> None:
        self.request_data = {
            'email': 'email@email.com',
            'password': 'Password123',
            'company_name': 'PT Indonesia Sejahtera',
            'company_description': 'PT Indonesia Sejahtera adalah sebuah PT',
            'company_address': 'JL. PPL Jaya'
        }

        self.expected_company = Company(
            email=self.request_data.get('email'),
            password=self.request_data.get('Password123'),
            company_name=self.request_data.get('company_name'),
            description=self.request_data.get('company_description'),
            address=self.request_data.get('company_address'),
        )

    def test_validate_user_company_registration_data_when_company_is_valid(self):
        request_data = dict(self.request_data)

        try:
            registration.validate_user_company_registration_data(request_data)
        except InvalidRegistrationException as exception:
            self.fail(f'{exception} is raised.')

    def test_validate_user_company_registration_data_when_company_name_is_not_valid(self):
        exception_error_message = 'Company name must be more than 3 characters'
        request_data_missing_name = dict(self.request_data)
        request_data_missing_name['company_name'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_name = dict(self.request_data)
        request_data_short_name['company_name'] = 'PT'

        try:
            registration.validate_user_company_registration_data(request_data_short_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_company_registration_data_when_company_description_is_not_valid(self):
        exception_error_message = 'Company description must be more than 3 characters'
        request_data_missing_description = dict(self.request_data)
        request_data_missing_description['company_description'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_description)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_description = dict(self.request_data)
        request_data_short_description['company_description'] = 'PT'

        try:
            registration.validate_user_company_registration_data(request_data_short_description)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_validate_user_company_registration_data_when_company_address_is_invalid(self):
        exception_error_message = 'Company address must be more than 3 characters'
        request_data_missing_address = dict(self.request_data)
        request_data_missing_address['company_address'] = ''

        try:
            registration.validate_user_company_registration_data(request_data_missing_address)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

        request_data_short_address = dict(self.request_data)
        request_data_short_address['company_address'] = 'JL'

        try:
            registration.validate_user_company_registration_data(request_data_short_address)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRegistrationException as exception:
            self.assertEqual(str(exception), exception_error_message)

    def test_save_company_from_request_data(self):
        request_data = dict(self.request_data)
        with patch.object(Company.objects, 'create_user') as mocked_create_user:
            mocked_create_user.return_value = self.expected_company
            saved_company = registration.save_company_from_request_data(request_data)

            mocked_create_user.assert_called_once()
            self.assertEqual(saved_company, self.expected_company)

    def test_register_company(self):
        request_data = dict(self.request_data)
        with patch.object(registration, 'validate_user_registration_data') as mocked_validate_user_registration_data:
            with patch.object(registration, 'validate_user_company_registration_data') \
                    as mocked_validate_user_company_registration_data:
                with patch.object(registration, 'save_company_from_request_data') \
                        as mocked_save_company_from_request_data:
                    mocked_validate_user_registration_data.return_value = None
                    mocked_validate_user_company_registration_data.return_value = \
                        mocked_validate_user_company_registration_data
                    mocked_save_company_from_request_data.return_value = self.expected_company

                    dummy_company = registration.register_company(request_data)

                    mocked_validate_user_registration_data.assert_called_once()
                    mocked_validate_user_company_registration_data.assert_called_once()
                    mocked_save_company_from_request_data.assert_called_once()
                    self.assertEqual(dummy_company, self.expected_company)
