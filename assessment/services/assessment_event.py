from datetime import datetime
from one_day_intern import utils as odi_utils
from users.models import Company
from ..exceptions.exceptions import TestFlowDoesNotExist, InvalidAssessmentEventRegistration
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

    if start_date < datetime.now():
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


def validate_assessment_event_ownership(assessment_event: AssessmentEvent, company: Company):
    raise Exception


def convert_list_of_participants_emails_to_user_objects(list_of_participants, creating_company):
    raise Exception


def add_list_of_participants_to_event(event: AssessmentEvent, list_of_participants: list):
    pass


def add_assessment_event_participation(request_data, user):
    pass
