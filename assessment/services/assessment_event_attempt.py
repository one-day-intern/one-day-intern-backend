from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from one_day_intern.decorators import catch_exception_and_convert_to_invalid_request_decorator
from one_day_intern.exceptions import RestrictedAccessException, InvalidRequestException
from one_day_intern.settings import GOOGLE_BUCKET_BASE_DIRECTORY, GOOGLE_STORAGE_BUCKET_NAME
from users.models import Assessee, Assessor
from .participation_validators import validate_user_participation
from ..exceptions.exceptions import EventDoesNotExist, AssessmentToolDoesNotExist
from ..models import (
    AssessmentEvent,
    AssignmentAttempt,
    Assignment,
    AssessmentTool,
    InteractiveQuiz,
    InteractiveQuizAttempt,
    Question,
    MultipleChoiceAnswerOptionAttempt,
    MultipleChoiceAnswerOption,
    TextQuestionAttempt,
    ResponseTest
)
from .TaskGenerator import TaskGenerator
from . import utils, google_storage
import mimetypes

ASSESEE_NOT_PART_OF_EVENT = 'Assessee with email {} is not part of assessment with id {}'


def subscribe_to_assessment_flow(request_data, user) -> TaskGenerator:
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_task_generator()


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=EventDoesNotExist)
def get_all_active_response_test(request_data: dict, user: User):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_released_response_tests()


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=EventDoesNotExist)
def get_all_active_assignment(request_data: dict, user: User):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_released_assignments()


def get_response_test_attempt(event: AssessmentEvent, response_test: ResponseTest, assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_response_test_attempt(response_test)
    return found_attempt


def validate_response_test_has_not_been_attempted(event: AssessmentEvent, response_test: ResponseTest, assessee: Assessee):
    found_attempt = get_response_test_attempt(event, response_test, assessee)
    if found_attempt:
        raise InvalidRequestException(f'Response test with id {response_test.assessment_id} has been attempted')


def save_response_test_response(event: AssessmentEvent, response_test: ResponseTest, assessee: Assessee, request_data):
    event_participation = event.get_assessment_event_participation_by_assessee(assessee)
    response_test_attempt = event_participation.create_response_test_attempt(response_test)
    response_test_attempt.set_subject(request_data.get('subject'))
    response_test_attempt.set_response(request_data.get('response'))


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=EventDoesNotExist)
def get_assessment_event_data(request_data, user: User):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event


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


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=(AssessmentToolDoesNotExist, EventDoesNotExist, ValidationError))
def submit_assignment(request_data, file, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = \
        event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
    validate_submission(assessment_tool, file.name)
    validate_attempt_is_submittable(assessment_tool, event)
    save_assignment_attempt(event, assessment_tool, assessee, file)


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


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=(EventDoesNotExist, AssessmentToolDoesNotExist))
def get_submitted_assignment(request_data, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(
        assessment_id=request_data.get('assessment-tool-id'))
    validate_tool_is_assignment(assessment_tool)
    downloaded_file = download_assignment_attempt(event, assessment_tool, assessee)
    return downloaded_file


def get_or_create_interactive_quiz_attempt(event: AssessmentEvent, interactive_quiz: InteractiveQuiz,
                                           assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_interactive_quiz_attempt(interactive_quiz)

    if found_attempt:
        return found_attempt
    else:
        return assessee_participation.create_interactive_quiz_attempt(interactive_quiz)


def validate_interactive_quiz_submission(assessment_tool):
    if assessment_tool is None:
        raise InvalidRequestException('Assessment tool associated with event does not exist')

    if not isinstance(assessment_tool, InteractiveQuiz):
        raise InvalidRequestException(f'Assessment tool with id {assessment_tool.assessment_id} '
                                      f'is not an interactive quiz')


def save_answer_attempts(interactive_quiz_attempt, attempt):
    answer_attempts = attempt['answers']
    for answer in answer_attempts:
        question_attempt = interactive_quiz_attempt.get_question_attempt(answer['question-id'])
        if question_attempt:
            question = Question.objects.get(question_id=answer['question-id'])
            question_type = question.question_type
            if question_type == "multiple_choice":
                answer_option_attempt = MultipleChoiceAnswerOptionAttempt.objects.get(answer_option_id=answer['answer-option-id'])
                answer_option_attempt.set_answer_option(answer['answer-option-id'])
            else:
                text_question_attempt = TextQuestionAttempt.objects.get(question=question)
                text_question_attempt.set_answer(answer['text-answer'])
        else:
            question = Question.objects.get(question_id=answer['question-id'])
            question_type = question.question_type

            if question_type == "multiple_choice":
                answer_option = MultipleChoiceAnswerOption.objects.get(answer_option_id=answer['answer-option-id'])
                MultipleChoiceAnswerOptionAttempt.objects.create(
                    question=question,
                    interactive_quiz_attempt=interactive_quiz_attempt,
                    is_answered=True,
                    selected_option=answer_option
                )
            else:
                text_answer = answer['text-answer']
                if text_answer != '':
                    TextQuestionAttempt.objects.create(
                        question=question,
                        interactive_quiz_attempt=interactive_quiz_attempt,
                        is_answered=True,
                        answer=text_answer
                    )


def save_interactive_quiz_attempt(event: AssessmentEvent, interactive_quiz: InteractiveQuiz, assessee: Assessee,
                                  attempt):
    interactive_quiz_attempt: InteractiveQuizAttempt = get_or_create_interactive_quiz_attempt(event,
                                                                                              interactive_quiz,
                                                                                              assessee)
    save_answer_attempts(interactive_quiz_attempt, attempt)


def submit_interactive_quiz_answers(request_data, user):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        assessment_tool = \
            event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
        validate_interactive_quiz_submission(assessment_tool)
        validate_attempt_is_submittable(assessment_tool, event)
        save_interactive_quiz_attempt(event, assessment_tool, assessee, request_data)

    except (AssessmentToolDoesNotExist, EventDoesNotExist, ValidationError) as exception:
        raise InvalidRequestException(str(exception))


def submit_interactive_quiz(request_data, user):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        assessment_tool = \
            event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
        interactive_quiz_attempt = get_or_create_interactive_quiz_attempt(event,
                                                                          assessment_tool,
                                                                          assessee)

        interactive_quiz_attempt.set_submitted_time()

    except (AssessmentToolDoesNotExist, EventDoesNotExist, ValidationError) as exception:
        raise InvalidRequestException(str(exception))
