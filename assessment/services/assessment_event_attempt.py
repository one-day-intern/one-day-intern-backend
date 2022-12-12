from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from one_day_intern.decorators import catch_exception_and_convert_to_invalid_request_decorator
from one_day_intern.exceptions import RestrictedAccessException, InvalidRequestException
from one_day_intern.settings import GOOGLE_BUCKET_BASE_DIRECTORY, GOOGLE_STORAGE_BUCKET_NAME
from users.models import Assessee, Assessor
from .participation_validators import validate_user_participation
from ..exceptions.exceptions import (
    EventDoesNotExist,
    AssessmentToolDoesNotExist,
    QuestionAttemptDoesNotExist,
    QuestionDoesNotExist
)
from ..models import (
    AssessmentEvent,
    AssignmentAttempt,
    Assignment,
    AssessmentTool,
    InteractiveQuiz,
    InteractiveQuizAttempt,
    Question,
    QuestionAttempt,
    MultipleChoiceAnswerOptionAttempt,
    MultipleChoiceAnswerOption,
    TextQuestionAttempt,
    ResponseTest,
    ToolAttemptSerializer,
    MultipleChoiceAnswerOptionAttemptSerializer,
    TextQuestionAttemptSerializer,
    MultipleChoiceQuestion
)
from .TaskGenerator import TaskGenerator
from . import utils, google_storage
import mimetypes

ASSOCIATED_TOOL_NOT_FOUND = 'Assessment tool associated with event does not exist'
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


def get_or_create_interactive_quiz_attempt(event: AssessmentEvent, interactive_quiz: InteractiveQuiz,
                                           assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_interactive_quiz_attempt(interactive_quiz)

    if found_attempt:
        return found_attempt
    else:
        return assessee_participation.create_interactive_quiz_attempt(interactive_quiz)


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=EventDoesNotExist)
def get_all_active_interactive_quiz(request_data: dict, user: User):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_released_interactive_quizzes()


def validate_is_interactive_quiz(assessment_tool):
    if assessment_tool is None:
        raise InvalidRequestException(ASSOCIATED_TOOL_NOT_FOUND)

    if not isinstance(assessment_tool, InteractiveQuiz):
        raise InvalidRequestException(f'Assessment tool with id {assessment_tool.assessment_id} '
                                      f'is not an interactive quiz')


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=EventDoesNotExist)
def get_interactive_quiz_attempt(event: AssessmentEvent, quiz: InteractiveQuiz, assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_interactive_quiz_attempt(quiz)
    return found_attempt


def get_answer_options_data_submission(question):
    mc_question = MultipleChoiceQuestion.objects.get(question_id=question.question_id)
    answer_options = mc_question.get_answer_options()
    data = []

    for ao in answer_options:
        data.append({'answer-option-id': str(ao.get_answer_option_id()),
                     'content': ao.get_content(),
                     })
    return data


def combine_tool_attempt_data(tool_attempt):
    tool_attempt_data = ToolAttemptSerializer(tool_attempt).data

    combined_data = dict()
    combined_data['tool-attempt-id'] = tool_attempt_data.get('tool_attempt_id')
    combined_data['assessment-tool-attempted'] = tool_attempt_data.get('assessment_tool_attempted')
    combined_data['answer-attempts'] = list()

    question_attempts = tool_attempt.get_all_question_attempts()
    for qa in question_attempts:
        question = qa.get_question()

        question_type = question.get_question_type()
        if question_type == 'multiple_choice':
            mc_answer_option = MultipleChoiceAnswerOptionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
            mc_answer_option_data = MultipleChoiceAnswerOptionAttemptSerializer(mc_answer_option).data
            mcq_dict = dict()

            mcq_dict['question-attempt-id'] = mc_answer_option_data.get('question_attempt_id')
            mcq_dict['is-answered'] = mc_answer_option_data.get('is_answered')
            mcq_dict['prompt'] = question.get_prompt()
            mcq_dict['question-type'] = question_type
            mcq_dict['answer-options'] = get_answer_options_data_submission(question)
            mcq_dict['selected-answer-option-id'] = str(mc_answer_option_data.get('selected_option'))

            combined_data['answer-attempts'].append(mcq_dict)

        else:
            text_question_attempt = TextQuestionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
            tq_dict = dict()

            text_question_attempt_data = TextQuestionAttemptSerializer(text_question_attempt).data
            tq_dict['question-attempt-id'] = text_question_attempt_data.get('question_attempt_id')
            tq_dict['is-answered'] = text_question_attempt_data.get('is_answered')
            tq_dict['prompt'] = question.get_prompt()
            tq_dict['question-type'] = question_type
            tq_dict['answer'] = text_question_attempt_data.get('answer')

            combined_data['answer-attempts'].append(tq_dict)

    return combined_data


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=(EventDoesNotExist, AssessmentToolDoesNotExist))
def get_submitted_interactive_quiz(request_data, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
    validate_is_interactive_quiz(assessment_tool)
    quiz_attempt = get_or_create_interactive_quiz_attempt(event, interactive_quiz=assessment_tool, assessee=assessee)
    return combine_tool_attempt_data(quiz_attempt)


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=QuestionDoesNotExist)
def get_question_attempt_data(qa):
    question = qa.get_question()

    question_type = question.get_question_type()
    if question_type == 'multiple_choice':
        mc_answer_option = MultipleChoiceAnswerOptionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
        mc_answer_option_data = MultipleChoiceAnswerOptionAttemptSerializer(mc_answer_option).data
        mcq_dict = dict()

        mcq_dict['question-attempt-id'] = mc_answer_option_data.get('question_attempt_id')
        mcq_dict['is-answered'] = mc_answer_option_data.get('is_answered')
        mcq_dict['prompt'] = question.get_prompt()
        mcq_dict['question-type'] = question_type
        mcq_dict['answer-options'] = get_answer_options_data_submission(question)
        mcq_dict['selected-answer-option-id'] = str(mc_answer_option_data.get('selected_option'))

        question_data = mcq_dict

    else:
        text_question_attempt = TextQuestionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
        tq_dict = dict()

        text_question_attempt_data = TextQuestionAttemptSerializer(text_question_attempt).data
        tq_dict['question-attempt-id'] = text_question_attempt_data.get('question_attempt_id')
        tq_dict['is-answered'] = text_question_attempt_data.get('is_answered')
        tq_dict['prompt'] = question.get_prompt()
        tq_dict['question-type'] = question_type
        tq_dict['answer'] = text_question_attempt_data.get('answer')

        question_data = tq_dict

    return question_data


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=(EventDoesNotExist, AssessmentToolDoesNotExist, QuestionAttemptDoesNotExist))
def get_submitted_individual_question(request_data, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
    validate_is_interactive_quiz(assessment_tool)
    quiz_attempt = get_or_create_interactive_quiz_attempt(event, assessment_tool, assessee=assessee)
    question_attempt = quiz_attempt.get_question_attempt_with_attempt_id(request_data.get('question-attempt-id'))
    return get_question_attempt_data(question_attempt)


def get_response_test_attempt(event: AssessmentEvent, response_test: ResponseTest, assessee: Assessee):
    assessee_participation = event.get_assessment_event_participation_by_assessee(assessee)
    found_attempt = assessee_participation.get_response_test_attempt(response_test)
    return found_attempt


def validate_response_test_has_not_been_attempted(event: AssessmentEvent, response_test: ResponseTest,
                                                  assessee: Assessee):
    found_attempt = get_response_test_attempt(event, response_test, assessee)
    if found_attempt:
        raise InvalidRequestException(f'Response test with id {response_test.assessment_id} has been attempted')


def validate_response_test_request_is_valid(request_data):
    if not request_data.get('response'):
        raise InvalidRequestException('The response body should not be empty')
    if not isinstance(request_data.get('response'), str):
        raise InvalidRequestException('The response body should be a string')
    if request_data.get('subject') and not isinstance(request_data.get('subject'), str):
        raise InvalidRequestException('The response subject should be a string')


def save_response_test_response(event: AssessmentEvent, response_test: ResponseTest, assessee: Assessee, request_data):
    event_participation = event.get_assessment_event_participation_by_assessee(assessee)
    response_test_attempt = event_participation.create_response_test_attempt(response_test)
    response_test_attempt.set_subject(request_data.get('subject'))
    response_test_attempt.set_response(request_data.get('response'))


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def submit_response_test(request_data, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
    validate_attempt_is_submittable(assessment_tool, event)
    validate_tool_is_response_test(assessment_tool)
    validate_response_test_has_not_been_attempted(event, assessment_tool, assessee)
    validate_response_test_request_is_valid(request_data)
    save_response_test_response(event, assessment_tool, assessee, request_data)


def validate_tool_is_response_test(assessment_tool):
    if not assessment_tool:
        raise InvalidRequestException(ASSOCIATED_TOOL_NOT_FOUND)
    if not isinstance(assessment_tool, ResponseTest):
        raise InvalidRequestException(f'Assessment tool with id {assessment_tool.assessment_id} is not a response test')


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_submitted_response_test(request_data: dict, user: User):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(assessment_id=request_data.get('assessment-tool-id'))
    validate_tool_is_response_test(assessment_tool)
    response_test_attempt = get_response_test_attempt(event, response_test=assessment_tool, assessee=assessee)
    return response_test_attempt


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
        raise InvalidRequestException(ASSOCIATED_TOOL_NOT_FOUND)

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


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=(AssessmentToolDoesNotExist, EventDoesNotExist, ValidationError))
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


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=(EventDoesNotExist, AssessmentToolDoesNotExist))
def get_submitted_assignment(request_data, user):
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    assessment_tool = event.get_assessment_tool_from_assessment_id(
        assessment_id=request_data.get('assessment-tool-id'))
    validate_tool_is_assignment(assessment_tool)
    downloaded_file = download_assignment_attempt(event, assessment_tool, assessee)
    return downloaded_file


def update_question_attempt(question, question_attempt, answer):
    question_type = question.question_type
    if question_type == "multiple_choice":
        answer_option_attempt = MultipleChoiceAnswerOptionAttempt.objects.get(
            question_attempt_id=question_attempt.question_attempt_id)
        answer_option_attempt.set_selected_option(answer['answer-option-id'])
    else:
        text_question_attempt = TextQuestionAttempt.objects.get(question=question)
        text_question_attempt.set_answer(answer['text-answer'])


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=QuestionAttemptDoesNotExist)
def save_answer_attempts(interactive_quiz_attempt, attempt):
    answer_attempts = attempt['answers']
    for answer in answer_attempts:
        question_attempt = interactive_quiz_attempt.get_question_attempt_with_question_id(answer['question-id'])
        question = Question.objects.get(question_id=answer['question-id'])
        update_question_attempt(question, question_attempt, answer)


def save_interactive_quiz_attempt(event: AssessmentEvent, interactive_quiz: InteractiveQuiz, assessee: Assessee,
                                  attempt):
    interactive_quiz_attempt: InteractiveQuizAttempt = get_interactive_quiz_attempt(event,
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
        validate_is_interactive_quiz(assessment_tool)
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
