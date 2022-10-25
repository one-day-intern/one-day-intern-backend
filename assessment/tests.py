from django.test import TestCase
from users.models import (
    Company,
    Assessor,
    Assessee,
    AuthenticationService,
    AssessorSerializer
)
from rest_framework.test import APIClient
from unittest.mock import patch
from .models import Assignment, AssignmentSerializer, InteractiveQuizSerializer, InteractiveQuiz, \
    MultipleChoiceQuestion, MultipleChoiceAnswerOption, TextQuestion, TextQuestionSerializer, QuestionSerializer, \
    MultipleChoiceQuestionSerializer
from .exceptions.exceptions import RestrictedAccessException, InvalidAssignmentRegistration, \
    InvalidInteractiveQuizRegistration
from .services import assessment, utils
import datetime
import json

EXCEPTION_NOT_RAISED = 'Exception not raised'
CREATE_ASSIGNMENT_URL = '/assessment/create/assignment/'
CREATE_INTERACTIVE_QUIZ_URL = '/assessment/create/interactive-quiz/'
OK_RESPONSE_STATUS_CODE = 200


class AssessmentTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company@company.com',
            password='password',
            company_name='Company',
            description='Company Description',
            address='JL. Company Levinson Durbin Householder'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor@assessor.com',
            password='password',
            first_name='Levinson',
            last_name='Durbin',
            phone_number='+6282312345678',
            employee_id='A&EX4NDER',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.request_data = {
            'assignment_name': 'Business Proposal Task 1',
            'description': 'This is the first assignment',
            'duration_in_minutes': 55,
            'expected_file_format': '.pdf'
        }

        self.expected_assignment = Assignment(
            name=self.request_data.get('assignment_name'),
            description=self.request_data.get('description'),
            owning_company=self.assessor.associated_company,
            expected_file_format='pdf',
            duration_in_minutes=self.request_data.get('duration_in_minutes')
        )

        self.expected_assignment_data = AssignmentSerializer(self.expected_assignment).data

    def test_sanitize_file_format_when_not_none(self):
        expected_file_format = 'pdf'
        sanitized_file_format = utils.sanitize_file_format('.pdf')
        self.assertEqual(sanitized_file_format, expected_file_format)

    def test_sanitize_file_format_when_none(self):
        sanitize_file_format = utils.sanitize_file_format(None)
        self.assertIsNone(sanitize_file_format)

    def test_get_assessor_or_raise_exception_when_assessor_exists(self):
        expected_assessor_data = AssessorSerializer(self.assessor).data
        assessor = assessment.get_assessor_or_raise_exception(self.assessor)
        assessor_data = AssessorSerializer(assessor).data
        self.assertDictEqual(assessor_data, expected_assessor_data)

    def test_get_assessor_or_raise_exception_when_assessor_does_not_exist(self):
        user = Assessee.objects.create_user(
            email='assessee@gmail.com',
            password='password',
            first_name='Assessee',
            last_name='Ajax',
            phone_number='+621234567192',
            date_of_birth=datetime.datetime.now(),
            authentication_service=AuthenticationService.GOOGLE.value
        )
        expected_message = f'User {user.email} is not an assessor'

        try:
            assessment.get_assessor_or_raise_exception(user)
            self.fail(EXCEPTION_NOT_RAISED)
        except RestrictedAccessException as exception:
            self.assertEqual(str(exception), expected_message)

    def test_validate_assessment_tool_when_request_is_valid(self):
        valid_request_data = self.request_data.copy()
        try:
            assessment.validate_assessment_tool(valid_request_data)
        except InvalidAssignmentRegistration as exception:
            self.fail(f'{exception} is raised')

    def test_validate_assessment_tool_when_request_data_has_no_name(self):
        invalid_request_data = self.request_data.copy()
        invalid_request_data['assignment_name'] = ''
        expected_message = 'Assessment name should not be empty'

        try:
            assessment.validate_assessment_tool(invalid_request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssignmentRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    def test_validate_assignment_when_request_is_valid(self):
        try:
            assessment.validate_assignment(self.request_data)
        except InvalidAssignmentRegistration as exception:
            self.fail(f'{exception} is raised')

    def test_validate_assignment_when_request_duration_is_invalid(self):
        request_data_with_no_duration = self.request_data.copy()
        request_data_with_no_duration['duration_in_minutes'] = ''
        expected_message = 'Assignment should have duration'
        try:
            assessment.validate_assignment(request_data_with_no_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssignmentRegistration as exception:
            self.assertEqual(str(exception), expected_message)

        request_data_with_non_numeric_duration = self.request_data.copy()
        request_data_with_non_numeric_duration['duration_in_minutes'] = '1a'
        expected_message = 'Assignment duration must only be of type numeric'
        try:
            assessment.validate_assignment(request_data_with_non_numeric_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssignmentRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(Assignment.objects, 'create')
    def test_save_assignment_to_database(self, mocked_create):
        mocked_create.return_value = self.expected_assignment
        returned_assignment = assessment.save_assignment_to_database(self.request_data, self.assessor)
        returned_assignment_data = AssignmentSerializer(returned_assignment).data
        mocked_create.assert_called_once()
        self.assertDictEqual(returned_assignment_data, self.expected_assignment_data)

    @patch.object(utils, 'sanitize_file_format')
    @patch.object(assessment, 'save_assignment_to_database')
    @patch.object(assessment, 'validate_assignment')
    @patch.object(assessment, 'validate_assessment_tool')
    @patch.object(assessment, 'get_assessor_or_raise_exception')
    def test_create_assignment(self, mocked_get_assessor, mocked_validate_assessment_tool,
                               mocked_validate_assignment, mocked_save_assignment, mocked_sanitize_file_format):
        mocked_get_assessor.return_value = self.assessor
        mocked_validate_assessment_tool.return_value = None
        mocked_validate_assignment.return_value = None
        mocked_save_assignment.return_value = self.expected_assignment
        mocked_sanitize_file_format.return_value = 'pdf'
        returned_assignment = assessment.create_assignment(self.request_data, self.assessor)
        returned_assignment_data = AssignmentSerializer(returned_assignment).data
        self.assertDictEqual(returned_assignment_data, self.expected_assignment_data)

    def test_create_assignment_when_complete_status_200(self):
        assignment_data = json.dumps(self.request_data.copy())
        client = APIClient()
        client.force_authenticate(user=self.assessor)

        response = client.post(CREATE_ASSIGNMENT_URL, data=assignment_data, content_type='application/json')
        self.assertEqual(response.status_code, OK_RESPONSE_STATUS_CODE)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertIsNotNone(response_content.get('assessment_id'))
        self.assertEqual(response_content.get('name'), self.expected_assignment_data.get('name'))
        self.assertEqual(response_content.get('description'), self.expected_assignment_data.get('description'))
        self.assertEqual(
            response_content.get('expected_file_format'), self.expected_assignment_data.get('expected_file_format')
        )
        self.assertEqual(
            response_content.get('duration_in_minutes'), self.expected_assignment_data.get('duration_in_minutes')
        )
        self.assertEqual(response_content.get('owning_company_id'), self.company.id)


class InteractiveQuizTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company@company.com',
            password='password',
            company_name='Company',
            description='Company Description',
            address='JL. Company Levinson Durbin Householder'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor@assessor.com',
            password='password',
            first_name='Levinson',
            last_name='Durbin',
            phone_number='+6282312345678',
            employee_id='A&EX4NDER',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.request_data = {
            'assignment_name': 'Data Cleaning Test',
            'description': 'This is a data cleaning test',
            'duration_in_minutes': 55,
            'total_points': 10,
            'questions': [
                {
                    'prompt': 'What is data cleaning?',
                    'points': 5,
                    'question_type': 'multiple_choice',
                    'answer_options': [
                        {
                            'content': 'Cleaning data',
                            'correct': True,
                        },
                        {
                            'content': 'Creating new features',
                            'correct': False,
                        },

                    ]
                },
                {
                    'prompt': 'Have you ever done data cleaning with Pandas?',
                    'points': 5,
                    'question_type': 'text',
                    'answer_key': 'Yes, I have',
                }
            ]
        }

        self.expected_interactive_quiz = InteractiveQuiz.objects.create(
            name=self.request_data.get('assignment_name'),
            description=self.request_data.get('description'),
            owning_company=self.assessor.associated_company,
            total_points=self.request_data.get('total_points'),
            duration_in_minutes=self.request_data.get('duration_in_minutes')
        )

        self.expected_interactive_quiz_data = InteractiveQuizSerializer(self.expected_interactive_quiz).data

        self.mc_question_data = self.request_data.get('questions')[0]

        self.expected_mc_question = MultipleChoiceQuestion(
            interactive_quiz=self.expected_interactive_quiz,
            prompt=self.mc_question_data.get('prompt'),
            points=self.mc_question_data.get('points'),
            question_type=self.mc_question_data.get('question_type')
        )

        self.correct_answer_option_data = self.mc_question_data.get('answer_options')[0]

        self.expected_correct_answer_option = MultipleChoiceAnswerOption(
            question=self.expected_mc_question,
            content=self.correct_answer_option_data.get('content'),
            correct=self.correct_answer_option_data.get('correct'),
        )

        self.incorrect_answer_option_data = self.mc_question_data.get('answer_options')[1]

        self.expected_incorrect_answer_option = MultipleChoiceAnswerOption(
            question=self.expected_mc_question,
            content=self.correct_answer_option_data.get('content'),
            correct=self.correct_answer_option_data.get('correct'),
        )

        self.text_question_data = self.request_data.get('questions')[1]

        self.expected_text_question = TextQuestion(
            interactive_quiz=self.expected_interactive_quiz,
            prompt=self.text_question_data.get('prompt'),
            points=self.text_question_data.get('points'),
            question_type=self.text_question_data.get('question_type'),
            answer_key=self.text_question_data.get('answer_key')
        )

    def test_validate_interactive_quiz_when_request_is_valid(self):
        valid_request_data = self.request_data.copy()
        try:
            self.assertEqual(type(valid_request_data), dict)
            assessment.validate_interactive_quiz(valid_request_data)
        except InvalidAssignmentRegistration as exception:
            self.fail(f'{exception} is raised')

    def test_interactive_quiz_when_request_duration_is_invalid(self):
        request_data_with_no_duration = self.request_data.copy()
        request_data_with_no_duration['duration_in_minutes'] = ''
        expected_message = 'Interactive Quiz should have a duration'
        try:
            assessment.validate_interactive_quiz(request_data_with_no_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidInteractiveQuizRegistration as exception:
            self.assertEqual(str(exception), expected_message)

        request_data_with_non_numeric_duration = self.request_data.copy()
        request_data_with_non_numeric_duration['duration_in_minutes'] = '1a'
        expected_message = 'Interactive Quiz duration must only be of type numeric'
        try:
            assessment.validate_interactive_quiz(request_data_with_non_numeric_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidInteractiveQuizRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    def test_interactive_quiz_when_request_total_points_is_invalid(self):
        request_data_with_no_duration = self.request_data.copy()
        request_data_with_no_duration['total_points'] = None
        expected_message = 'Interactive Quiz should have total points'
        try:
            assessment.validate_interactive_quiz(request_data_with_no_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidInteractiveQuizRegistration as exception:
            self.assertEqual(str(exception), expected_message)

        request_data_with_non_numeric_duration = self.request_data.copy()
        request_data_with_non_numeric_duration['total_points'] = '1a'
        expected_message = 'Interactive Quiz total points must only be of type numeric'
        try:
            assessment.validate_interactive_quiz(request_data_with_non_numeric_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidInteractiveQuizRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(InteractiveQuiz.objects, 'create')
    def test_save_interactive_quiz_to_database(self, mocked_create):
        mocked_create.return_value = self.expected_interactive_quiz
        returned_interactive_quiz = assessment.save_interactive_quiz_to_database(self.request_data, self.assessor)
        returned_interactive_quiz_data = InteractiveQuizSerializer(returned_interactive_quiz).data
        mocked_create.assert_called_once()
        self.assertDictEqual(returned_interactive_quiz_data, self.expected_interactive_quiz_data)

    @patch.object(MultipleChoiceAnswerOption.objects, 'create')
    @patch.object(MultipleChoiceAnswerOption.objects, 'create')
    @patch.object(MultipleChoiceQuestion.objects, 'create')
    def test_save_mc_question_to_database(self, mocked_create_mc_question, mocked_create_incorrect_answer_option,
                                          mocked_create_correct_answer_option):

        mocked_create_correct_answer_option.return_value = self.expected_correct_answer_option
        mocked_create_incorrect_answer_option.return_value = self.expected_incorrect_answer_option
        mocked_create_mc_question.return_value = self.expected_mc_question

        returned_mc_question = assessment.save_question_to_database(self.mc_question_data,
                                                                    self.expected_interactive_quiz)
        returned_mc_question_data = MultipleChoiceQuestionSerializer(returned_mc_question).data
        mocked_create_mc_question.assert_called_once()
        mocked_create_correct_answer_option.called_once()
        mocked_create_incorrect_answer_option.called_once()

        keys = ['prompt', 'points', 'question_type']
        self.expected_mc_question_data = {key: self.mc_question_data[key] for key in keys}
        self.assertDictEqual(returned_mc_question_data, self.expected_mc_question_data)

    @patch.object(TextQuestion.objects, 'create')
    def test_save_text_question_to_database(self, mocked_create_text_question):

        mocked_create_text_question.return_value = self.expected_text_question

        returned_question = assessment.save_question_to_database(self.text_question_data,
                                                                 self.expected_interactive_quiz)
        returned_question_data = TextQuestionSerializer(returned_question).data
        mocked_create_text_question.assert_called_once()
        self.assertDictEqual(returned_question_data, self.text_question_data)

    @patch.object(utils, 'get_interactive_quiz_total_points')
    @patch.object(assessment, 'save_answer_option_to_database')
    @patch.object(assessment, 'save_question_to_database')
    @patch.object(assessment, 'save_interactive_quiz_to_database')
    @patch.object(assessment, 'validate_answer_option')
    @patch.object(assessment, 'validate_question')
    @patch.object(assessment, 'validate_interactive_quiz')
    @patch.object(assessment, 'validate_assessment_tool')
    @patch.object(assessment, 'get_assessor_or_raise_exception')
    def test_create_interactive_quiz(self, mocked_get_assessor, mocked_validate_assessment_tool,
                                     mocked_validate_interactive_quiz, mocked_validate_question,
                                     mocked_validate_answer_option, mocked_save_interactive_quiz,
                                     mocked_save_questions, mocked_save_answer_options,
                                     mocked_get_interactive_quiz_total_points):
        mocked_get_assessor.return_value = self.assessor

        mocked_validate_assessment_tool.return_value = None
        mocked_validate_interactive_quiz.return_value = None
        mocked_validate_question.return_value = None
        mocked_validate_answer_option.return_value = None

        mocked_save_interactive_quiz.return_value = self.expected_interactive_quiz
        mocked_save_questions.return_value = None
        mocked_save_answer_options.return_value = None

        mocked_get_interactive_quiz_total_points.return_value = 10

        returned_interactive_quiz = assessment.create_interactive_quiz(self.request_data, self.assessor)
        returned_interactive_quiz_data = InteractiveQuizSerializer(returned_interactive_quiz).data
        self.assertDictEqual(returned_interactive_quiz_data, self.expected_interactive_quiz_data)

    def test_create_interactive_quiz_when_complete_status_200(self):
        interactive_quiz_data = json.dumps(self.request_data.copy())
        client = APIClient()
        client.force_authenticate(user=self.assessor)

        response = client.post(CREATE_INTERACTIVE_QUIZ_URL, data=interactive_quiz_data, content_type='application/json')
        self.assertEqual(response.status_code, OK_RESPONSE_STATUS_CODE)

        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertIsNotNone(response_content.get('assessment_id'))
        self.assertEqual(response_content.get('name'), self.expected_interactive_quiz_data.get('name'))
        self.assertEqual(response_content.get('description'), self.expected_interactive_quiz_data.get('description'))
        self.assertEqual(
            response_content.get('total_points'), self.expected_interactive_quiz_data.get('total_points')
        )
        self.assertEqual(
            response_content.get('duration_in_minutes'), self.expected_interactive_quiz_data.get('duration_in_minutes')
        )
        self.assertEqual(response_content.get('owning_company_id'), self.company.id)
        self.assertEqual(response_content.get('owning_company_name'), self.company.company_name)
