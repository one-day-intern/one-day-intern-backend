from django.contrib.auth.models import User
from one_day_intern.settings import EMAIL_HOST_USER
from users.models import Company, CompanyOneTimeLinkCode
from users.services import utils as users_utils
from . import utils, company as company_service
from one_day_intern.exceptions import InvalidRequestException


def validate_request_data(request_data: dict):
    if not request_data.get('assessor_emails'):
        raise InvalidRequestException('Request must contain at least 1 assessor emails')
    if not isinstance(request_data.get('assessor_emails'), list):
        raise InvalidRequestException('Request assessor_emails field must be a list')

    assessor_emails = request_data.get('assessor_emails')
    for email in assessor_emails:
        is_valid = users_utils.validate_email(email)
        if not is_valid:
            raise InvalidRequestException(f'{email} is not a valid email')


def generate_message(email: str, company: Company) -> tuple:
    one_time_code = CompanyOneTimeLinkCode.objects.create(associated_company=company)
    message = (
        'ODI Assessor Invitation',
        '',
        f"""
        <h2>Hello, There!</h2>
        <span>You have been invited to join <b>{company.company_name}</b> as an assessor.</span><br/>
        <span>
            By becoming an assessor, you are able to create future assessment events, response tests, video conferences
            and also grade assignments.
        </span><br/>
        <p>Please register through the following link https://www.google.com/?code={one_time_code.code}.</p>
        <img src="https://i.ibb.co/CzmHtCB/image.png" alt="One Day Intern" style="height:70px; width:auto">
        <div>
            <span style="font-size:0.8rem;font-weight:bold;">One Day Intern</span><br/>
            <span style="font-size:0.6rem">
                One Day Intern is an open-source project that aims in making fairer and more practical assessments.
            </span><br/>
            <span style="font-size:0.6rem">
                For further information, please contact us through onedayintern@gmail.com
            </span>
        </div>
        """,
        EMAIL_HOST_USER,
        [email]
    )
    return message


def email_one_time_code(request_data: dict, company: Company):
    assessor_emails = request_data.get('assessor_emails')
    messages_to_sent = []
    for email in assessor_emails:
        message = generate_message(email, company)
        messages_to_sent.append(message)
    utils.send_mass_html_mail(messages_to_sent)


def send_one_time_code_to_assessors(request_data: dict, user: User):
    company = company_service.get_company_or_raise_exception(user)
    validate_request_data(request_data)
    email_one_time_code(request_data, company)


