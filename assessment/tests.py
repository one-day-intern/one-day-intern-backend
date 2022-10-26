from django.test import TestCase
from django.urls import reverse
from http import HTTPStatus
from one_day_intern.exceptions import RestrictedAccessException, InvalidAssignmentRegistration, InvalidRequestException, \
    InvalidInteractiveQuizRegistration
from rest_framework.test import APIClient
from unittest.mock import patch, call
from users.models import (
    Company,
    Assessor,
    Assessee,
    AuthenticationService,
    AssessorSerializer
)
from .models import InteractiveQuizSerializer, InteractiveQuiz, \
    MultipleChoiceQuestion, MultipleChoiceAnswerOption, TextQuestion, TextQuestionSerializer, \
    MultipleChoiceQuestionSerializer


from .exceptions.exceptions import AssessmentToolDoesNotExist
from .models import Assignment, AssignmentSerializer, TestFlow, TestFlowTool
from .services import assessment, utils, test_flow
import datetime
import json
import uuid

EXCEPTION_NOT_RAISED = 'Exception not raised'
TEST_FLOW_INVALID_NAME = 'Test Flow name must exist and must be at most 50 characters'
CREATE_ASSIGNMENT_URL = '/assessment/create/assignment/'
CREATE_INTERACTIVE_QUIZ_URL = '/assessment/create/interactive-quiz/'
CREATE_TEST_FLOW_URL = reverse('test-flow-create')
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
            'name': 'Business Proposal Task 1',
            'description': 'This is the first assignment',
            'duration_in_minutes': 55,
            'expected_file_format': '.pdf'
        }

        self.expected_assignment = Assignment(
            name=self.request_data.get('name'),
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
        invalid_request_data['name'] = ''
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
            'name': 'Data Cleaning Test',
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
            name=self.request_data.get('name'),
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


def fetch_create_test_flow(request_data, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    test_flow_data = json.dumps(request_data)
    response = client.post(CREATE_TEST_FLOW_URL, data=test_flow_data, content_type='application/json')
    return response


class TestFlowTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='companytestflow@company.com',
            password='password',
            company_name='Company',
            description='Company Description',
            address='JL. Company Levinson Durbin Householder'
        )

        self.assessment_tool_1 = Assignment.objects.create(
            name='Assignment 1',
            description='An Assignment number 1',
            owning_company=self.company,
            expected_file_format='docx',
            duration_in_minutes=50
        )

        self.assessment_tool_2 = Assignment.objects.create(
            name='Assignment 2',
            description='An Assignment number 2',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=100
        )

        self.base_request_data = {
            'name': 'TestFlow 1',
            'tools_used': [
                {
                    'tool_id': str(self.assessment_tool_1.assessment_id),
                    'release_time': '1899-12-30T09:00:00.000Z'
                },
                {
                    'tool_id': str(self.assessment_tool_2.assessment_id),
                    'release_time': '1899-12-30T13:00:00.000Z'
                },
            ]
        }

        self.converted_tools = [
            {
                'tool': self.assessment_tool_1,
                'release_time': datetime.time(13, 0)
            },
            {
                'tool': self.assessment_tool_2,
                'release_time': datetime.time(9, 0)
            }
        ]

    def test_get_tool_from_id_when_tool_exist(self):
        tool_id = str(self.assessment_tool_1.assessment_id)
        retrieved_assessment_tool = utils.get_tool_from_id(tool_id)
        self.assertEqual(str(retrieved_assessment_tool.assessment_id), tool_id)
        self.assertEqual(retrieved_assessment_tool.name, self.assessment_tool_1.name)
        self.assertEqual(retrieved_assessment_tool.description, self.assessment_tool_1.description)
        self.assertEqual(retrieved_assessment_tool.expected_file_format, self.assessment_tool_1.expected_file_format)
        self.assertEqual(retrieved_assessment_tool.duration_in_minutes, self.assessment_tool_1.duration_in_minutes)

    def test_get_tool_from_id_when_tool_does_not_exist(self):
        tool_id = str(uuid.uuid4())
        expected_message = f'Assessment tool with id {tool_id} does not exist'
        try:
            utils.get_tool_from_id(tool_id)
            self.fail(EXCEPTION_NOT_RAISED)
        except AssessmentToolDoesNotExist as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_time_from_date_time_string_when_string_is_invalid_iso_date_time(self):
        invalid_iso_date = '2022-1025T01:20:00.000Z'
        expected_message = f'2022-1025T01:20:00.000 is not a valid ISO date string'
        try:
            utils.get_time_from_date_time_string(invalid_iso_date)
            self.fail(EXCEPTION_NOT_RAISED)
        except ValueError as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_time_from_date_time_string_when_string_is_valid_iso_date_time(self):
        valid_iso_date = '2022-10-25T01:20:00.000Z'
        time_: datetime.time = utils.get_time_from_date_time_string(valid_iso_date)
        self.assertEqual(time_.hour, 1)
        self.assertEqual(time_.minute, 20)

    @patch.object(TestFlowTool.objects, 'create')
    def test_add_tool_to_test_flow(self, mock_test_flow_tools_create):
        release_time = datetime.time(10, 30)
        test_flow_ = TestFlow.objects.create(
            name=self.base_request_data['name'],
            owning_company=self.company,
            is_usable=False
        )

        test_flow_.add_tool(self.assessment_tool_1, release_time=release_time)
        self.assertTrue(test_flow_.get_is_usable())
        mock_test_flow_tools_create.assert_called_with(
            assessment_tool=self.assessment_tool_1,
            test_flow=test_flow_,
            release_time=release_time
        )

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_name_does_not_exist(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        del request_data['name']

        try:
            test_flow.validate_test_flow_registration(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), TEST_FLOW_INVALID_NAME)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_name_exceeds_50_character(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['name'] = 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz'

        try:
            test_flow.validate_test_flow_registration(request_data)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), TEST_FLOW_INVALID_NAME)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_does_not_contain_tool_used(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []

        try:
            test_flow.validate_test_flow_registration(request_data)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_contain_tool_used(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()

        try:
            test_flow.validate_test_flow_registration(request_data)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_tool_does_not_exist(self, mocked_get_tool, mocked_get_time):
        invalid_tool_id = str(uuid.uuid4())
        expected_error_message = f'Assessment tool with id {invalid_tool_id} does not exist'
        mocked_get_time.return_value = None
        mocked_get_tool.side_effect = AssessmentToolDoesNotExist(expected_error_message)
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [{
            'tool_id': invalid_tool_id,
            'release_time': '2022-10-25T01:20:00.000Z'
        }]

        try:
            test_flow.validate_test_flow_registration(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_datetime_is_invalid(self, mocked_get_tool, mocked_get_time):
        invalid_datetime_string = '2020-Monday-OctoberT01:01:01'
        expected_error_message = f'{invalid_datetime_string} is not a valid ISO date string'
        mocked_get_tool.return_value = None
        mocked_get_time.side_effect = ValueError(expected_error_message)

        request_data = self.base_request_data.copy()
        request_data['tool_id'] = [{
            'tool_id': str(self.assessment_tool_1.assessment_id),
            'release_time': invalid_datetime_string
        }]

        try:
            test_flow.validate_test_flow_registration(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), f'{invalid_datetime_string} is not a valid ISO date string')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_validate_test_flow_when_tool_used_is_not_a_list(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = 'list'
        try:
            test_flow.validate_test_flow_registration(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), 'Test Flow must be of type list')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_convert_assessment_tool_id_to_assessment_tool_when_request_does_not_contain_tool(self, mocked_get_tool,
                                                                                              mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        del request_data['tools_used']
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data)
        self.assertEqual(converted_tool, [])

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_convert_assessment_tool_id_to_assessment_tool_when_tools_used_is_empty(self, mocked_get_tool,
                                                                                    mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data)
        self.assertEqual(converted_tool, [])

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_from_id')
    def test_convert_assessment_tool_id_assessment_tool_when_tools_used_not_empty(self, mocked_get_tool,
                                                                                  mocked_get_time):
        number_of_assessment_tools = 2
        expected_release_time = datetime.time(13, 00)
        mocked_get_tool.return_value = self.assessment_tool_1
        mocked_get_time.return_value = expected_release_time
        request_data = self.base_request_data.copy()
        converted_tools = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data)

        self.assertEqual(len(converted_tools), number_of_assessment_tools)
        tool_data_assessment_1 = converted_tools[1]
        self.assertIsNotNone(tool_data_assessment_1.get('tool'))
        self.assertIsNotNone(tool_data_assessment_1.get('release_time'))

        tool = tool_data_assessment_1['tool']
        release_time = tool_data_assessment_1['release_time']
        self.assertEqual(tool.assessment_id, self.assessment_tool_1.assessment_id)
        self.assertEqual(release_time, expected_release_time)

    @patch.object(TestFlow, 'save')
    @patch.object(TestFlow, 'add_tool')
    def test_save_test_flow_to_database_when_converted_tools_is_empty(self, mocked_add_tool, mocked_save):
        converted_tools = []
        request_data = self.base_request_data.copy()
        saved_test_flow = test_flow.save_test_flow_to_database(request_data, converted_tools, self.company)
        mocked_save.assert_called_once()
        mocked_add_tool.assert_not_called()
        self.assertIsNotNone(saved_test_flow.test_flow_id)
        self.assertEqual(saved_test_flow.name, request_data.get('name'))
        self.assertEqual(saved_test_flow.owning_company, self.company)

    @patch.object(TestFlow, 'save')
    @patch.object(TestFlow, 'add_tool')
    def test_save_test_flow_to_database_when_converted_tools_is_not_empty(self, mocked_add_tool, mocked_save):
        request_data = self.base_request_data.copy()
        converted_tools = self.converted_tools.copy()
        converted_tool_1 = converted_tools[0]
        converted_tool_2 = converted_tools[1]
        expected_calls = [
            call(assessment_tool=converted_tool_1['tool'], release_time=converted_tool_1['release_time']),
            call(assessment_tool=converted_tool_2['tool'], release_time=converted_tool_2['release_time'])
        ]

        saved_test_flow = test_flow.save_test_flow_to_database(request_data, converted_tools, self.company)
        mocked_save.assert_called_once()
        mocked_add_tool.assert_has_calls(expected_calls)
        self.assertIsNotNone(saved_test_flow.test_flow_id)
        self.assertEqual(saved_test_flow.name, request_data.get('name'))
        self.assertEqual(saved_test_flow.owning_company, self.company)

    def flow_assert_response_correctness_when_request_is_valid(self, response, request_data,
                                                               expected_number_of_tools, expected_usable, company):
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('test_flow_id'))
        self.assertEqual(response_content.get('name'), request_data.get('name'))
        self.assertEqual(response_content.get('owning_company_id'), str(company.company_id))
        self.assertEqual(response_content.get('is_usable'), expected_usable)
        self.assertEqual(len(response_content.get('tools')), expected_number_of_tools)

    def flow_assert_response_correctness_when_request_is_invalid(self, response, expected_status_code,
                                                                 expected_message):
        self.assertEqual(response.status_code, expected_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), expected_message)

    def test_create_test_flow_when_tools_used_is_empty_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []

        response = fetch_create_test_flow(request_data=request_data, authenticated_user=self.company)
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=0,
            expected_usable=False,
            company=self.company
        )

    def test_create_test_flow_when_no_tools_used_field_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        del request_data['tools_used']
        response = fetch_create_test_flow(request_data=request_data, authenticated_user=self.company)
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=0,
            expected_usable=False,
            company=self.company
        )

    def test_create_test_flow_when_tool_id_used_does_not_exist_and_user_is_company(self):
        non_exist_tool_id = str(uuid.uuid4())
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [
            {
                'tool_id': non_exist_tool_id,
                'release_time': '1998-01-01T01:01:00Z'
            }
        ]
        response = fetch_create_test_flow(request_data=request_data, authenticated_user=self.company)
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=f'Assessment tool with id {non_exist_tool_id} does not exist'
        )

    def test_create_test_flow_when_tool_release_time_is_invalid_and_user_is_company(self):
        invalid_iso_datetime = '2022-10-2501:20:00.000'
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [
            {
                'tool_id': str(self.assessment_tool_1.assessment_id),
                'release_time': invalid_iso_datetime
            }
        ]

        response = fetch_create_test_flow(request_data=request_data, authenticated_user=self.company)
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=f'{invalid_iso_datetime} is not a valid ISO date string'
        )

    def assert_tool_data_correctness(self, tool_flow_data, assessment_tool: Assignment):
        self.assertIsNotNone(tool_flow_data.get('assessment_tool'))
        assessment_tool_data = tool_flow_data.get('assessment_tool')
        self.assertEqual(assessment_tool_data.get('name'), assessment_tool.name)
        self.assertEqual(assessment_tool_data.get('description'), assessment_tool.description)
        self.assertEqual(assessment_tool_data.get('owning_company_id'), str(assessment_tool.owning_company.company_id))

    def test_create_test_flow_when_request_is_valid_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        response = fetch_create_test_flow(request_data=request_data, authenticated_user=self.company)
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=2,
            expected_usable=True,
            company=self.company
        )

        response_content = json.loads(response.content)
        tools = response_content.get('tools')

        test_flow_tool_1 = tools[0]
        self.assert_tool_data_correctness(test_flow_tool_1, self.assessment_tool_1)

        test_flow_tool_2 = tools[1]
        self.assert_tool_data_correctness(test_flow_tool_2, self.assessment_tool_2)
