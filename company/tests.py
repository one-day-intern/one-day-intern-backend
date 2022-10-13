from django.test import TestCase
from unittest.mock import patch
from django.core import mail
from django.core.mail.backends.smtp import EmailBackend
from rest_framework.test import APIClient
from .services import utils, one_time_code, company as company_service
from users.models import (
    Company,
    CompanySerializer,
    CompanyOneTimeLinkCode,
    Assessor,
    AuthenticationService
)
from assessment.exceptions.exceptions import RestrictedAccessException
from .exceptions.exceptions import InvalidRequestException
from users.services import utils as users_utils
from one_day_intern import settings
import uuid
import json
import http

EXCEPTION_NOT_RAISED = 'Exception not raised'
SEND_ONE_TIME_CODE_URL = '/company/one-time-code/generate/'


class OneTimeCodeTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company@company.com',
            password='Password123',
            description='A Company',
            address='Hacker Way, Menlo Park, 94025'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor@assessor.com',
            password='password',
            first_name='Levinson',
            last_name='Durbin',
            phone_number='+6282312345678',
            employee_id='A&EX4NDER',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.base_request_data = {
            'assessor_emails': [
                'one-day-intern@gmail.com',
                'one-day-intern@yahoo.com'
            ]
        }

    def assert_message_equal(self, message_1: mail.EmailMultiAlternatives, message_2: mail.EmailMultiAlternatives):
        self.assertEqual(message_1.subject, message_2.subject)
        self.assertEqual(message_1.body, message_2.body)
        self.assertEqual(message_1.from_email, message_2.from_email)
        self.assertEqual(message_1.to[0], message_2.to[0])

    def assert_invalid_request_response_matches(self, user, data, http_status_code, message,
                                                mocked_send_mass_html_mail):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(SEND_ONE_TIME_CODE_URL, data=data, content_type='application/json')
        mocked_send_mass_html_mail.assert_not_called()
        self.assertEqual(response.status_code, http_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), message)

    @patch.object(EmailBackend, 'send_messages')
    @patch.object(mail, 'get_connection')
    def test_send_mass_html_mail_when_no_datatuple(self, mocked_get_connection, mocked_send_messages):
        mocked_get_connection.return_value = EmailBackend()
        datatuple = []
        expected_messages_sent = []
        utils.send_mass_html_mail(datatuple)
        mocked_send_messages.assert_called_with(expected_messages_sent)

    @patch.object(EmailBackend, 'send_messages')
    @patch.object(mail, 'get_connection')
    def test_send_mass_html_when_datatuple_is_not_empty(self, mocked_get_connection, mocked_send_messages):
        mocked_get_connection.return_value = EmailBackend()
        datatuple = [
            ('Subject 1', 'Hello, World! 1', '<h1>Hello, World! 1</h1>', 'from_email1@gmail.com',
             ['recipient1@gmail.com']),
            ('Subject 2', 'Hello, World! 2', '<h1>Hello, World! 2</h1>', 'from_email2@gmail.com',
             ['recipient2@gmail.com']),
        ]
        expected_message_1 = mail.EmailMultiAlternatives(
            subject='Subject 1',
            body='Hello, World! 1',
            from_email='from_email1@gmail.com',
            to=['recipient1@gmail.com']
        )
        expected_message_1.attach_alternative('<h1>Hello, World! 1</h1>', 'text/html')
        expected_message_2 = mail.EmailMultiAlternatives(
            subject='Subject 2',
            body='Hello, World! 2',
            from_email='from_email2@gmail.com',
            to=['recipient2@gmail.com']
        )
        expected_message_2.attach_alternative('<h1>Hello, World! 2</h1>', 'text/html')

        utils.send_mass_html_mail(datatuple)

        mocked_send_messages.assert_called_once()
        call_arguments = list(mocked_send_messages.call_args)[0][0]
        self.assertTrue(len(call_arguments) == 2)
        actual_message_1, actual_message_2 = call_arguments
        self.assert_message_equal(actual_message_1, expected_message_1)
        self.assert_message_equal(actual_message_2, expected_message_2)

    def test_get_company_or_raise_exception_when_company_exists(self):
        expected_company_data = CompanySerializer(self.company).data
        company = company_service.get_company_or_raise_exception(self.company)
        company_data = CompanySerializer(company).data
        self.assertDictEqual(company_data, expected_company_data)

    def test_get_company_or_raise_exception_when_company_does_not_exist(self):
        expected_message = f'User {self.assessor.email} is not a company'
        try:
            company_service.get_company_or_raise_exception(self.assessor)
            self.fail(EXCEPTION_NOT_RAISED)
        except RestrictedAccessException as exception:
            self.assertEqual(str(exception), expected_message)

    def test_validate_request_data_when_request_is_valid(self):
        try:
            one_time_code.validate_request_data(self.base_request_data)
        except InvalidRequestException as exception:
            self.fail(f'{exception} is raised')

    def test_validate_request_data_when_assessor_emails_not_present(self):
        request_data = {'attribute': 'value'}
        expected_message = 'Request must contain at least 1 assessor emails'

        try:
            one_time_code.validate_request_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), expected_message)

    def test_validate_request_data_when_assessor_emails_is_not_a_list(self):
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = 'one-day-intern@gmail.com'
        expected_message = 'Request assessor_emails field must be a list'

        try:
            one_time_code.validate_request_data(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(users_utils, 'validate_email')
    def test_validate_request_data_when_one_or_more_emails_is_invalid(self, mocked_validate_email):
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = ['assessor@yahoo.com', 'assessor@mail', 'assesspr@gmail.com']
        expected_message = 'assessor@mail is not a valid email'
        try:
            one_time_code.validate_request_data(request_data)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(CompanyOneTimeLinkCode.objects, 'create')
    def test_generate_message(self, mocked_one_time_code_create):
        company_one_time_code = CompanyOneTimeLinkCode(
            associated_company=self.company,
            code=uuid.UUID('1895e8ad-a541-4d3a-86ba-8fdcce4954d8'),
            is_active=True
        )
        mocked_one_time_code_create.return_value = company_one_time_code
        email = self.base_request_data.get('assessor_emails')[0]
        subject = 'ODI Assessor Invitation'
        text_content = ''
        expected_sender = settings.EMAIL_HOST_USER
        expected_receivers = [email]

        returned_message = one_time_code.generate_message(email, self.company)

        self.assertEqual(returned_message[0], subject)
        self.assertEqual(returned_message[1], text_content)
        self.assertInHTML(self.company.company_name, returned_message[2])
        self.assertIn(str(company_one_time_code.code), returned_message[2])
        self.assertEqual(returned_message[3], expected_sender)
        self.assertEqual(returned_message[4], expected_receivers)

    @patch.object(utils, 'send_mass_html_mail')
    def test_email_one_time_code_when_assessor_emails_is_not_empty(self, mocked_send_html_mail):
        expected_message_1_receivers = [self.base_request_data.get('assessor_emails')[0]]
        expected_message_2_receivers = [self.base_request_data.get('assessor_emails')[1]]

        one_time_code.email_one_time_code(self.base_request_data, self.company)
        mocked_send_html_mail.assert_called_once()
        call_arguments = mocked_send_html_mail.call_args.args[0]
        message_1, message_2 = call_arguments
        message_1_receivers = message_1[4]
        message_2_receivers = message_2[4]

        self.assertEqual(message_1_receivers, expected_message_1_receivers)
        self.assertEqual(message_2_receivers, expected_message_2_receivers)

    @patch.object(utils, 'send_mass_html_mail')
    def test_email_one_time_code_when_assessor_emails_is_empty(self, mocked_send_html_mail):
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = []

        one_time_code.email_one_time_code(request_data, self.company)
        mocked_send_html_mail.assert_called_once()
        call_arguments = mocked_send_html_mail.call_args.args[0]
        self.assertEqual(len(call_arguments), 0)

    @patch.object(utils, 'send_mass_html_mail')
    def test_send_one_time_code_to_assessors(self, mocked_send_mass_html_mail):
        mocked_send_mass_html_mail.return_value = None
        try:
            one_time_code.send_one_time_code_to_assessors(self.base_request_data, self.company)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'send_mass_html_mail')
    def test_serve_send_one_time_code_to_assessors_when_valid_status_200(self, mocked_send_mass_html_mail):
        receiving_emails = self.base_request_data.get('assessor_emails')
        expected_message = 'Invitations has been sent'
        assessor_email_data = json.dumps(self.base_request_data)
        client = APIClient()
        client.force_authenticate(user=self.company)

        response = client.post(SEND_ONE_TIME_CODE_URL, data=assessor_email_data, content_type='application/json')

        mocked_send_mass_html_mail.assert_called_once()
        messages_sent = mocked_send_mass_html_mail.call_args.args[0]
        self.assertEqual(len(messages_sent), len(receiving_emails))
        self.assertEqual(response.status_code, http.HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), expected_message)

    @patch.object(utils, 'send_mass_html_mail')
    def test_serve_send_one_time_code_to_assessors_when_user_is_not_company(self, mocked_send_mass_html_mail):
        expected_message = 'User assessor@assessor.com is not a company'
        assessor_email_data = json.dumps(self.base_request_data)
        self.assert_invalid_request_response_matches(
            user=self.assessor,
            data=assessor_email_data,
            http_status_code=http.HTTPStatus.UNAUTHORIZED,
            message=expected_message,
            mocked_send_mass_html_mail=mocked_send_mass_html_mail
        )

    @patch.object(utils, 'send_mass_html_mail')
    def test_serve_send_one_time_code_to_assessors_when_assessor_emails_empty(self, mocked_send_mass_html_mail):
        expected_message = 'Request must contain at least 1 assessor emails'
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = []
        assessor_email_data = json.dumps(request_data)
        self.assert_invalid_request_response_matches(
            user=self.company,
            data=assessor_email_data,
            http_status_code=http.HTTPStatus.BAD_REQUEST,
            message=expected_message,
            mocked_send_mass_html_mail=mocked_send_mass_html_mail
        )

    @patch.object(utils, 'send_mass_html_mail')
    def test_serve_one_time_code_to_assessors_when_assessor_emails_not_a_list(self, mocked_send_mass_html_mail):
        expected_message = 'Request assessor_emails field must be a list'
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = 'one-day-intern@gmail.com'
        assessor_email_data = json.dumps(request_data)
        self.assert_invalid_request_response_matches(
            user=self.company,
            data=assessor_email_data,
            http_status_code=http.HTTPStatus.BAD_REQUEST,
            message=expected_message,
            mocked_send_mass_html_mail=mocked_send_mass_html_mail
        )

    @patch.object(utils, 'send_mass_html_mail')
    def test_serve_one_time_code_to_assessors_when_assessor_emails_are_invalid(self, mocked_send_mass_html_mail):
        expected_message = 'email@email is not a valid email'
        request_data = self.base_request_data.copy()
        request_data['assessor_emails'] = ['email@email']
        assessor_email_data = json.dumps(request_data)
        self.assert_invalid_request_response_matches(
            user=self.company,
            data=assessor_email_data,
            http_status_code=http.HTTPStatus.BAD_REQUEST,
            message=expected_message,
            mocked_send_mass_html_mail=mocked_send_mass_html_mail
        )
