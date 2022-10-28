from datetime import datetime
from one_day_intern.exceptions import RestrictedAccessException
from users.models import Company
from one_day_intern import utils as odi_utils
from ..exceptions.exceptions import TestFlowDoesNotExist, InvalidAssessmentEventRegistration
from ..models import TestFlow, AssessmentEvent
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
