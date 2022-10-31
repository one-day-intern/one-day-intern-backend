from .utils import validate_phone_number
from ..models import OdiUser, Company, CompanyOneTimeLinkCode, Assessor, Assessee
from one_day_intern.exceptions import InvalidRegistrationException, EmailNotFoundException
from . import utils
import uuid


def validate_user_registration_data(request_data):
    email = request_data.get('email').lower()
    password = request_data.get('password')

    if not email:
        raise InvalidRegistrationException('Email must not be null')
    if not utils.validate_email(email):
        raise InvalidRegistrationException('Email is invalid')
    if OdiUser.objects.filter(email=email).exists():
        raise InvalidRegistrationException(f'Email {email} is already registered')
    if not password:
        raise InvalidRegistrationException('Password must not be null')

    validate_password_result = utils.validate_password(password)

    if not (validate_password_result['is_valid']):
        raise InvalidRegistrationException(validate_password_result['message'])
    if password != request_data.get('confirmed_password'):
        raise InvalidRegistrationException('Password must match password confirmation')


def validate_user_company_registration_data(request_data):
    if not (company_name := request_data.get('company_name')) or len(company_name) < 3 or len(company_name) > 50:
        raise InvalidRegistrationException('Company name must be of minimum 3 characters and maximum of 50 characters')
    if not (company_description := request_data.get('company_description')) or len(company_description) < 3:
        raise InvalidRegistrationException('Company description must be more than 3 characters')
    if not (company_address := request_data.get('company_address')) or len(company_address) < 3:
        raise InvalidRegistrationException('Company address must be more than 3 characters')


def validate_user_assessee_registration_data(request_data):
    if not request_data.get('first_name'):
        raise InvalidRegistrationException('Assessee first name must not be null')
    if not request_data.get('last_name'):
        raise InvalidRegistrationException('Assessee last name must not be null')
    if not request_data.get('phone_number'):
        raise InvalidRegistrationException('Assessee phone number must not be null')
    if not utils.validate_phone_number(request_data.get('phone_number')):
        raise InvalidRegistrationException('Phone number is invalid')
    if not request_data.get('date_of_birth'):
        raise InvalidRegistrationException('Assessee date of birth must not be null')
    if not utils.validate_date_format(request_data.get('date_of_birth')):
        raise InvalidRegistrationException('Invalid date of birth format')


def validate_user_assessor_registration_data(request_data):
    one_time_code = request_data.get('one_time_code')
    if not one_time_code:
        raise InvalidRegistrationException('Registration code must not be null')
    if not request_data.get('first_name'):
        raise InvalidRegistrationException('Assessor first name must not be null')
    if not request_data.get('phone_number'):
        raise InvalidRegistrationException('Assessor phone number must not be null')
    if not validate_phone_number(request_data.get('phone_number')):
        raise InvalidRegistrationException('Phone number is invalid')

    one_time_code = uuid.UUID(one_time_code)
    found_one_time_code = CompanyOneTimeLinkCode.objects.filter(code=one_time_code)

    if not found_one_time_code:
        raise InvalidRegistrationException('Registration code is invalid')
    if not found_one_time_code[0].is_active:
        raise InvalidRegistrationException('Registration code is expired')


def save_company_from_request_data(request_data):
    email = request_data.get('email')
    password = request_data.get('password')
    company_name = request_data.get('company_name')
    company_description = request_data.get('company_description')
    company_address = request_data.get('company_address')

    company = Company.objects.create_user(
        email=email,
        password=password,
        company_name=company_name,
        description=company_description,
        address=company_address
    )

    return company


def register_company(request_data):
    utils.sanitize_request_data(request_data)
    validate_user_registration_data(request_data)
    validate_user_company_registration_data(request_data)
    company = save_company_from_request_data(request_data)
    return company


def save_assessee_from_request_data(request_data):
    email = request_data.get('email')
    password = request_data.get('password')
    first_name = request_data.get('first_name')
    last_name = request_data.get('last_name')
    phone_number = request_data.get('phone_number')
    date_of_birth_text = request_data.get('date_of_birth')
    date_of_birth = utils.get_date_from_string(date_of_birth_text)

    assessee = Assessee.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        date_of_birth=date_of_birth,
    )

    return assessee


def save_assessor_from_request_data(request_data):
    email = request_data.get('email')
    password = request_data.get('password')
    first_name = request_data.get('first_name')
    last_name = request_data.get('last_name')
    phone_number = request_data.get('phone_number')
    employee_id = request_data.get('employee_id')
    one_time_code = uuid.UUID(request_data.get('one_time_code'))

    found_one_time_code = CompanyOneTimeLinkCode.objects.get(code=one_time_code)
    associated_company = found_one_time_code.associated_company
    found_one_time_code.is_active = False
    found_one_time_code.save()

    assessor = Assessor.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        employee_id=employee_id,
        associated_company=associated_company
    )

    return assessor


def register_assessee(request_data):
    validate_user_registration_data(request_data)
    validate_user_assessee_registration_data(request_data)
    assessee = save_assessee_from_request_data(request_data)
    return assessee


def register_assessor(request_data):
    validate_user_registration_data(request_data)
    validate_user_assessor_registration_data(request_data)
    assessor = save_assessor_from_request_data(request_data)
    return assessor


def generate_one_time_code(company_email):
    found_companies = Company.objects.filter(email=company_email)
    if not found_companies:
        raise EmailNotFoundException(f'Company with email {company_email} is not found')

    found_company = found_companies[0]
    one_time_code = CompanyOneTimeLinkCode.objects.create(associated_company=found_company)
    return one_time_code
