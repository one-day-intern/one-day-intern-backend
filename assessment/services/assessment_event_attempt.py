from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from one_day_intern.exceptions import RestrictedAccessException, InvalidRequestException
from one_day_intern.settings import GOOGLE_BUCKET_BASE_DIRECTORY, GOOGLE_STORAGE_BUCKET_NAME
from users.models import Assessee, Assessor
from ..exceptions.exceptions import EventDoesNotExist, AssessmentToolDoesNotExist
from ..models import AssessmentEvent, AssignmentAttempt, Assignment, AssessmentTool
from .TaskGenerator import TaskGenerator
from . import utils, google_storage
import mimetypes

ASSESEE_NOT_PART_OF_EVENT = 'Assessee with email {} is not part of assessment with id {}'


def validate_user_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise RestrictedAccessException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )


def validate_assessor_participation(assessment_event: AssessmentEvent, assessor: Assessor):
    if not assessment_event.check_assessor_participation(assessor):
        raise RestrictedAccessException(
            f'Assessor with email {assessor.email} is not part of assessment with id {assessment_event.event_id}'
        )


def subscribe_to_assessment_flow(request_data, user) -> TaskGenerator:
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_task_generator()


def get_all_active_assignment(request_data: dict, user: User):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        return event.get_released_assignments()
    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))


def get_assessment_event_data(request_data, user: User):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        return event
    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))


def get_or_create_assignment_attempt(event: AssessmentEvent, assignment: Assignment, assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_assignment_attempt(assignment)

    if found_attempt:
        return found_attempt
    else:
        return assessee_participation.create_assignment_attempt(assignment)


def validate_attempt_is_submittable(assessment_tool: AssessmentTool, event: AssessmentEvent):
    if not event.check_if_tool_is_submittable(assessment_tool):
        raise InvalidRequestException('Assessment is not accepting submissions at this time')


def validate_submission(assessment_tool, file_name):
    if assessment_tool is None:
        raise InvalidRequestException('Assessment tool associated with event does not exist')

    if not isinstance(assessment_tool, Assignment):
        raise InvalidRequestException(f'Assessment tool with id {assessment_tool.assessment_id} is not an assignment')

    if not file_name:
        raise InvalidRequestException('File name should not be empty')

    try:
        file_prefix = utils.get_prefix_from_file_name(file_name)
        if assessment_tool.expected_file_format and file_prefix != assessment_tool.expected_file_format:
            raise InvalidRequestException(
                f'File type does not match expected format (expected {assessment_tool.expected_file_format})'
            )

    except ValueError as exception:
        raise InvalidRequestException(str(exception))


def save_assignment_attempt(event: AssessmentEvent, assignment: Assignment, assessee: Assessee, file_to_be_uploaded):
    assignment_attempt: AssignmentAttempt = get_or_create_assignment_attempt(event, assignment, assessee)
    cloud_storage_file_name = f'{GOOGLE_BUCKET_BASE_DIRECTORY}/' \
                              f'{event.event_id}/' \
                              f'{assignment_attempt.tool_attempt_id}.{assignment.expected_file_format}'
    google_storage.upload_file_to_google_bucket(
        cloud_storage_file_name,
        GOOGLE_STORAGE_BUCKET_NAME,
        file_to_be_uploaded
    )
    assignment_attempt.update_attempt_cloud_directory(cloud_storage_file_name)
    assignment_attempt.update_file_name(file_to_be_uploaded.name)


def submit_assignment(request_data, file, user):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        assessment_tool = \
            event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
        validate_submission(assessment_tool, file.name)
        validate_attempt_is_submittable(assessment_tool, event)
        save_assignment_attempt(event, assessment_tool, assessee, file)

    except (AssessmentToolDoesNotExist, EventDoesNotExist, ValidationError) as exception:
        raise InvalidRequestException(str(exception))


def validate_tool_is_assignment(assessment_tool):
    if not isinstance(assessment_tool, Assignment):
        raise InvalidRequestException(f'Assessment tool with id {assessment_tool.assessment_id} is not an assignment')


def download_assignment_attempt(event: AssessmentEvent, assignment: Assignment, assessee: Assessee):
    event_participation = event.get_assessment_event_participation_by_assessee(assessee)
    assignment_attempt = event_participation.get_assignment_attempt(assignment)

    if assignment_attempt:
        cloud_storage_file_name = f'{GOOGLE_BUCKET_BASE_DIRECTORY}/' \
                                  f'{event.event_id}/' \
                                  f'{assignment_attempt.tool_attempt_id}.{assignment.expected_file_format}'
        expected_content_type = mimetypes.guess_type(assignment_attempt.filename)[0]
        downloaded_file = google_storage.download_file_from_google_bucket(
            cloud_storage_file_name,
            GOOGLE_STORAGE_BUCKET_NAME,
            assignment_attempt.filename,
            expected_content_type
        )
        return downloaded_file
    else:
        return None


def get_submitted_assignment(request_data, user):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        assessment_tool = event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
        validate_tool_is_assignment(assessment_tool)
        downloaded_file = download_assignment_attempt(event, assessment_tool, assessee)
        return downloaded_file
    except (EventDoesNotExist, AssessmentToolDoesNotExist) as exception:
        raise InvalidRequestException(str(exception))
