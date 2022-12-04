from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from one_day_intern import utils as odi_utils
from one_day_intern.exceptions import RestrictedAccessException
from users.models import Company
from ..exceptions.exceptions import TestFlowDoesNotExist, InvalidAssessmentEventRegistration, EventDoesNotExist
from ..models import AssessmentEvent
from . import utils


def validate_assessment_event(request_data, creating_company):
    if not odi_utils.text_value_is_valid(request_data.get('name'), min_length=3, max_length=50):
        raise InvalidAssessmentEventRegistration(
            'Assessment Event name must be minimum of length 3 and at most 50 characters'
        )

    if not request_data.get('start_date'):
        raise InvalidAssessmentEventRegistration('Assessment Event should have a start date')

    if not request_data.get('test_flow_id'):
        raise InvalidAssessmentEventRegistration('Assessment Event should use a test flow')

    try:
        start_date = utils.get_date_from_date_time_string(request_data.get('start_date'))
    except ValueError as exception:
        raise InvalidAssessmentEventRegistration(str(exception))

    if start_date.date() < date.today():
        raise InvalidAssessmentEventRegistration('The assessment event must not begin on a previous date.')

    try:
        utils.get_active_test_flow_of_company_from_id(request_data.get('test_flow_id'), creating_company)
    except TestFlowDoesNotExist as exception:
        raise InvalidAssessmentEventRegistration(str(exception))


def save_assessment_event(request_data, creating_company):
    name = request_data.get('name')
    start_date_time = utils.get_date_from_date_time_string(request_data.get('start_date'))
    test_flow = utils.get_active_test_flow_of_company_from_id(request_data.get('test_flow_id'), creating_company)
    assessment_event = AssessmentEvent.objects.create(
        name=name,
        start_date_time=start_date_time,
        owning_company=creating_company,
        test_flow_used=test_flow
    )

    return assessment_event


def create_assessment_event(request_data, user):
    company = utils.get_company_or_assessor_associated_company_from_user(user)
    validate_assessment_event(request_data, company)
    assessment_event = save_assessment_event(request_data, company)
    return assessment_event


def validate_add_assessment_participant(request_data):
    if not request_data.get('assessment_event_id'):
        raise InvalidAssessmentEventRegistration('Assessment Event Id should be present in the request body')
    if not request_data.get('list_of_participants'):
        raise InvalidAssessmentEventRegistration('The request should include a list of participants')
    if not isinstance(request_data.get('list_of_participants'), list):
        raise InvalidAssessmentEventRegistration('List of participants should be a list')

    try:
        utils.get_assessment_event_from_id(request_data.get('assessment_event_id'))
    except EventDoesNotExist as exception:
        raise InvalidAssessmentEventRegistration(str(exception))


def validate_assessment_event_ownership(assessment_event: AssessmentEvent, company: Company):
    if not assessment_event.check_company_ownership(company):
        raise RestrictedAccessException(
            f'Event with id {assessment_event.event_id} does not belong to company with id {company.company_id}'
        )


def convert_list_of_participants_emails_to_user_objects(list_of_participants, creating_company):
    converted_list_of_participants = []

    try:
        for participant_data in list_of_participants:
            assessee = utils.get_assessee_from_email(participant_data.get('assessee_email'))
            assessor = utils.get_company_assessor_from_email(participant_data.get('assessor_email'), creating_company)
            converted_list_of_participants.append((assessee, assessor))
    except ObjectDoesNotExist as exception:
        raise InvalidAssessmentEventRegistration(str(exception))

    return converted_list_of_participants


def add_list_of_participants_to_event(event: AssessmentEvent, list_of_participants: list):
    for assessee, assessor in list_of_participants:
        event.add_participant(assessee=assessee, assessor=assessor)


def add_assessment_event_participation(request_data, user):
    validate_add_assessment_participant(request_data)
    company = utils.get_company_or_assessor_associated_company_from_user(user)
    event = utils.get_assessment_event_from_id(request_data.get('assessment_event_id'))
    validate_assessment_event_ownership(event, company)
    converted_list_of_participants = \
        convert_list_of_participants_emails_to_user_objects(request_data.get('list_of_participants'), company)
    add_list_of_participants_to_event(event, converted_list_of_participants)
