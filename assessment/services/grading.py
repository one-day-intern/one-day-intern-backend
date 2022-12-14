from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.decorators import catch_exception_and_convert_to_invalid_request_decorator
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from one_day_intern.settings import GOOGLE_STORAGE_BUCKET_NAME
from users.services import utils as user_utils
from ..models import (
    AssignmentAttempt,
    InteractiveQuizAttempt,
    MultipleChoiceAnswerOptionAttempt,
    TextQuestionAttempt,
    TextQuestionAttemptSerializer,
    QuestionAttempt,
    ToolAttemptSerializer,
    MultipleChoiceAnswerOptionAttemptSerializer,
    MultipleChoiceAnswerOptionSerializer,
    MultipleChoiceQuestion,
    ResponseTestAttempt,
    Question
)
from .participation_validators import validate_assessor_participation
from . import utils, google_storage
import mimetypes


def validate_grade_assessment_tool_request(request_data):
    if request_data.get('tool-attempt-id') is None:
        raise InvalidRequestException('Tool attempt id must exist')
    if request_data.get('grade') is not None and not isinstance(request_data.get('grade'), (float, int)):
        raise InvalidRequestException('Grade must be an integer or a floating point number')
    if request_data.get('note') is not None and not isinstance(request_data.get('note'), str):
        raise InvalidRequestException('Note must be a string')


def validate_assessor_responsibility(event, assessor, assessee):
    if not event.check_assessee_and_assessor_pair(assessee, assessor):
        raise RestrictedAccessException(
            f'{assessor} is not responsible for {assessee} on event with id {event.event_id}')


def validate_tool_attempt_is_for_assignment(tool_attempt):
    if not isinstance(tool_attempt, AssignmentAttempt):
        raise InvalidRequestException(f'Attempt with id {tool_attempt.tool_attempt_id} is not an assignment')


def set_grade_and_note_of_tool_attempt(tool_attempt, request_data):
    if request_data.get('grade'):
        tool_attempt.set_grade(request_data.get('grade'))

    if request_data.get('note'):
        tool_attempt.set_note(request_data.get('note'))


def get_assessor_or_raise_exception(user):
    try:
        return user_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def grade_assessment_tool(request_data, user):
    validate_grade_assessment_tool_request(request_data)
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    validate_assessor_participation(event, assessor)
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    set_grade_and_note_of_tool_attempt(tool_attempt, request_data)
    return tool_attempt


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_assignment_attempt_data(request_data, user):
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_assignment(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    return tool_attempt


def download_assignment_attempt(assignment_attempt: AssignmentAttempt):
    if assignment_attempt.get_attempt_cloud_directory() is not None:
        cloud_storage_file_name = assignment_attempt.get_attempt_cloud_directory()
        expected_content_type = mimetypes.guess_type(assignment_attempt.get_file_name())[0]
        download_file = google_storage.download_file_from_google_bucket(
            cloud_storage_file_name,
            GOOGLE_STORAGE_BUCKET_NAME,
            assignment_attempt.get_file_name(),
            expected_content_type
        )
        return download_file
    else:
        return None


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_assignment_attempt_file(request_data, user):
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    downloaded_file = download_assignment_attempt(tool_attempt)
    return downloaded_file


def validate_tool_attempt_is_for_interactive_quiz(tool_attempt):
    if not isinstance(tool_attempt, InteractiveQuizAttempt):
        raise InvalidRequestException(f'Attempt with id {tool_attempt.tool_attempt_id} is not an interactive quiz')


def set_multiple_choice_question_attempt_grade(mcq_attempt: MultipleChoiceAnswerOptionAttempt, request_data):
    if isinstance(request_data.get('is_correct'), bool):
        mcq_attempt.set_is_correct(request_data.get('is_correct'))

    if request_data.get('note'):
        mcq_attempt.set_note(request_data.get('note'))


def set_text_question_attempt_grade(tool_attempt, question_attempt: TextQuestionAttempt, request_data):
    if request_data.get('grade'):
        previous_points = question_attempt.get_point()
        question_attempt.set_point(request_data.get('grade'))
        if question_attempt.get_is_graded():
            tool_attempt.update_points(previous_points, request_data.get('grade'))
        else:
            tool_attempt.accumulate_points(request_data.get('grade'))
            question_attempt.set_is_graded()
        question_attempt.awarded_points = request_data.get('grade')
        question_attempt.save()

    if request_data.get('note'):
        question_attempt.set_note(request_data.get('note'))


def set_question_attempt_grade(tool_attempt, request_data):
    qtype = QuestionAttempt.objects.get(question_attempt_id=request_data.get('question-attempt-id')).get_question_type()

    if qtype == 'multiple_choice':
        mcq_attempt = MultipleChoiceAnswerOptionAttempt.objects.get(
            question_attempt_id=request_data.get('question-attempt-id'),
            selected_option_id=request_data.get('selected-option-id'))
        set_multiple_choice_question_attempt_grade(mcq_attempt, request_data)

    else:
        question_attempt = TextQuestionAttempt.objects.get(question_attempt_id=request_data.get('question-attempt-id'))
        set_text_question_attempt_grade(tool_attempt, question_attempt, request_data)


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def grade_interactive_quiz_individual_question(request_data, user):
    validate_grade_assessment_tool_request(request_data)
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_interactive_quiz(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    validate_assessor_participation(event, assessor)
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    set_question_attempt_grade(tool_attempt, request_data)
    iq_attempt: InteractiveQuizAttempt = InteractiveQuizAttempt.objects.get(tool_attempt_id=tool_attempt.tool_attempt_id)
    iq_attempt.calculate_total_points()
    return request_data.get('grade'), request_data.get('note')


def set_interactive_quiz_grade_and_note(tool_attempt, request_data):
    tool_attempt.calculate_total_points()
    if request_data.get('note'):
        tool_attempt.set_note(request_data.get('note'))
    return tool_attempt.get_grade(), tool_attempt.note


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def grade_interactive_quiz(request_data, user):
    validate_grade_assessment_tool_request(request_data)
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_interactive_quiz(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    validate_assessor_participation(event, assessor)
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    grade, note = set_interactive_quiz_grade_and_note(tool_attempt, request_data)
    return grade, note


def get_answer_options_data_grading(question):
    mc_question = MultipleChoiceQuestion.objects.get(question_id=question.question_id)
    answer_options = mc_question.get_answer_options()
    data = []

    for ao in answer_options:
        data.append({'answer-option-id': str(ao.get_answer_option_id()),
                     'content': ao.get_content(),
                     'correct': ao.is_correct()
                     })
    return data


def combine_tool_grading_data(tool_attempt):
    tool_attempt_data = ToolAttemptSerializer(tool_attempt).data

    combined_data = dict()
    combined_data['tool-attempt-id'] = tool_attempt_data.get('tool_attempt_id')
    combined_data['assessment-tool-id'] = tool_attempt_data.get('assessment_tool_attempted')
    combined_data['grade'] = tool_attempt_data.get('grade')
    combined_data['note'] = tool_attempt_data.get('note')
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
            mcq_dict['note'] = qa.get_note()
            mcq_dict['grade'] = str(mc_answer_option_data.get('point'))
            mcq_dict['question-points'] = str(question.get_points())
            mcq_dict['question-type'] = question_type
            mcq_dict['answer-options'] = get_answer_options_data_grading(question)
            mcq_dict['selected-answer-option-id'] = str(mc_answer_option_data.get('selected_option'))
            mcq_dict['is-correct'] = mc_answer_option_data.get('is_correct')

            combined_data['answer-attempts'].append(mcq_dict)

        else:
            text_question_attempt = TextQuestionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
            tq_dict = dict()

            text_question_attempt_data = TextQuestionAttemptSerializer(text_question_attempt).data
            tq_dict['question-attempt-id'] = text_question_attempt_data.get('question_attempt_id')
            tq_dict['is-answered'] = text_question_attempt_data.get('is_answered')
            tq_dict['prompt'] = question.get_prompt()
            tq_dict['grade'] = str(text_question_attempt.get_point())
            tq_dict['question-points'] = str(question.get_points())
            tq_dict['note'] = qa.get_note()
            tq_dict['question-type'] = question_type
            tq_dict['answer'] = text_question_attempt_data.get('answer')
            tq_dict['answer-key'] = text_question_attempt.get_answer_key()
            tq_dict['is-graded'] = text_question_attempt_data.get('is_graded')
            tq_dict['awarded-points'] = text_question_attempt_data.get('awarded_points')

            combined_data['answer-attempts'].append(tq_dict)

    return combined_data


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_interactive_quiz_grading_data(request_data, user):
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_interactive_quiz(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    combined_data = combine_tool_grading_data(tool_attempt)
    return combined_data


@catch_exception_and_convert_to_invalid_request_decorator(
    exception_types=ObjectDoesNotExist)
def get_question_data(qa, tool_attempt_id):
    question_data = dict()
    question_data['tool-attempt-id'] = tool_attempt_id

    question = qa.get_question()

    question_type = question.get_question_type()
    if question_type == 'multiple_choice':
        mc_answer_option = MultipleChoiceAnswerOptionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)
        mc_answer_option_data = MultipleChoiceAnswerOptionAttemptSerializer(mc_answer_option).data

        question_data['question-attempt-id'] = mc_answer_option_data.get('question_attempt_id')
        question_data['is-answered'] = mc_answer_option_data.get('is_answered')
        question_data['prompt'] = question.get_prompt()
        question_data['note'] = qa.get_note()
        question_data['grade'] = str(mc_answer_option_data.get('point'))
        question_data['question-points'] = str(question.get_points())
        question_data['question-type'] = question_type
        question_data['answer-options'] = get_answer_options_data_grading(question)
        question_data['selected-answer-option-id'] = str(mc_answer_option_data.get('selected_option'))
        question_data['is-correct'] = mc_answer_option_data.get('is_correct')

    else:
        text_question_attempt = TextQuestionAttempt.objects.get(question_attempt_id=qa.question_attempt_id)

        text_question_attempt_data = TextQuestionAttemptSerializer(text_question_attempt).data
        question_data['question-attempt-id'] = text_question_attempt_data.get('question_attempt_id')
        question_data['is-answered'] = text_question_attempt_data.get('is_answered')
        question_data['prompt'] = question.get_prompt()
        question_data['note'] = qa.get_note()
        question_data['grade'] = str(text_question_attempt.get_point())
        question_data['question-points'] = str(question.get_points())
        question_data['question-type'] = question_type
        question_data['answer'] = text_question_attempt_data.get('answer')
        question_data['answer-key'] = text_question_attempt.get_answer_key()
        question_data['is-graded'] = text_question_attempt_data.get('is_graded')

    return question_data


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_question_grading_data(request_data, user):
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_interactive_quiz(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    question_attempt = tool_attempt.get_question_attempt(request_data.get('question-attempt-id'))
    return get_question_data(question_attempt, request_data.get('tool-attempt-id'))


def validate_tool_attempt_is_for_response_test(tool_attempt):
    if not isinstance(tool_attempt, ResponseTestAttempt):
        raise InvalidRequestException(f'Attempt with id {tool_attempt.tool_attempt_id} is not a response test')


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_response_test_attempt_data(request_data, user):
    tool_attempt = utils.get_tool_attempt_from_id(request_data.get('tool-attempt-id'))
    validate_tool_attempt_is_for_response_test(tool_attempt)
    assessor = get_assessor_or_raise_exception(user)
    event = tool_attempt.get_event_of_attempt()
    assessee = tool_attempt.get_user_of_attempt()
    validate_assessor_responsibility(event, assessor, assessee)
    return tool_attempt
