from django.contrib.auth.models import User
from one_day_intern.exceptions import (
    RestrictedAccessException,
    InvalidAssignmentRegistration,
    InvalidInteractiveQuizRegistration,
    InvalidResponseTestRegistration
)
from users.models import Assessor, Company
from . import utils
from ..models import Assignment, MultipleChoiceQuestion, InteractiveQuiz, TextQuestion, ResponseTest


def get_assessor_or_raise_exception(user: User):
    user_email = user.email
    found_assessors = Assessor.objects.filter(email=user_email)
    if len(found_assessors) > 0:
        return found_assessors[0]
    else:
        raise RestrictedAccessException(f'User {user_email} is not an assessor')


def get_assessor_or_company_or_raise_exception(user: User):
    user_email = user.email
    found_company = Company.objects.filter(email=user_email)
    found_assessors = Assessor.objects.filter(email=user_email)
    if len(found_assessors) > 0:
        return {
            "user": found_assessors[0],
            "type": "assessor"
        }
    if len(found_company) > 0:
        return {
            "user": found_company[0],
            "type": "company"
        }
    return RestrictedAccessException(f"User {user_email} is not a valid company or assessor")


def validate_assessment_tool(request_data):
    if not request_data.get('name'):
        raise InvalidAssignmentRegistration('Assessment name should not be empty')


def validate_assignment(request_data):
    if not request_data.get('duration_in_minutes'):
        raise InvalidAssignmentRegistration('Assignment should have duration')
    if not isinstance(request_data.get('duration_in_minutes'), int):
        raise InvalidAssignmentRegistration('Assignment duration must only be of type numeric')


def save_assignment_to_database(request_data: dict, assessor: Assessor):
    name = request_data.get('name')
    description = request_data.get('description')
    owning_company = assessor.associated_company
    expected_file_format = utils.sanitize_file_format(request_data.get('expected_file_format'))
    duration_in_minutes = request_data.get('duration_in_minutes')
    assignment = Assignment.objects.create(
        name=name,
        description=description,
        owning_company=owning_company,
        expected_file_format=expected_file_format,
        duration_in_minutes=duration_in_minutes
    )
    return assignment


def create_assignment(request_data, user):
    assessor = get_assessor_or_raise_exception(user)
    validate_assessment_tool(request_data)
    validate_assignment(request_data)
    assignment = save_assignment_to_database(request_data, assessor)
    return assignment

def validate_response_test(request_data):
    """
    response test MUST have subject and prompt
    """
    if len(request_data.get('prompt').split()) == 0:
        raise InvalidResponseTestRegistration('Prompt Should Not Be Empty')
    if len(request_data.get('subject').split()) == 0:
        raise InvalidResponseTestRegistration('Subject Should Not Be Empty')


def save_response_test_to_database(request_data: dict, assessor: Assessor):
    name = request_data.get('name')
    description = request_data.get('description')
    owning_company = assessor.associated_company
    prompt = request_data.get('prompt')
    subject = request_data.get('subject')
    sender = assessor
    assignment = ResponseTest.objects.create(
        name=name,
        description=description,
        owning_company=owning_company,
        prompt=prompt,
        subject=subject,
        sender=sender
    )
    return assignment


def create_response_test(request_data, user):
    assessor = get_assessor_or_raise_exception(user)
    validate_assessment_tool(request_data)
    validate_response_test(request_data)
    response_test = save_response_test_to_database(request_data, assessor)
    return response_test

def validate_interactive_quiz(request_data):
    if request_data.get('total_points') is None:
        raise InvalidInteractiveQuizRegistration('Interactive Quiz should have total points')
    if not isinstance(request_data.get('total_points'), int):
        raise InvalidInteractiveQuizRegistration('Interactive Quiz total points must only be of type numeric')

    if not request_data.get('duration_in_minutes'):
        raise InvalidInteractiveQuizRegistration('Interactive Quiz should have a duration')
    if not isinstance(request_data.get('duration_in_minutes'), int):
        raise InvalidInteractiveQuizRegistration('Interactive Quiz duration must only be of type numeric')


def save_question_to_database(question_data: dict, interactive_quiz: InteractiveQuiz):
    prompt = question_data.get('prompt')
    points = question_data.get('points')
    question_type = question_data.get('question_type')

    if question_type == 'multiple_choice':
        question = MultipleChoiceQuestion.objects.create(
            interactive_quiz=interactive_quiz,
            prompt=prompt,
            points=points,
            question_type=question_type
        )

        answers = question_data.get('answer_options')
        for answer in answers:
            question.save_answer_option_to_database(answer)
    else:
        answer_key = question_data.get('answer_key')

        question = TextQuestion.objects.create(
            interactive_quiz=interactive_quiz,
            prompt=prompt,
            points=points,
            question_type=question_type,
            answer_key=answer_key
        )
    return question


def save_interactive_quiz_to_database(request_data: dict, assessor: Assessor):
    name = request_data.get('name')
    description = request_data.get('description')
    owning_company = assessor.associated_company
    questions = request_data.get('questions')
    duration_in_minutes = request_data.get('duration_in_minutes')

    total_points = utils.get_interactive_quiz_total_points(questions)

    interactive_quiz = InteractiveQuiz.objects.create(
        name=name,
        description=description,
        owning_company=owning_company,
        total_points=total_points,
        duration_in_minutes=duration_in_minutes
    )

    return interactive_quiz


def validate_answer_option(answer):
    if not answer.get('content'):
        raise InvalidInteractiveQuizRegistration(f'Answer options should have content')

    if not isinstance(answer.get('correct'), bool):
        raise InvalidInteractiveQuizRegistration('Answer options should be either True or False')


def validate_question(question):
    if not question.get('prompt'):
        raise InvalidInteractiveQuizRegistration(f'Questions should have a prompt')

    if not question.get('question_type'):
        raise InvalidInteractiveQuizRegistration(f'Questions should have a type')

    if question.get('points') is None:
        raise InvalidInteractiveQuizRegistration('Question should have points')
    if not isinstance(question.get('points'), int):
        raise InvalidInteractiveQuizRegistration('Question points must only be of type numeric')

    if question.get('question_type') == 'multiple_choice':
        if len(question.get('answer_options')) <= 0:
            raise InvalidInteractiveQuizRegistration('Multiple Choice Questions should have answer options')

        true_option_counter = 0
        for answer in question.get('answer_options'):
            validate_answer_option(answer)
            true_option_counter += 1 if answer.get('correct') is True else 0

        if true_option_counter == 0 or true_option_counter > 1:
            raise InvalidInteractiveQuizRegistration('Multiple Choice Questions should one correct option')

    elif question.get('question_type') != 'text':
        raise InvalidInteractiveQuizRegistration('Question type should be either multiple choice or text')


def create_interactive_quiz(request_data, user):
    assessor = get_assessor_or_raise_exception(user)
    validate_assessment_tool(request_data)
    validate_interactive_quiz(request_data)

    questions = request_data.get('questions')
    for q in questions:
        validate_question(q)

    interactive_quiz = save_interactive_quiz_to_database(request_data, assessor)

    for q in questions:
        save_question_to_database(q, interactive_quiz)

    return interactive_quiz

