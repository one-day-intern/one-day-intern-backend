from django.test import TestCase
from unittest.mock import patch
from django.core import mail
from django.core.mail.backends.smtp import EmailBackend
from .services import utils


class OneTimeCodeTest(TestCase):
    def assert_message_equal(self, message_1: mail.EmailMultiAlternatives, message_2: mail.EmailMultiAlternatives):
        self.assertEqual(message_1.subject, message_2.subject)
        self.assertEqual(message_1.body, message_2.body)
        self.assertEqual(message_1.from_email, message_2.from_email)
        self.assertEqual(message_1.to[0], message_2.to[0])

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
