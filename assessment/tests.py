from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from freezegun import freeze_time
from google.cloud import storage
from http import HTTPStatus
from assessment.services.assessment_tool import get_assessment_tool_by_company, get_test_flow_by_company
from one_day_intern.exceptions import (
    RestrictedAccessException,
    InvalidAssignmentRegistration,
    InvalidInteractiveQuizRegistration,
    InvalidRequestException,
    InvalidResponseTestRegistration
)
from one_day_intern.settings import GOOGLE_BUCKET_BASE_DIRECTORY, GOOGLE_STORAGE_BUCKET_NAME
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, call
from users.models import (
    Company,
    Assessor,
    Assessee,
    AuthenticationService,
    AssessorSerializer
)
from .exceptions.exceptions import (
    AssessmentToolDoesNotExist,
    InvalidTestFlowRegistration,
    InvalidAssessmentEventRegistration
)
from .models import (
    AssessmentTool,
    Assignment,
    AssignmentSerializer,
    ResponseTest,
    ResponseTestSerializer,
    TestFlow,
    TestFlowTool,
    AssessmentEvent,
    TestFlowAttempt,
    AssessmentEventParticipation,
    MultipleChoiceAnswerOption,
    TextQuestion,
    MultipleChoiceQuestion,
    InteractiveQuizSerializer,
    InteractiveQuiz, MultipleChoiceQuestionSerializer, TextQuestionSerializer,
    VideoConferenceRoom,
    AssignmentAttempt, AssessmentEventSerializer
)
from .services import (
    assessment, utils, test_flow,
    assessment_event, assessment_event_attempt, TaskGenerator,
    google_storage
)
import datetime
import json
import schedule
import pytz
import uuid

ASSESSMENT_EVENT_ID_PARAM_NAME = '?assessment-event-id='

EXCEPTION_NOT_RAISED = 'Exception not raised'
TEST_FLOW_INVALID_NAME = 'Test Flow name must exist and must be at most 50 characters'
TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT = 'Assessment tool with id {} belonging to company {} does not exist'
ASSESSMENT_EVENT_INVALID_NAME = 'Assessment Event name must be minimum of length 3 and at most 50 characters'
ACTIVE_TEST_FLOW_NOT_FOUND = 'Active test flow of id {} belonging to {} does not exist'
INVALID_DATE_FORMAT = '{} is not a valid ISO date string'
ASSESSMENT_EVENT_OWNERSHIP_INVALID = 'Event with id {} does not belong to company with id {}'
NOT_PART_OF_EVENT = 'Assessee with email {} is not part of assessment with id {}'
ASSESSOR_NOT_PART_OF_EVENT = 'Assessor with email {} is not part of assessment with id {}'
EVENT_DOES_NOT_EXIST = 'Assessment Event with ID {} does not exist'
EVENT_IS_NOT_ACTIVE = 'Assessment Event with ID {} is not active'
TOOL_OF_EVENT_NOT_FOUND = 'Tool with id {} associated with event with id {} is not found'
TOOL_IS_NOT_ASSIGNMENT = 'Assessment tool with id {} is not an assignment'
FILENAME_DOES_NOT_MATCH_FORMAT = 'File type does not match expected format (expected {})'
IMPROPER_FILE_NAME = '{} is not a proper file name'
USER_IS_NOT_ASSESSEE = 'User with email {} is not an assessee'
CREATE_ASSIGNMENT_URL = '/assessment/create/assignment/'
CREATE_INTERACTIVE_QUIZ_URL = '/assessment/create/interactive-quiz/'
CANNOT_SUBMIT_AT_THIS_TIME = 'Assessment is not accepting submissions at this time'

CREATE_TEST_FLOW_URL = reverse('test-flow-create')
CREATE_ASSESSMENT_EVENT_URL = reverse('assessment-event-create')
ADD_PARTICIPANT_URL = reverse('event-add-participation')
EVENT_SUBSCRIPTION_URL = reverse('event-subscription')
SUBMIT_ASSIGNMENT_URL = reverse('submit-assignments')
GET_RELEASED_ASSIGNMENTS = reverse('event-active-assignments') + ASSESSMENT_EVENT_ID_PARAM_NAME
GET_EVENT_DATA = reverse('get-event-data') + ASSESSMENT_EVENT_ID_PARAM_NAME
GET_AND_DOWNLOAD_ATTEMPT_URL = reverse('get-submitted-assignment')
CREATE_RESPONSE_TEST_URL = '/assessment/create/response-test/'

GET_TOOLS_URL = "/assessment/tools/"
REQUEST_CONTENT_TYPE = 'application/json'
APPLICATION_PDF = 'application/pdf'
OK_RESPONSE_STATUS_CODE = 200


class AssessmentTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company63@company.com',
            password='password',
            company_name='Company',
            description='Company Description 66',
            address='JL. Company Levinson Durbin Householder 67'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor@assessor.com',
            password='password',
            first_name='Levinson',
            last_name='Durbin',
            phone_number='+6282312345111',
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

        self.expected_assignment_data = AssignmentSerializer(
            self.expected_assignment).data

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
            assessment.validate_assignment(
                request_data_with_non_numeric_duration)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssignmentRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(Assignment.objects, 'create')
    def test_save_assignment_to_database(self, mocked_create):
        mocked_create.return_value = self.expected_assignment
        returned_assignment = assessment.save_assignment_to_database(
            self.request_data, self.assessor)
        returned_assignment_data = AssignmentSerializer(
            returned_assignment).data
        mocked_create.assert_called_once()
        self.assertDictEqual(returned_assignment_data,
                             self.expected_assignment_data)

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
        returned_assignment = assessment.create_assignment(
            self.request_data, self.assessor)
        returned_assignment_data = AssignmentSerializer(
            returned_assignment).data
        self.assertDictEqual(returned_assignment_data,
                             self.expected_assignment_data)

    def test_create_assignment_when_complete_status_200(self):
        assignment_data = self.request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_ASSIGNMENT_URL,
            request_data=assignment_data,
            authenticated_user=self.assessor
        )

        self.assertEqual(response.status_code, OK_RESPONSE_STATUS_CODE)
        response_content = json.loads(response.content)
        self.assertTrue(len(response_content) > 0)
        self.assertIsNotNone(response_content.get('assessment_id'))
        self.assertEqual(response_content.get('name'),
                         self.expected_assignment_data.get('name'))
        self.assertEqual(response_content.get('description'),
                         self.expected_assignment_data.get('description'))
        self.assertEqual(
            response_content.get('expected_file_format'), self.expected_assignment_data.get(
                'expected_file_format')
        )
        self.assertEqual(
            response_content.get('duration_in_minutes'), self.expected_assignment_data.get(
                'duration_in_minutes')
        )
        self.assertEqual(response_content.get('owning_company_id'), self.company.id)
        self.assertEqual(response_content.get('owning_company_name'), self.company.company_name)


class InteractiveQuizTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company213@company.com',
            password='password213',
            company_name='Company213',
            description='Company213 Description',
            address='JL. Company213 Levinson Durbin Householder'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor213@assessor.com',
            password='password213',
            first_name='Levinson213',
            last_name='Durbin213',
            phone_number='+6282312345213',
            employee_id='A&EX4ND3R',
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
                                     mocked_save_questions, mocked_get_interactive_quiz_total_points):
        mocked_get_assessor.return_value = self.assessor

        mocked_validate_assessment_tool.return_value = None
        mocked_validate_interactive_quiz.return_value = None
        mocked_validate_question.return_value = None
        mocked_validate_answer_option.return_value = None

        mocked_save_interactive_quiz.return_value = self.expected_interactive_quiz
        mocked_save_questions.return_value = None

        mocked_get_interactive_quiz_total_points.return_value = 10

        returned_interactive_quiz = assessment.create_interactive_quiz(self.request_data, self.assessor)
        returned_interactive_quiz_data = InteractiveQuizSerializer(returned_interactive_quiz).data
        self.assertDictEqual(returned_interactive_quiz_data, self.expected_interactive_quiz_data)

    def test_create_interactive_quiz_when_complete_status_200(self):
        interactive_quiz_data = json.dumps(self.request_data.copy())
        client = APIClient()
        client.force_authenticate(user=self.assessor)

        response = client.post(CREATE_INTERACTIVE_QUIZ_URL, data=interactive_quiz_data,
                               content_type=REQUEST_CONTENT_TYPE)
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


def fetch_and_get_response(path, request_data, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    request_data_json = json.dumps(request_data)
    response = client.post(path, data=request_data_json, content_type=REQUEST_CONTENT_TYPE)
    return response


class TestFlowTest(TestCase):
    def setUp(self) -> None:
        self.company_1 = Company.objects.create_user(
            email='companytestflow@company.com',
            password='password',
            company_name='Company',
            description='Company Description 518',
            address='JL. Company Levinson Durbin Householder 2'
        )

        self.assessment_tool_1 = Assignment.objects.create(
            name='Assignment 1',
            description='An Assignment number 1',
            owning_company=self.company_1,
            expected_file_format='docx',
            duration_in_minutes=50
        )

        self.assessment_tool_2 = Assignment.objects.create(
            name='Assignment 2',
            description='An Assignment number 2',
            owning_company=self.company_1,
            expected_file_format='pdf',
            duration_in_minutes=100
        )

        self.base_request_data = {
            'name': 'TestFlow 1',
            'tools_used': [
                {
                    'tool_id': str(self.assessment_tool_1.assessment_id),
                    'release_time': '1899-12-30T09:00:00.000Z',
                    'start_working_time': '1899-12-30T10:00:00.000Z'
                },
                {
                    'tool_id': str(self.assessment_tool_2.assessment_id),
                    'release_time': '1899-12-30T13:00:00.000Z',
                    'start_working_time': '1899-12-30T14:00:00.000Z'
                },
            ]
        }

        self.converted_tools = [
            {
                'tool': self.assessment_tool_1,
                'release_time': datetime.time(9, 0),
                'start_working_time': datetime.time(10, 0),
            },
            {
                'tool': self.assessment_tool_2,
                'release_time': datetime.time(13, 0),
                'start_working_time': datetime.time(14, 0)
            }
        ]

        self.company_2 = Company.objects.create_user(
            email='companytestflow2@company.com',
            password='Password12',
            company_name='Company',
            description='Company Description 2',
            address='JL. Company Levinson Hermitian Householder'
        )

        self.assessment_tool_3 = Assignment.objects.create(
            name='Assignment 3',
            description='An Assignment number 3',
            owning_company=self.company_2,
            expected_file_format='txt',
            duration_in_minutes=100
        )

    def test_get_tool_of_company_from_id_when_tool_exists_and_belong_to_company(self):
        tool_id = str(self.assessment_tool_1.assessment_id)
        retrieved_assessment_tool = utils.get_tool_of_company_from_id(
            tool_id, self.company_1)
        self.assertEqual(str(retrieved_assessment_tool.assessment_id), tool_id)
        self.assertEqual(retrieved_assessment_tool.name,
                         self.assessment_tool_1.name)
        self.assertEqual(retrieved_assessment_tool.description,
                         self.assessment_tool_1.description)
        self.assertEqual(retrieved_assessment_tool.expected_file_format,
                         self.assessment_tool_1.expected_file_format)
        self.assertEqual(retrieved_assessment_tool.duration_in_minutes,
                         self.assessment_tool_1.duration_in_minutes)

    def test_et_tool_of_company_from_id_when_tool_does_not_exist(self):
        tool_id = str(uuid.uuid4())
        expected_message = TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(
            tool_id, self.company_1.company_name)

        try:
            utils.get_tool_of_company_from_id(tool_id, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except AssessmentToolDoesNotExist as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_tool_from_id_when_tool_exists_but_does_not_belong_to_company(self):
        tool_id = str(self.assessment_tool_3.assessment_id)
        expected_message = TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(
            tool_id, self.company_1.company_name)

        try:
            utils.get_tool_of_company_from_id(tool_id, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except AssessmentToolDoesNotExist as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_time_from_date_time_string_when_string_is_None(self):
        invalid_iso_date = None
        expected_message = 'None is not a valid ISO date string'
        try:
            utils.get_time_from_date_time_string(invalid_iso_date)
            self.fail(EXCEPTION_NOT_RAISED)
        except ValueError as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_time_from_date_time_string_when_string_is_invalid_iso_date_time(self):
        invalid_iso_date = '2022-1025T01:20:00.000Z'
        expected_message = '2022-1025T01:20:00.000 is not a valid ISO date string'
        try:
            utils.get_time_from_date_time_string(invalid_iso_date)
            self.fail(EXCEPTION_NOT_RAISED)
        except ValueError as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_time_from_date_time_string_when_string_is_valid_iso_date_time(self):
        valid_iso_date = '2022-10-25T01:20:00.000Z'
        time_: datetime.time = utils.get_time_from_date_time_string(
            valid_iso_date)
        self.assertEqual(time_.hour, 1)
        self.assertEqual(time_.minute, 20)

    @patch.object(TestFlowTool.objects, 'create')
    def test_add_tool_to_test_flow(self, mock_test_flow_tools_create):
        release_time = datetime.time(10, 30)
        start_working_time = datetime.time(11, 45)
        test_flow_ = TestFlow.objects.create(
            name=self.base_request_data['name'],
            owning_company=self.company_1,
            is_usable=False
        )

        test_flow_.add_tool(self.assessment_tool_1, release_time=release_time,
                            start_working_time=start_working_time)
        self.assertTrue(test_flow_.get_is_usable())
        mock_test_flow_tools_create.assert_called_with(
            assessment_tool=self.assessment_tool_1,
            test_flow=test_flow_,
            release_time=release_time,
            start_working_time=start_working_time
        )

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_name_does_not_exist(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        del request_data['name']

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidTestFlowRegistration as exception:
            self.assertEqual(str(exception), TEST_FLOW_INVALID_NAME)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_name_exceeds_50_character(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['name'] = 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz'

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
        except InvalidTestFlowRegistration as exception:
            self.assertEqual(str(exception), TEST_FLOW_INVALID_NAME)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_does_not_contain_tool_used(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_contain_tool_used(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_tool_does_not_exist(self, mocked_get_tool, mocked_get_time):
        invalid_tool_id = str(uuid.uuid4())
        expected_error_message = f'Assessment tool with id {invalid_tool_id} does not exist'
        mocked_get_time.return_value = None
        mocked_get_tool.side_effect = AssessmentToolDoesNotExist(
            expected_error_message)
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [{
            'tool_id': invalid_tool_id,
            'release_time': '2022-10-25T01:20:00.000Z',
            'start_working_time': '2022-10-25T04:20:00.000Z'
        }]

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidTestFlowRegistration as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_datetime_is_invalid(self, mocked_get_tool, mocked_get_time):
        invalid_datetime_string = '2020-Monday-OctoberT01:01:01'
        expected_error_message = f'{invalid_datetime_string} is not a valid ISO date string'
        mocked_get_tool.return_value = None
        mocked_get_tool.side_effect = ValueError(expected_error_message)

        request_data = self.base_request_data.copy()
        request_data['tool_id'] = [{
            'tool_id': str(self.assessment_tool_1.assessment_id),
            'release_time': invalid_datetime_string,
            'start_working_time': '2022-10-25T04:20:00.000Z'
        }]

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidTestFlowRegistration as exception:
            self.assertEqual(str(exception), expected_error_message)

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_tool_used_is_not_a_list(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = 'list'

        try:
            test_flow.validate_test_flow_registration(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidTestFlowRegistration as exception:
            self.assertEqual(str(exception), 'Test Flow must be of type list')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_convert_assessment_tool_id_to_assessment_tool_when_request_does_not_contain_tool(self, mocked_get_tool,
                                                                                              mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        del request_data['tools_used']
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(
            request_data, self.company_1)
        self.assertEqual(converted_tool, [])

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_convert_assessment_tool_id_to_assessment_tool_when_tools_used_is_empty(self, mocked_get_tool,
                                                                                    mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(
            request_data, self.company_1)
        self.assertEqual(converted_tool, [])

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_convert_assessment_tool_id_assessment_tool_when_tools_used_not_empty(self, mocked_get_tool,
                                                                                  mocked_get_time):
        number_of_assessment_tools = 2
        expected_returned_time = datetime.time(13, 00)
        mocked_get_tool.return_value = self.assessment_tool_1
        mocked_get_time.return_value = expected_returned_time
        request_data = self.base_request_data.copy()
        converted_tools = test_flow.convert_assessment_tool_id_to_assessment_tool(
            request_data, self.company_1)

        self.assertEqual(len(converted_tools), number_of_assessment_tools)
        tool_data_assessment_1 = converted_tools[1]
        self.assertIsNotNone(tool_data_assessment_1.get('tool'))
        self.assertIsNotNone(tool_data_assessment_1.get('release_time'))
        self.assertIsNotNone(tool_data_assessment_1.get('start_working_time'))

        tool = tool_data_assessment_1['tool']
        release_time = tool_data_assessment_1['release_time']
        start_working_time = tool_data_assessment_1['start_working_time']
        self.assertEqual(tool.assessment_id,
                         self.assessment_tool_1.assessment_id)
        self.assertEqual(release_time, expected_returned_time)
        self.assertEqual(start_working_time, expected_returned_time)

    @patch.object(TestFlow, 'save')
    @patch.object(TestFlow, 'add_tool')
    def test_save_test_flow_to_database_when_converted_tools_is_empty(self, mocked_add_tool, mocked_save):
        converted_tools = []
        request_data = self.base_request_data.copy()
        saved_test_flow = test_flow.save_test_flow_to_database(
            request_data, converted_tools, self.company_1)
        mocked_save.assert_called_once()
        mocked_add_tool.assert_not_called()
        self.assertIsNotNone(saved_test_flow.test_flow_id)
        self.assertEqual(saved_test_flow.name, request_data.get('name'))
        self.assertEqual(saved_test_flow.owning_company, self.company_1)

    @patch.object(TestFlow, 'save')
    @patch.object(TestFlow, 'add_tool')
    def test_save_test_flow_to_database_when_converted_tools_is_not_empty(self, mocked_add_tool, mocked_save):
        request_data = self.base_request_data.copy()
        converted_tools = self.converted_tools.copy()
        converted_tool_1 = converted_tools[0]
        converted_tool_2 = converted_tools[1]
        expected_calls = [
            call(
                assessment_tool=converted_tool_1['tool'],
                release_time=converted_tool_1['release_time'],
                start_working_time=converted_tool_1['start_working_time']
            ),
            call(
                assessment_tool=converted_tool_2['tool'],
                release_time=converted_tool_2['release_time'],
                start_working_time=converted_tool_2['start_working_time']
            ),
        ]

        saved_test_flow = test_flow.save_test_flow_to_database(
            request_data, converted_tools, self.company_1)
        mocked_save.assert_called_once()
        mocked_add_tool.assert_has_calls(expected_calls)
        self.assertIsNotNone(saved_test_flow.test_flow_id)
        self.assertEqual(saved_test_flow.name, request_data.get('name'))
        self.assertEqual(saved_test_flow.owning_company, self.company_1)

    def flow_assert_response_correctness_when_request_is_valid(self, response, request_data,
                                                               expected_number_of_tools, expected_usable, company):
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('test_flow_id'))
        self.assertEqual(response_content.get(
            'name'), request_data.get('name'))
        self.assertEqual(response_content.get(
            'owning_company_id'), str(company.company_id))
        self.assertEqual(response_content.get('is_usable'), expected_usable)
        self.assertEqual(len(response_content.get('tools')),
                         expected_number_of_tools)

    def flow_assert_response_correctness_when_request_is_invalid(self, response, expected_status_code,
                                                                 expected_message):
        self.assertEqual(response.status_code, expected_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), expected_message)

    def test_create_test_flow_when_tools_used_is_empty_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []

        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=0,
            expected_usable=False,
            company=self.company_1
        )

    def test_create_test_flow_when_no_tools_used_field_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        del request_data['tools_used']
        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=0,
            expected_usable=False,
            company=self.company_1
        )

    def test_create_test_flow_when_tool_id_used_does_not_exist_and_user_is_company(self):
        non_exist_tool_id = str(uuid.uuid4())
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [
            {
                'tool_id': non_exist_tool_id,
                'release_time': '1998-01-01T01:01:00Z',
                'start_working_time': '1998-01-01T01:01:00Z'
            }
        ]

        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(
                non_exist_tool_id, self.company_1.company_name)
        )

    def test_create_test_flow_when_tool_release_time_is_invalid_and_user_is_company(self):
        invalid_iso_datetime = '2022-10-2501:20:00.000'
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [
            {
                'tool_id': str(self.assessment_tool_1.assessment_id),
                'release_time': invalid_iso_datetime,
                'start_working_time': '1998-01-01T01:10:00Z'
            }
        ]

        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=f'{invalid_iso_datetime} is not a valid ISO date string'
        )

    def test_create_test_flow_when_tool_start_working_time_is_invalid_and_user_is_company(self):
        invalid_iso_datetime = '20211-02-01033:03T'
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [
            {
                'tool_id': str(self.assessment_tool_1.assessment_id),
                'release_time': '1998-01-01T01:10:00Z',
                'start_working_time': invalid_iso_datetime
            }
        ]

        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=f'{invalid_iso_datetime} is not a valid ISO date string'
        )

    def assert_tool_data_correctness(self, tool_flow_data, assessment_tool: Assignment):
        self.assertIsNotNone(tool_flow_data.get('assessment_tool'))
        assessment_tool_data = tool_flow_data.get('assessment_tool')
        self.assertEqual(assessment_tool_data.get(
            'name'), assessment_tool.name)
        self.assertEqual(assessment_tool_data.get(
            'description'), assessment_tool.description)
        self.assertEqual(assessment_tool_data.get('owning_company_id'), str(
            assessment_tool.owning_company.company_id))

    def test_create_test_flow_when_request_is_valid_and_user_is_company(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.flow_assert_response_correctness_when_request_is_valid(
            response=response,
            request_data=request_data,
            expected_number_of_tools=2,
            expected_usable=True,
            company=self.company_1
        )

        response_content = json.loads(response.content)
        tools = response_content.get('tools')

        test_flow_tool_1 = tools[0]
        self.assert_tool_data_correctness(
            test_flow_tool_1, self.assessment_tool_1)

        test_flow_tool_2 = tools[1]
        self.assert_tool_data_correctness(
            test_flow_tool_2, self.assessment_tool_2)

    def test_create_test_flow_when_user_does_not_own_assessment_tool(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_TEST_FLOW_URL,
            request_data=request_data,
            authenticated_user=self.company_2
        )
        self.flow_assert_response_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(
                self.assessment_tool_1.assessment_id, self.company_2.company_name
            )
        )


class AssessmentEventTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee_event@email.com',
            password='Password123'
        )

        self.company_1 = Company.objects.create_user(
            email='assessment_company@email.com',
            password='Password123',
            company_name='Company 1',
            description='Description',
            address='Company 1 address'
        )

        self.company_2 = Company.objects.create_user(
            email='assessment_company2@email.com',
            password='Password123',
            company_name='Company 2',
            description='Description 2',
            address='Company 2 address'
        )

        self.assessor = Assessor.objects.create_user(
            email="assessor_event@email.com",
            password='Password123',
            first_name='Assessor First',
            last_name='Assessor Last',
            phone_number='+11234567',
            associated_company=self.company_1,
            authentication_service=AuthenticationService.DEFAULT
        )

        self.assessment_tool = Assignment.objects.create(
            name='Assignment 1',
            description='Assignment Description',
            owning_company=self.company_1,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow_1 = TestFlow.objects.create(
            name='Test Flow 1',
            owning_company=self.company_1
        )

        self.test_flow_2 = TestFlow.objects.create(
            name='Test Flow 2',
            owning_company=self.company_1
        )

        self.test_flow_1.add_tool(
            self.assessment_tool,
            release_time=datetime.time(10, 20),
            start_working_time=datetime.time(11, 00)
        )

        self.start_date = datetime.datetime(year=2022, month=12, day=2)

        self.base_request_data = {
            'name': 'Assessment Manajer Tingkat 1 TE 2022',
            'start_date': '2022-12-02',
            'test_flow_id': str(self.test_flow_1.test_flow_id)
        }

    def test_get_test_flow_based_on_company_by_company(self):
        test_flows = get_test_flow_by_company(self.company_1)
        self.assertEqual(len(test_flows), 2)
        self.assertIn(self.test_flow_1, test_flows)

    def test_get_test_flow_based_on_company_by_assessor(self):
        test_flows = get_test_flow_by_company(self.assessor)
        self.assertEqual(len(test_flows), 2)
        self.assertIn(self.test_flow_2, test_flows)

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_name_is_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['name']
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), ASSESSMENT_EVENT_INVALID_NAME
            )

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_name_is_too_short(self):
        request_data = self.base_request_data.copy()
        request_data['name'] = 'AB'
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), ASSESSMENT_EVENT_INVALID_NAME)

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_name_is_too_long(self):
        request_data = self.base_request_data.copy()
        request_data['name'] = 'asjdnakjsdnaksjdnaskdnaskjdnaksdnasjdnaksdjansjdkansdkjnsad'
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), ASSESSMENT_EVENT_INVALID_NAME)

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_start_date_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['start_date']
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'Assessment Event should have a start date')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_id_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['test_flow_id']
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'Assessment Event should use a test flow')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_start_date_is_invalid_iso(self):
        request_data = self.base_request_data.copy()
        request_data['start_date'] = '2022-01-99T01:01:01'
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), INVALID_DATE_FORMAT.format(
                request_data['start_date']))

    @freeze_time('2022-12-03')
    def test_validate_assessment_event_when_start_date_is_a_previous_date(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'The assessment event must not begin on a previous date.')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_is_not_owned_by_company(self):
        request_data = self.base_request_data.copy()
        expected_message = ACTIVE_TEST_FLOW_NOT_FOUND.format(
            request_data["test_flow_id"], self.company_2.company_name)

        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_2)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception),
                expected_message
            )

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_is_not_active(self):
        request_data = self.base_request_data.copy()
        request_data['test_flow_id'] = str(self.test_flow_2.test_flow_id)
        expected_message = ACTIVE_TEST_FLOW_NOT_FOUND.format(
            request_data["test_flow_id"], self.company_2.company_name)

        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_2)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception),
                expected_message
            )

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_assessment_event(
                request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(AssessmentEvent, 'save')
    def test_save_assessment_event_called_save(self, mocked_save):
        request_data = self.base_request_data.copy()
        assessment_event.save_assessment_event(request_data, self.company_1)
        mocked_save.assert_called_once()

    def test_save_assessment_event_add_event_to_company(self):
        request_data = self.base_request_data.copy()
        saved_event = assessment_event.save_assessment_event(
            request_data, self.company_1)
        self.assertEqual(saved_event.owning_company, self.company_1)
        self.assertEqual(len(self.company_1.assessmenttool_set.all()), 1)

    def assessment_event_assert_correctness_when_request_is_invalid(self, response, expected_status_code,
                                                                    expected_message):
        self.assertEqual(response.status_code, expected_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), expected_message)

    def test_create_assessment_event_when_name_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['name']
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=ASSESSMENT_EVENT_INVALID_NAME
        )

    def test_create_assessment_event_when_name_is_too_short(self):
        request_data = self.base_request_data.copy()
        request_data['name'] = 'AB'
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=ASSESSMENT_EVENT_INVALID_NAME
        )

    def test_create_assessment_event_when_name_is_too_long(self):
        request_data = self.base_request_data.copy()
        request_data['name'] = 'abcdefghijklmnop1234jabcdefghijklmnop123456abcdefghijklmnop1234jabcdefghijklmnop123456'
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=ASSESSMENT_EVENT_INVALID_NAME
        )

    def test_create_assessment_when_start_date_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['start_date']
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='Assessment Event should have a start date'
        )

    def test_create_assessment_when_test_flow_id_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['test_flow_id']
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='Assessment Event should use a test flow'
        )

    def test_create_assessment_event_when_start_date_is_invalid_iso(self):
        request_data = self.base_request_data.copy()
        request_data['start_date'] = '0000-00-00'
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=INVALID_DATE_FORMAT.format(
                request_data['start_date'])
        )

    @freeze_time('2022-12-03')
    def test_create_assessment_event_when_start_date_is_a_previous_date(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='The assessment event must not begin on a previous date.'
        )

    def test_create_assessment_event_when_test_flow_is_not_active(self):
        request_data = self.base_request_data.copy()
        request_data['test_flow_id'] = str(self.test_flow_2.test_flow_id)
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=ACTIVE_TEST_FLOW_NOT_FOUND.format(
                request_data["test_flow_id"],
                self.company_1.company_name
            )
        )

    def test_create_assessment_event_when_test_flow_does_not_belong_to_company(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_2
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message=ACTIVE_TEST_FLOW_NOT_FOUND.format(
                request_data["test_flow_id"],
                self.company_2.company_name
            )
        )

    def test_create_assessment_event_when_user_is_assessee(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.assessee
        )
        self.assessment_event_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.FORBIDDEN,
            expected_message=f'User with email {self.assessee.email} is not a company or an assessor'
        )

    def test_create_assessment_event_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        expected_start_date_in_response = request_data['start_date'] + 'T00:00:00'
        response = fetch_and_get_response(
            path=CREATE_ASSESSMENT_EVENT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertIsNotNone(response_content.get('event_id'))
        self.assertEqual(response_content.get('name'), request_data['name'])
        self.assertEqual(response_content.get('start_date_time'), expected_start_date_in_response)
        self.assertEqual(response_content.get('owning_company_id'), str(self.company_1.company_id))
        self.assertEqual(response_content.get('test_flow_id'), request_data['test_flow_id'])


class AssessmentEventParticipationTest(TestCase):
    def setUp(self) -> None:
        self.company_1 = Company.objects.create_user(
            email='assessment_company_participation@email.com',
            password='Password123',
            company_name='Company 1',
            description='Description',
            address='Company 1 address'
        )

        self.company_2 = Company.objects.create_user(
            email='assessment_company_participation2@email.com',
            password='Password123',
            company_name='Company 2',
            description='Description 2',
            address='Company 2 address'
        )

        self.assessor_1 = Assessor.objects.create_user(
            email='assessor_1@email.com',
            password='Password123',
            first_name='Assessor First',
            last_name='Assessor Last',
            phone_number='+11234567',
            associated_company=self.company_1,
            authentication_service=AuthenticationService.DEFAULT
        )

        self.assessee = Assessee.objects.create_user(
            email='assessee@email.com',
            password='Password123'
        )

        self.assessment_tool = Assignment.objects.create(
            name='Assignment Participation',
            description='Assignment Description',
            owning_company=self.company_1,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow_1 = TestFlow.objects.create(
            name='Test Flow Participation',
            owning_company=self.company_1
        )

        self.test_flow_1.add_tool(
            self.assessment_tool,
            release_time=datetime.time(10, 20),
            start_working_time=datetime.time(11, 00)
        )

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event',
            start_date_time=datetime.datetime.now(),
            owning_company=self.company_1,
            test_flow_used=self.test_flow_1
        )

        self.base_request_data = {
            'assessment_event_id': str(self.assessment_event.event_id),
            'list_of_participants': [
                {
                    'assessee_email': self.assessee.email,
                    'assessor_email': self.assessor_1.email
                }
            ]
        }

        self.list_of_participants = [
            (self.assessee, self.assessor_1)
        ]

    @patch.object(AssessmentEventParticipation.objects, 'create')
    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_add_participation_when_assessee_has_not_been_registered(self, mocked_check, mocked_create):
        mocked_check.return_value = True
        self.assessment_event.add_participant(self.assessee, self.assessor_1)
        mocked_create.assert_not_called()

    @patch.object(VideoConferenceRoom.objects, 'create')
    @patch.object(TestFlowAttempt.objects, 'create')
    @patch.object(AssessmentEventParticipation.objects, 'create')
    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_add_participation_when_assessee_has_been_registered(self, mocked_check, mocked_create_participation,
                                                                 mocked_create_attempt,
                                                                 mocked_create_video_conference_room):
        mocked_check.return_value = False
        self.assessment_event.add_participant(self.assessee, self.assessor_1)
        mocked_create_participation.assert_called_once()
        mocked_create_video_conference_room.assert_called_once()

    def test_get_assessee_from_email_when_assessee_exist(self):
        found_assessee = utils.get_assessee_from_email(self.assessee.email)
        self.assertEqual(found_assessee, self.assessee)

    def test_get_assessee_from_email_when_assessee_does_not_exist(self):
        try:
            utils.get_assessee_from_email('email12@email.com')
            self.fail(EXCEPTION_NOT_RAISED)
        except ObjectDoesNotExist as exception:
            self.assertEqual(
                str(exception), f'Assessee with email email12@email.com not found')

    def test_get_assessor_from_email_when_assessor_exist(self):
        found_assessor = utils.get_company_assessor_from_email(
            self.assessor_1.email, self.company_1)
        self.assertEqual(found_assessor, self.assessor_1)

    def test_get_assessor_from_email_when_assessor_does_not_exist(self):
        try:
            utils.get_company_assessor_from_email(
                'email@email.com', self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except ObjectDoesNotExist as exception:
            self.assertEqual(
                str(exception),
                f'Assessor with email email@email.com associated with {self.company_1.company_name} is not found'
            )

    def test_get_assessor_from_email_when_assessor_exist_but_is_not_associated_with_company(self):
        try:
            utils.get_company_assessor_from_email(
                self.assessor_1.email, self.company_2)
            self.fail(EXCEPTION_NOT_RAISED)
        except ObjectDoesNotExist as exception:
            self.assertEqual(
                str(exception),
                f'Assessor with email {self.assessor_1.email} associated with {self.company_2.company_name} is not found'
            )

    def test_validate_add_event_participation_when_assessment_event_id_not_present(self):
        request_data = self.base_request_data.copy()
        del request_data['assessment_event_id']
        try:
            assessment_event.validate_add_assessment_participant(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'Assessment Event Id should be present in the request body')

    def test_validate_add_event_participation_when_list_of_participants_not_present(self):
        request_data = self.base_request_data.copy()
        del request_data['list_of_participants']
        try:
            assessment_event.validate_add_assessment_participant(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'The request should include a list of participants')

    def test_validate_add_event_participation_when_list_of_participants_not_a_list(self):
        request_data = self.base_request_data.copy()
        request_data['list_of_participants'] = 'email@email.com'
        try:
            assessment_event.validate_add_assessment_participant(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception), 'List of participants should be a list')

    def test_validate_add_event_participation_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_add_assessment_participant(request_data)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    def test_validate_assessment_event_ownership_when_assessment_event_does_not_belong_to_company(self):
        try:
            assessment_event.validate_assessment_event_ownership(
                self.assessment_event, self.company_2)
        except RestrictedAccessException as exception:
            self.assertEqual(
                str(exception),
                ASSESSMENT_EVENT_OWNERSHIP_INVALID.format(
                    self.assessment_event.event_id, self.company_2.company_id)
            )

    def test_validate_assessment_event_ownership_when_assessment_event_belongs_to_company(self):
        try:
            assessment_event.validate_assessment_event_ownership(
                self.assessment_event, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    def test_convert_list_of_participants_emails_to_user_objects_when_participants_inexist(self):
        converted_list = assessment_event.convert_list_of_participants_emails_to_user_objects([
        ], self.company_1)
        self.assertEqual(converted_list, [])

    @patch.object(utils, 'get_company_assessor_from_email')
    @patch.object(utils, 'get_assessee_from_email')
    def test_convert_list_of_participants_emails_to_user_objects_when_participants_exist(self, mocked_get_assessee,
                                                                                         mocked_get_assessor):
        mocked_get_assessee.return_value = self.assessee
        mocked_get_assessor.return_value = self.assessor_1
        request_data = self.base_request_data.copy()

        converted_list = assessment_event.convert_list_of_participants_emails_to_user_objects(
            request_data.get('list_of_participants'),
            self.company_1
        )

        self.assertEqual(len(converted_list), 1)
        self.assertTrue(isinstance(converted_list[0], tuple))
        converted_assessee = converted_list[0][0]
        converted_assessor = converted_list[0][1]
        self.assertEqual(converted_assessee, self.assessee)
        self.assertEqual(converted_assessor, self.assessor_1)

    @patch.object(utils, 'get_company_assessor_from_email')
    @patch.object(utils, 'get_assessee_from_email')
    def test_convert_list_of_participants_emails_to_user_objects_when_user_does_not_exist(self, mocked_get_assessee,
                                                                                          mocked_get_assessor):
        expected_message = f'Assessor with email {self.assessee.email} not found'
        request_data = self.base_request_data.copy()
        mocked_get_assessee.side_effect = ObjectDoesNotExist(expected_message)
        try:
            assessment_event.convert_list_of_participants_emails_to_user_objects(
                request_data.get('list_of_participants'), self.company_1
            )
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(AssessmentEvent, 'add_participant')
    def test_add_list_of_participants_to_event_when_list_of_participants_empty(self, mocked_add_participant):
        assessment_event.add_list_of_participants_to_event(
            self.assessment_event, [])
        mocked_add_participant.assert_not_called()

    @patch.object(AssessmentEvent, 'add_participant')
    def test_add_list_of_participants_to_event_when_list_of_participants_not_empty(self, mocked_add_participant):
        assessment_event.add_list_of_participants_to_event(
            self.assessment_event, self.list_of_participants)
        mocked_add_participant.assert_called_with(
            assessee=self.assessee, assessor=self.assessor_1)

    def add_participant_assert_correctness_when_request_is_invalid(self, response, expected_status_code,
                                                                   expected_message):
        self.assertEqual(response.status_code, expected_status_code)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), expected_message)

    def test_add_assessment_event_participation_when_assessment_event_id_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['assessment_event_id']
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.add_participant_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='Assessment Event Id should be present in the request body'
        )

    def test_add_assessment_event_participation_when_list_of_participants_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['list_of_participants']
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.add_participant_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='The request should include a list of participants'
        )

    def test_add_assessment_event_participation_when_list_of_participants_is_not_a_list(self):
        request_data = self.base_request_data.copy()
        request_data['list_of_participants'] = 'email1@gmail.com'
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )
        self.add_participant_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.BAD_REQUEST,
            expected_message='List of participants should be a list'
        )

    def test_add_assessment_event_participation_when_assessment_event_is_not_owned_by_company(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.company_2
        )
        self.add_participant_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.FORBIDDEN,
            expected_message=ASSESSMENT_EVENT_OWNERSHIP_INVALID.format(
                request_data['assessment_event_id'],
                self.company_2.company_id
            )
        )

    def test_add_assessment_event_participation_when_user_is_assessee(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.assessee
        )
        self.add_participant_assert_correctness_when_request_is_invalid(
            response=response,
            expected_status_code=HTTPStatus.FORBIDDEN,
            expected_message=f'User with email {self.assessee.email} is not a company or an assessor'
        )

    def test_add_assessment_event_participation_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        response = fetch_and_get_response(
            path=ADD_PARTICIPANT_URL,
            request_data=request_data,
            authenticated_user=self.company_1
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), 'Participants are successfully added')
        self.assertTrue(self.assessment_event.check_assessee_participation(self.assessee))


def fetch_and_get_response_subscription(access_token, assessment_event_id):
    client = Client()
    auth_headers = {'HTTP_AUTHORIZATION': 'Bearer ' + str(access_token)}
    response = client.get(
        EVENT_SUBSCRIPTION_URL + ASSESSMENT_EVENT_ID_PARAM_NAME + str(assessment_event_id),
        **auth_headers
    )
    return response


class AssesseeSubscribeToAssessmentEvent(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee_subs@assessee.com',
            password='Password123',
            first_name='Assessee',
            last_name='Lamb',
            phone_number='+62123141203',
            authentication_service=AuthenticationService.DEFAULT.value
        )
        self.assessee_token = RefreshToken.for_user(self.assessee)

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee_subs_2@assessee.com',
            password='Password123',
            first_name='Assessee',
            last_name='Sauce',
            phone_number='+2123141203',
            authentication_service=AuthenticationService.DEFAULT.value
        )
        self.assessee_2_token = RefreshToken.for_user(self.assessee_2)

        self.company = Company.objects.create_user(
            email='company@company.com',
            password='password',
            company_name='Company',
            description='Company Description A',
            address='JL. Company Levinson Durbin Householder'
        )
        self.company_token = RefreshToken.for_user(user=self.company)

        self.assignment_1 = AssessmentTool.objects.create(
            name='Base Assessment Tool',
            description='Base assessment description',
            owning_company=self.company
        )

        self.assignment_1 = Assignment.objects.create(
            name='Assignment Name',
            description='Assignment description',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=120
        )
        self.tool_1_release_time = datetime.time(10, 20)

        self.assignment_2 = Assignment.objects.create(
            name='Assignment Name 2',
            description='Assignment 2 description',
            owning_company=self.company,
            expected_file_format='docx',
            duration_in_minutes=30
        )
        self.tool_2_release_time = datetime.time(10, 30)

        self.test_flow = TestFlow.objects.create(
            name='Asisten Manajer Sub Divisi 5',
            owning_company=self.company
        )

        self.test_flow.add_tool(
            assessment_tool=self.assignment_1,
            release_time=self.tool_1_release_time,
            start_working_time=datetime.time(10, 30)
        )

        self.test_flow.add_tool(
            assessment_tool=self.assignment_2,
            release_time=self.tool_2_release_time,
            start_working_time=datetime.time(11, 50)
        )

        self.tool_1_expected_data = {
            'type': 'assignment',
            'name': self.assignment_1.name,
            'description': self.assignment_1.description,
            'additional_info': {
                'duration': self.assignment_1.duration_in_minutes,
                'expected_file_format': self.assignment_1.expected_file_format
            }
        }

        self.tool_2_expected_data = {
            'type': 'assignment',
            'name': self.assignment_2.name,
            'description': self.assignment_2.description,
            'additional_info': {
                'duration': self.assignment_2.duration_in_minutes,
                'expected_file_format': self.assignment_2.expected_file_format
            }
        }

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 2022',
            start_date_time=datetime.datetime(2022, 3, 30),
            owning_company=self.company,
            test_flow_used=self.test_flow
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor_1@gmail.com',
            password='password12A',
            first_name='Assessor',
            last_name='A',
            phone_number='+12312312312',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessor_2 = Assessor.objects.create_user(
            email='assessor_02@gmail.com',
            password='password12A',
            first_name='Assessor',
            last_name='A',
            phone_number='+12312312312',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessment_event.add_participant(
            assessee=self.assessee,
            assessor=self.assessor
        )

    def test_get_tool_data_of_assessment_tool(self):
        tool_data = self.assignment_1.get_tool_data()
        self.assertTrue(isinstance(tool_data, dict))
        self.assertEqual(tool_data.get('name'), self.assignment_1.name)
        self.assertEqual(tool_data.get('description'),
                         self.assignment_1.description)

    def test_get_tool_data_of_assignment(self):
        tool_data = self.assignment_1.get_tool_data()
        self.assertTrue(isinstance(tool_data, dict))
        self.assertDictEqual(tool_data, self.tool_1_expected_data)

    def test_get_tools_data_of_test_flow(self):
        tools_data = self.test_flow.get_tools_data()
        self.assertTrue(isinstance(tools_data, list))
        self.assertEqual(len(tools_data), 2)

        flow_tool_1_data = tools_data[0]
        tool_1_release_time = flow_tool_1_data.get('release_time')
        self.assertEqual(tool_1_release_time, str(self.tool_1_release_time))
        assessment_data_1 = flow_tool_1_data.get('assessment_data')
        self.assertDictEqual(assessment_data_1, self.tool_1_expected_data)

        flow_tool_2_data = tools_data[1]
        tool_2_release_time = flow_tool_2_data.get('release_time')
        self.assertEqual(tool_2_release_time, str(self.tool_2_release_time))
        assessment_data_2 = flow_tool_2_data.get('assessment_data')
        self.assertDictEqual(assessment_data_2, self.tool_2_expected_data)

    @patch.object(schedule.Job, 'at')
    def test_task_generator_of_assessment_event(self, mocked_job_at):
        task_generator = TaskGenerator.TaskGenerator()
        expected_job_do_call = call().do(
            task_generator._get_message_to_returned_value, 'message')
        task_generator.add_task(message='message', time_to_send='10:10:10')
        mocked_job_at.assert_called_with('10:10:10')
        job_do_call = mocked_job_at.mock_calls[1]
        self.assertEqual(job_do_call, expected_job_do_call)

    @patch.object(TaskGenerator.TaskGenerator, 'add_task')
    def test_get_task_generator(self, mocked_add_task):
        expected_calls = [
            call(self.assignment_1.get_tool_data(),
                 str(self.tool_1_release_time)),
            call(self.assignment_2.get_tool_data(),
                 str(self.tool_2_release_time))
        ]
        self.assessment_event.get_task_generator()
        mocked_add_task.assert_has_calls(expected_calls)

    def test_check_assessee_participation_when_assessee_is_a_participant(self):
        self.assertTrue(
            self.assessment_event.check_assessee_participation(self.assessee))

    def test_check_assessee_participation_when_assessee_is_not_a_participant(self):
        self.assertFalse(
            self.assessment_event.check_assessee_participation(self.assessee_2))

    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_validate_user_participation_when_user_participates_in_test_flow(self, mocked_check_participation):
        mocked_check_participation.return_value = True
        try:
            assessment_event_attempt.validate_user_participation(
                self.assessment_event, self.assessee)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_validate_user_participation_when_user_does_not_participate_in_test_flow(self, mocked_check_participation):
        mocked_check_participation.return_value = False
        try:
            assessment_event_attempt.validate_user_participation(
                self.assessment_event, self.assessee_2)
            self.fail(EXCEPTION_NOT_RAISED)
        except RestrictedAccessException as exception:
            self.assertEqual(str(exception), NOT_PART_OF_EVENT.format(
                self.assessee_2, self.assessment_event.event_id))

    def test_check_assessor_participation_when_assessor_is_a_participant(self):
        self.assertTrue(self.assessment_event.check_assessor_participation(self.assessor))

    def test_check_assessor_participation_when_assessor_is_not_a_participant(self):
        self.assertFalse(self.assessment_event.check_assessor_participation(self.assessor_2))

    @patch.object(AssessmentEvent, 'check_assessor_participation')
    def test_validate_assessor_participation_when_assessor_participates_in_test_flow(self, mocked_check_participation):
        mocked_check_participation.return_value = True
        try:
            assessment_event_attempt.validate_assessor_participation(self.assessment_event, self.assessor)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(AssessmentEvent, 'check_assessor_participation')
    def test_validate_assessor_participation_when_assessor_does_not_participate_in_test_flow(self,
                                                                                             mocked_check_participation):
        mocked_check_participation.return_value = False
        try:
            assessment_event_attempt.validate_assessor_participation(self.assessment_event, self.assessor_2)
            self.fail(EXCEPTION_NOT_RAISED)
        except RestrictedAccessException as exception:
            self.assertEqual(str(exception),
                             ASSESSOR_NOT_PART_OF_EVENT.format(self.assessor_2, self.assessment_event.event_id))

    def test_subscribe_when_user_is_not_an_assessee(self):
        response = fetch_and_get_response_subscription(
            access_token=self.company_token.access_token,
            assessment_event_id=self.assessment_event.event_id,
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get(
            'message'), 'User with email company@company.com is not an assessee')

    def test_subscribe_when_assessee_does_not_participate_in_event(self):
        response = fetch_and_get_response_subscription(
            access_token=self.assessee_2_token.access_token,
            assessment_event_id=self.assessment_event.event_id
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'Assessee with email {self.assessee_2} is not part of assessment with id {self.assessment_event.event_id}'
        )

    def test_subscribe_when_assessment_id_is_not_present(self):
        invalid_assessment_id = str(uuid.uuid4())
        response = fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=invalid_assessment_id
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            EVENT_DOES_NOT_EXIST.format(invalid_assessment_id)
        )

    def test_subscribe_when_assessment_id_is_random_string(self):
        invalid_assessment_id = 'assessment-id'
        response = fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=invalid_assessment_id
        )

        self.assertEqual(response.status_code,
                         HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch.object(TaskGenerator.TaskGenerator, 'generate')
    def test_subscribe_when_request_is_valid(self, mocked_generate):
        response = fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=self.assessment_event.event_id
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mocked_generate.assert_called_once()


class AssessmentToolTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company@company.com',
            password='password',
            company_name='Company',
            description='Company Description 2054',
            address='Jl. Company Not Company'
        )

        self.company_2 = Company.objects.create_user(
            email='compan2y@company.com',
            password='password',
            company_name='Company2',
            description='Company Description 2062',
            address='Jl. Company Not Company'
        )

        self.assessor_1 = Assessor.objects.create_user(
            email='assessor@assessor.com',
            password='password',
            first_name='Assessor',
            last_name='Assessor',
            phone_number='+6282312342071',
            employee_id='A&EX4NDER',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessor_2 = Assessor.objects.create_user(
            email='assessor2@assessor.com',
            password='password',
            first_name='Assessor2',
            last_name='Assessor2',
            phone_number='+6282312342082',
            employee_id='A&EX4NDER2',
            associated_company=self.company_2,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessment_tool = Assignment.objects.create(
            name='Important Presentation',
            description='Protect this presentation with all your life',
            owning_company=self.company,
            expected_file_format='pptx',
            duration_in_minutes=50
        )

    def test_get_tool_from_authorised_user(self):
        assessment_tool = get_assessment_tool_by_company(self.assessor_1)
        self.assertEqual(assessment_tool[0], self.assessment_tool)

    def test_get_tool_from_company(self):
        self.assertRaises(RestrictedAccessException, get_assessment_tool_by_company, self.company)

    def test_get_tool_from_different_user(self):
        assessment_tool = get_assessment_tool_by_company(self.assessor_2)
        self.assertEqual(len(assessment_tool), 0)

    def test_endpoint_for_getting_tools_list(self):
        client = APIClient()
        client.force_authenticate(self.assessor_1)
        response = client.get(GET_TOOLS_URL)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content[0].get("name"), self.assessment_tool.name)
        self.assertEqual(response_content[0].get("description"), self.assessment_tool.description)


def get_fetch_and_get_response(base_url, request_param, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    response = client.get(base_url + request_param)
    return response


class GetEventDataTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee_1783@email.com',
            password='Password12341785',
            first_name='Joko',
            last_name='Wiranto',
            phone_number='+62312331788',
            date_of_birth=datetime.date(2000, 11, 2),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='google@gmail.com',
            password='Password121795',
            company_name='Google, Ltd.',
            description='A search engine application',
            address='Jl. The Google Street'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor1802@gojek.com',
            password='Password12352',
            first_name='Robert',
            last_name='Journey',
            employee_id='AX123123',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment_1 = Assignment.objects.create(
            name='ASG Audit Kasus BPK',
            description='Audit kasus Korupsi PT ZK',
            owning_company=self.company,
            expected_file_format='pptx',
            duration_in_minutes=180
        )

        self.assignment_2 = Assignment.objects.create(
            name='ASG Audit Kasus G20',
            description='Pembuktian Pemberkasan Pengadaan Barang dan Jasa Terkait G20',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=100
        )

        self.response_test = ResponseTest.objects.create(
            name='Response Test 2172',
            description='Description of Response Test',
            owning_company=self.company,
            sender=self.assessor,
            subject='Welcome Onboard!',
            prompt='Hello, welcome to Google'
        )

        self.test_flow_1 = TestFlow.objects.create(
            name='KPK Subdit Siber Lat 1',
            owning_company=self.company
        )

        self.test_flow_1.add_tool(
            assessment_tool=self.assignment_1,
            release_time=datetime.time(9, 30),
            start_working_time=datetime.time(9, 50)
        )

        self.test_flow_1.add_tool(
            assessment_tool=self.assignment_2,
            release_time=datetime.time(22, 30),
            start_working_time=datetime.time(22, 30)
        )

        self.expected_test_flow_1_end_time = datetime.datetime(2022, 12, 13, 0, 10, tzinfo=pytz.utc)

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 2131',
            start_date_time=datetime.datetime(2022, 12, 12, hour=8, minute=0, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow_1
        )
        self.assessment_event_expected_end_time = datetime.datetime(2022, 12, 13, 0, 20, tzinfo=pytz.utc)

        self.expected_assessment_event = {
            'event_id': str(self.assessment_event.event_id),
            'name': self.assessment_event.name,
            'start_date_time': self.assessment_event.start_date_time.isoformat(),
            'end_date_time': self.assessment_event_expected_end_time.isoformat(),
            'owning_company_id': str(self.company.company_id),
            'test_flow_id': str(self.test_flow_1.test_flow_id)
        }

        self.assessment_event.add_participant(self.assessee, self.assessor)

        self.test_flow_2 = TestFlow.objects.create(
            name='Test Flow 2',
            owning_company=self.company
        )
        self.test_flow_2.add_tool(
            assessment_tool=self.assignment_1,
            release_time=datetime.time(10, 15),
            start_working_time=datetime.time(10, 15)
        )
        self.test_flow_2.add_tool(
            assessment_tool=self.response_test,
            release_time=datetime.time(13, 00),
            start_working_time=datetime.time(13, 00)
        )
        self.expected_test_flow_2_end_time = datetime.datetime(2022, 12, 12, 13, 30, tzinfo=pytz.utc)

        self.assessment_event_2 = AssessmentEvent.objects.create(
            name='Assessment Event 1845',
            start_date_time=datetime.datetime(2022, 12, 12, hour=8, minute=0, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow_2
        )

        self.base_request_data = {
            'assessment-event-id': str(self.assessment_event.event_id)
        }

    def test_get_test_flow_last_end_time_when_latest_is_not_response_test(self):
        test_flow_used = self.assessment_event.test_flow_used
        end_datetime = test_flow_used.get_test_flow_last_end_time_when_executed_on_event(
            self.assessment_event.start_date_time.date()
        )
        self.assertEqual(end_datetime, self.expected_test_flow_1_end_time)

    def test_get_test_flow_last_end_time_when_latest_is_a_response_test(self):
        test_flow_used = self.assessment_event_2.test_flow_used
        end_datetime = test_flow_used.get_test_flow_last_end_time_when_executed_on_event(
            self.assessment_event.start_date_time.date()
        )
        self.assertEqual(end_datetime, self.expected_test_flow_2_end_time)

    def test_get_event_end_date_time(self):
        end_datetime = self.assessment_event.get_event_end_date_time()
        self.assertEqual(end_datetime, self.assessment_event_expected_end_time)

    @freeze_time('2022-12-12 10:00:00')
    def test_serve_verify_assessee_participation_when_user_is_not_an_assessee(self):
        assessment_event_id = str(self.assessment_event.event_id)
        response = get_fetch_and_get_response(
            base_url=GET_EVENT_DATA,
            request_param=assessment_event_id,
            authenticated_user=self.company
        )
        self.assertEquals(response.status_code, HTTPStatus.FORBIDDEN)

    @freeze_time('2022-12-12 10:00:00')
    def test_serve_verify_assessee_participation_when_user_is_an_assessee_but_event_does_not_exist(self):
        assessment_event_id = str(uuid.uuid4())
        response = get_fetch_and_get_response(
            base_url=GET_EVENT_DATA,
            request_param=assessment_event_id,
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), EVENT_DOES_NOT_EXIST.format(assessment_event_id))

    @freeze_time('2022-12-12 10:00:00')
    def test_serve_verify_assessee_participation_when_user_is_an_assessee_but_not_part_of_assessment_event(self):
        assessment_event_id = str(self.assessment_event_2.event_id)
        response = get_fetch_and_get_response(
            base_url=GET_EVENT_DATA,
            request_param=assessment_event_id,
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'), NOT_PART_OF_EVENT.format(self.assessee.email, assessment_event_id)
        )

    @freeze_time('2022-12-12 10:00:00')
    def test_serve_verify_assessee_participation_when_user_is_an_assessee_and_is_part_of_assessment_event(self):
        assessment_event_id = str(self.assessment_event.event_id)
        response = get_fetch_and_get_response(
            base_url=GET_EVENT_DATA,
            request_param=assessment_event_id,
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertDictEqual(response_content, self.expected_assessment_event)


class ResponseTestTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company123@company.com',
            password='password123',
            company_name='Company123',
            description='Company123 Description',
            address='JL. Company Levinson Durbin 123'
        )

        self.assessor = Assessor.objects.create_user(
            email='vandermonde@assessor.com',
            password='password',
            first_name='VanDer',
            last_name='Monde',
            phone_number='+6282312345673',
            employee_id='A&EX4NDER3',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )
        self.request_data = {
            'name': 'Communication Task 1',
            'description': 'This is the first assignment',
            'subject': 'This is a dummy email',
            'prompt': 'Hi! This is a dummy email'
        }

        self.expected_response_test = ResponseTest(
            name=self.request_data.get('name'),
            description=self.request_data.get('description'),
            prompt=self.request_data.get('prompt'),
            subject=self.request_data.get('subject'),
            sender=self.assessor,
            owning_company=self.assessor.associated_company
        )

        self.expected_response_test_data = ResponseTestSerializer(self.expected_response_test).data

    def test_validate_response_test_is_valid(self):
        valid_request_data = self.request_data.copy()
        try:
            self.assertEqual(type(valid_request_data), dict)
            assessment.validate_response_test(valid_request_data)
        except InvalidResponseTestRegistration as exception:
            self.fail(f'{exception} is raised')

    def test_validate_response_test_when_subject_is_invalid(self):
        request_data_with_no_subject = self.request_data.copy()
        request_data_with_no_subject['subject'] = ''
        expected_message = 'Subject Should Not Be Empty'
        try:
            assessment.validate_response_test(request_data_with_no_subject)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidResponseTestRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    def test_validate_response_test_when_prompt_is_invalid(self):
        request_data_with_no_subject = self.request_data.copy()
        request_data_with_no_subject['prompt'] = ''
        expected_message = 'Prompt Should Not Be Empty'
        try:
            assessment.validate_response_test(request_data_with_no_subject)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidResponseTestRegistration as exception:
            self.assertEqual(str(exception), expected_message)

    @patch.object(ResponseTest.objects, 'create')
    def test_save_response_test_to_database(self, mocked_create):
        mocked_create.return_value = self.expected_response_test
        returned_assignment = assessment.save_response_test_to_database(self.request_data, self.assessor)
        returned_assignment_data = ResponseTestSerializer(returned_assignment).data
        mocked_create.assert_called_once()
        self.assertDictEqual(returned_assignment_data, self.expected_response_test_data)

    @patch.object(assessment, 'save_response_test_to_database')
    @patch.object(assessment, 'validate_response_test')
    @patch.object(assessment, 'validate_assessment_tool')
    @patch.object(assessment, 'get_assessor_or_raise_exception')
    def test_create_assignment(self, mocked_get_assessor, mocked_validate_assessment_tool,
                               mocked_validate_response_test, mocked_save_response_test):
        mocked_get_assessor.return_value = self.assessor
        mocked_validate_assessment_tool.return_value = None
        mocked_validate_response_test.return_value = None
        mocked_save_response_test.return_value = self.expected_response_test
        returned_assignment = assessment.create_response_test(self.request_data, self.assessor)
        returned_assignment_data = ResponseTestSerializer(returned_assignment).data
        self.assertDictEqual(returned_assignment_data, self.expected_response_test_data)

    def test_create_response_test_when_complete_status_200(self):
        assignment_data = json.dumps(self.request_data.copy())
        client = APIClient()
        client.force_authenticate(user=self.assessor)
        response = client.post(CREATE_RESPONSE_TEST_URL, data=assignment_data, content_type=REQUEST_CONTENT_TYPE)
        response_content = json.loads(response.content)
        self.assertEqual(response.status_code, OK_RESPONSE_STATUS_CODE)
        self.assertTrue(len(response_content) > 0)
        self.assertIsNotNone(response_content.get('assessment_id'))
        self.assertEqual(response_content.get('name'), self.expected_response_test_data.get('name'))
        self.assertEqual(response_content.get('description'), self.expected_response_test_data.get('description'))
        self.assertEqual(response_content.get('subject'), self.expected_response_test_data.get('subject'))
        self.assertEqual(response_content.get('prompt'), self.expected_response_test_data.get('prompt'))
        self.assertEqual(response_content.get('owning_company_id'), self.company.id)
        self.assertEqual(response_content.get('owning_company_name'), self.company.company_name)


def submit_file_and_get_request(request_data, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    response = client.post(SUBMIT_ASSIGNMENT_URL, request_data)
    return response


class AssignmentSubmissionTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee1973@email.com',
            password='Password1231974',
            first_name='Assessee 1975',
            last_name='Lastname 1976',
            phone_number='+6212345901',
            date_of_birth=datetime.date(2000, 12, 19),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='company1983@email.com',
            password='Password1231984',
            company_name='Company 1985',
            description='A description 1986',
            address='Gedung ABRR Jakarta Pusat, no 1987'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor1991@email.com',
            password='Password1992',
            phone_number='+9123123123',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment = Assignment.objects.create(
            name='Esai Singkat: The Power of Social Media',
            description='Kerjakan sesuai pemahaman Anda',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow_used = TestFlow.objects.create(
            name='Test Flow 2006',
            owning_company=self.company
        )

        self.test_flow_used.add_tool(
            assessment_tool=self.assignment,
            release_time=datetime.time(11, 50),
            start_working_time=datetime.time(11, 50)
        )

        self.assessment_event: AssessmentEvent = AssessmentEvent.objects.create(
            name='Assessment Event 2017',
            start_date_time=datetime.datetime(2022, 11, 25, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow_used
        )

        self.assessment_event.add_participant(self.assessee, self.assessor)

        self.event_participation = \
            AssessmentEventParticipation.objects.get(assessee=self.assessee, assessment_event=self.assessment_event)

        self.file = SimpleUploadedFile('report.pdf', b"file_content_2111", content_type=APPLICATION_PDF)
        self.assessment_tool = AssessmentTool.objects.create(
            name='Assessment Tool 2038',
            description='Description 2039',
            owning_company=self.company
        )

        self.assessment_tool_2 = AssessmentTool.objects.create(
            name='Assessment Tool 2055',
            description='Description 2056',
            owning_company=self.company
        )

        self.test_flow_used.add_tool(
            assessment_tool=self.assessment_tool_2,
            release_time=datetime.time(11, 52),
            start_working_time=datetime.time(11, 52)
        )

        self.assessment_event_2 = AssessmentEvent.objects.create(
            name='Assessment Event 2046',
            start_date_time=datetime.datetime(2022, 11, 27, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow_used
        )

        self.request_data = {
            'assessment-event-id': str(self.assessment_event.event_id),
            'assessment-tool-id': str(self.assignment.assessment_id),
            'file': self.file
        }

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee2060@email.com',
            password='Password1232061',
            first_name='Assessee 2062',
            last_name='Lastname 2063',
            phone_number='+6212342064',
            date_of_birth=datetime.date(2000, 12, 19),
            authentication_service=AuthenticationService.DEFAULT.value
        )

    def test_get_assessment_event_participation_by_assessee(self):
        retrieved_assessment_event: AssessmentEventParticipation = (
            self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee))

        self.assertEquals(retrieved_assessment_event.assessment_event, self.assessment_event)
        self.assertEquals(retrieved_assessment_event.assessee, self.assessee)

    def test_get_assignment_attempt_when_no_attempt_exist(self):
        assignment_attempt = self.event_participation.get_assignment_attempt(self.assignment)
        self.assertEquals(assignment_attempt, None)

    def test_get_assignment_attempt_when_attempt_exists(self):
        expected_attempt = AssignmentAttempt.objects.create(
            test_flow_attempt=self.event_participation.attempt,
            assessment_tool_attempted=self.assignment
        )
        assignment_attempt = self.event_participation.get_assignment_attempt(self.assignment)
        self.assertIsNotNone(assignment_attempt)
        self.assertEquals(assignment_attempt, expected_attempt)
        del assignment_attempt

    def test_create_assignment_attempt(self):
        assignment_attempt = self.event_participation.create_assignment_attempt(self.assignment)
        self.assertTrue(isinstance(assignment_attempt, AssignmentAttempt))
        self.assertEqual(assignment_attempt.test_flow_attempt, self.event_participation.attempt)
        self.assertEqual(assignment_attempt.assessment_tool_attempted, self.assignment)
        del assignment_attempt

    @patch.object(storage.Client, '__init__')
    @patch.object(storage.Blob, 'upload_from_file')
    @patch.object(storage.Bucket, 'blob')
    @patch.object(storage.Client, 'get_bucket')
    def test_upload_file_to_google_bucket(self, mocked_get_bucket, mocked_blob, mocked_upload, mocked_client):
        destination_file_name = '/submissions/tests/test-uploaded_file.pdf'
        bucket_name = 'one-day-intern-bucket'

        mocked_client.return_value = None
        mocked_get_bucket.return_value = storage.Bucket(client=None)
        mocked_blob.return_value = storage.Blob(name=destination_file_name, bucket=None)

        uploaded_file = SimpleUploadedFile('test-file.pdf', b'<sample-uploaded_file>', content_type=APPLICATION_PDF)
        google_storage.upload_file_to_google_bucket(
            destination_file_name=destination_file_name,
            bucket_name=bucket_name,
            file=uploaded_file
        )

        mocked_client.assert_called_once()
        mocked_get_bucket.assert_called_with(bucket_name)
        mocked_blob.assert_called_with(destination_file_name)
        mocked_upload.assert_called_with(file_obj=uploaded_file, rewind=True)

    @freeze_time("2022-11-05 12:00:00")
    def test_update_attempt_cloud_directory(self):
        assignment_attempt = AssignmentAttempt.objects.create(
            test_flow_attempt=self.event_participation.attempt,
            assessment_tool_attempted=self.assignment,
            file_upload_directory='/directory',
            filename='filename.jpg'
        )
        new_directory = '/new-directory'
        assignment_attempt.update_attempt_cloud_directory(new_directory)

        found_assignment_attempt = AssignmentAttempt.objects.get(tool_attempt_id=assignment_attempt.tool_attempt_id)
        self.assertEqual(found_assignment_attempt.get_attempt_cloud_directory(), new_directory)
        self.assertEqual(found_assignment_attempt.get_submitted_time(), datetime.datetime.now(tz=pytz.utc))

    def test_update_file_name(self):
        assignment_attempt = AssignmentAttempt.objects.create(
            test_flow_attempt=self.event_participation.attempt,
            assessment_tool_attempted=self.assignment,
            file_upload_directory='/directory',
            filename='filename-old.jpg'
        )
        new_name = 'filename-new.jpg'
        assignment_attempt.update_file_name(new_name)

        found_assignment_attempt = AssignmentAttempt.objects.get(tool_attempt_id=assignment_attempt.tool_attempt_id)
        self.assertEqual(found_assignment_attempt.get_file_name(), new_name)

    @patch.object(AssignmentAttempt, 'update_file_name')
    @patch.object(AssignmentAttempt, 'update_attempt_cloud_directory')
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    @patch.object(assessment_event_attempt, 'get_or_create_assignment_attempt')
    def test_save_assignment_attempt(self, mocked_create_attempt, mocked_upload, mocked_update_stored_dir,
                                     mocked_update_stored_filename):
        assessment_event_attempt.save_assignment_attempt(
            event=self.assessment_event,
            assignment=self.assignment,
            assessee=self.assessee,
            file_to_be_uploaded=self.file
        )
        assignment_attempt = AssignmentAttempt.objects.create(
            test_flow_attempt=self.event_participation.attempt,
            assessment_tool_attempted=self.assignment
        )
        cloud_storage_file_name = f'{GOOGLE_BUCKET_BASE_DIRECTORY}/' \
                                  f'{self.assessment_event.event_id}/' \
                                  f'{assignment_attempt.tool_attempt_id}.{self.assignment.expected_file_format}'
        mocked_create_attempt.return_value = assignment_attempt

        assessment_event_attempt.save_assignment_attempt(self.assessment_event, self.assignment, self.assessee,
                                                         self.file)
        mocked_create_attempt.assert_called_with(self.assessment_event, self.assignment, self.assessee)
        mocked_upload.assert_called_with(
            cloud_storage_file_name,
            GOOGLE_STORAGE_BUCKET_NAME,
            self.file
        )
        mocked_update_stored_dir.assert_called_with(cloud_storage_file_name)
        mocked_update_stored_filename.assert_called_with(self.file.name)

    def test_get_assessment_tool_from_assessment_id_when_tool_exist(self):
        try:
            self.assessment_event.get_assessment_tool_from_assessment_id(assessment_id=self.assignment.assessment_id)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    def test_get_assessment_tool_from_assessment_id_when_tool_does_not_exist(self):
        invalid_id = str(uuid.uuid4())
        try:
            self.assessment_event.get_assessment_tool_from_assessment_id(invalid_id)
            self.fail(EXCEPTION_NOT_RAISED)
        except AssessmentToolDoesNotExist as exception:
            self.assertEqual(str(exception), TOOL_OF_EVENT_NOT_FOUND.format(invalid_id, self.assessment_event.event_id))

    def test_validate_submission_when_assessment_tool_does_not_exist(self):
        try:
            assessment_event_attempt.validate_submission(None, self.file.name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), 'Assessment tool associated with event does not exist')

    def test_validate_submission_when_assessment_tool_is_not_an_assignment(self):
        try:
            assessment_event_attempt.validate_submission(self.assessment_tool, self.file.name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), TOOL_IS_NOT_ASSIGNMENT.format(self.assessment_tool.assessment_id))

    def test_validate_submission_when_no_file_name(self):
        try:
            assessment_event_attempt.validate_submission(self.assignment, '')
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), 'File name should not be empty')

    def test_validate_submission_when_improper_file_name(self):
        improper_file_name = 'report'
        try:
            assessment_event_attempt.validate_submission(self.assignment, improper_file_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), IMPROPER_FILE_NAME.format(improper_file_name))

    def test_validate_submission_when_prefix_does_not_match_expected(self):
        non_matching_file_name = 'report.pptx'
        try:
            assessment_event_attempt.validate_submission(self.assignment, non_matching_file_name)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidRequestException as exception:
            self.assertEqual(
                str(exception), FILENAME_DOES_NOT_MATCH_FORMAT.format(self.assignment.expected_file_format))

    def test_validate_submission_when_valid(self):
        try:
            assessment_event_attempt.validate_submission(self.assignment, self.file.name)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_event_with_id_does_not_exist(self, mocked_upload):
        request_data = self.request_data.copy()
        request_data['assessment-event-id'] = str(uuid.uuid4())
        response = submit_file_and_get_request(request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            EVENT_DOES_NOT_EXIST.format(request_data['assessment-event-id'])
        )

    @freeze_time("2022-11-23 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_event_with_id_is_not_active(self, mocked_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), EVENT_IS_NOT_ACTIVE.format(self.assessment_event.event_id))

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_user_is_not_assessee(self, mocked_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessor)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), f'User with email {self.assessor.email} is not an assessee')

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_user_is_not_part_of_event(self, mocked_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessee_2)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            NOT_PART_OF_EVENT.format(self.assessee_2.email, self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_tool_is_not_part_of_event(self, mocked_upload):
        request_data = self.request_data.copy()
        request_data['assessment-tool-id'] = str(self.assessment_tool.assessment_id)
        response = submit_file_and_get_request(request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            TOOL_OF_EVENT_NOT_FOUND.format(request_data['assessment-tool-id'], request_data['assessment-event-id'])
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_file_name_is_invalid(self, mocked_upload):
        invalid_filename = 'invalid_filename'
        uploaded_file = SimpleUploadedFile(invalid_filename, b'file_content', content_type=APPLICATION_PDF)
        request_data = self.request_data.copy()
        request_data['file'] = uploaded_file
        response = submit_file_and_get_request(request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), IMPROPER_FILE_NAME.format(invalid_filename))

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_file_name_does_match_expected(self, mocked_upload):
        non_matching_filename = 'report.pptx'
        uploaded_file = SimpleUploadedFile(non_matching_filename, b'file_content', content_type=APPLICATION_PDF)
        request_data = self.request_data.copy()
        request_data['file'] = uploaded_file
        response = submit_file_and_get_request(request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            FILENAME_DOES_NOT_MATCH_FORMAT.format(self.assignment.expected_file_format)
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_request_is_valid(self, mocked_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), 'File uploaded successfully')

        created_attempt = self.event_participation.get_assignment_attempt(self.assignment)
        self.assertEqual(created_attempt.filename, self.file.name)
        self.assertEqual(created_attempt.submitted_time, datetime.datetime.now(tz=pytz.utc))

    @patch.object(storage.Client, '__init__')
    @patch.object(storage.Blob, 'download_as_bytes')
    @patch.object(storage.Bucket, 'get_blob')
    @patch.object(storage.Client, 'get_bucket')
    def test_download_file_from_google_bucket(self, mocked_get_bucket, mocked_get_blob, mocked_download_as_bytes,
                                              mocked_client):
        cloud_directory = '/submissions/tests/test-file.pdf'
        target_file_name = 'test-file.pdf'
        content_type = APPLICATION_PDF
        bucket_name = 'one-day-intern-bucket'
        mocked_client.return_value = None
        mocked_get_bucket.return_value = storage.Bucket(client=None)
        mocked_get_blob.return_value = storage.Blob(name=cloud_directory, bucket=None)
        mocked_download_as_bytes.return_value = b'Hello World'

        downloaded_file = google_storage.download_file_from_google_bucket(
            cloud_directory, bucket_name, target_file_name, content_type
        )

        mocked_client.assert_called_once()
        mocked_get_bucket.assert_called_with(bucket_name)
        mocked_get_blob.assert_called_with(cloud_directory)
        mocked_download_as_bytes.assert_called_once()
        self.assertTrue(isinstance(downloaded_file, SimpleUploadedFile))
        self.assertEqual(downloaded_file.name, target_file_name)
        self.assertEqual(downloaded_file.content_type, content_type)

    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_download_assignment_attempt_when_attempt_does_not_exist(self, mocked_download):
        event_participation = self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee)
        assignment_attempt = event_participation.get_assignment_attempt(self.assignment)
        if assignment_attempt:
            del assignment_attempt

        downloaded_file = assessment_event_attempt.download_assignment_attempt(self.assessment_event, self.assignment, self.assessee)
        self.assertIsNone(downloaded_file)
        mocked_download.assert_not_called()

    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_download_assignment_attempt_when_attempt_exist(self, mocked_download):
        event_participation = self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee)
        assignment_attempt = event_participation.get_assignment_attempt(self.assignment)
        if not assignment_attempt:
            assignment_attempt = event_participation.create_assignment_attempt(self.assignment)
            assignment_attempt.update_file_name('report2385.pdf')

        cloud_storage_file_name = f'{GOOGLE_BUCKET_BASE_DIRECTORY}/' \
                                  f'{self.assessment_event.event_id}/' \
                                  f'{assignment_attempt.tool_attempt_id}.{self.assignment.expected_file_format}'

        assessment_event_attempt.download_assignment_attempt(self.assessment_event, self.assignment, self.assessee)
        mocked_download.assert_called_with(
            cloud_storage_file_name,
            GOOGLE_STORAGE_BUCKET_NAME,
            assignment_attempt.filename,
            APPLICATION_PDF
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_when_event_with_id_does_not_exist(self, mocked_download):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        invalid_event_id = str(uuid.uuid4())
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={invalid_event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'
        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), EVENT_DOES_NOT_EXIST.format(invalid_event_id))

    @freeze_time("2022-11-23 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_when_event_with_id_is_not_active(self, mocked_download):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'
        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), EVENT_IS_NOT_ACTIVE.format(self.assessment_event.event_id))

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_event_when_user_is_not_assessee(self, mocked_download):
        client = APIClient()
        client.force_authenticate(user=self.assessor)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'
        response = client.get(parameterized_url)
        response_content = json.loads(response.content)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(response_content.get('message'), USER_IS_NOT_ASSESSEE.format(self.assessor.email))

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_event_when_user_is_not_a_participant(self, mocked_download):
        client = APIClient()
        client.force_authenticate(user=self.assessee_2)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'
        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            NOT_PART_OF_EVENT.format(self.assessee_2.email, self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_event_when_tool_does_not_exist(self, mocked_download):
        invalid_tool_id = str(uuid.uuid4())
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={invalid_tool_id}'
        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            TOOL_OF_EVENT_NOT_FOUND.format(invalid_tool_id, self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_when_tool_is_not_an_assignment(self, mocked_download):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assessment_tool_2.assessment_id}'
        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            TOOL_IS_NOT_ASSIGNMENT.format(self.assessment_tool_2.assessment_id)
        )

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_when_request_is_valid_and_attempt_exist(self, mocked_download):
        event_participation = self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee)
        assignment_attempt = event_participation.get_assignment_attempt(self.assignment)
        if not assignment_attempt:
            assignment_attempt = event_participation.create_assignment_attempt(self.assignment)
            assignment_attempt.update_file_name('report2385.pdf')
        mocked_download.return_value = SimpleUploadedFile(assignment_attempt.get_file_name(), b'Hello World', content_type=APPLICATION_PDF)

        client = APIClient()
        client.force_authenticate(user=self.assessee)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'

        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        headers = response.headers
        self.assertEqual(headers.get('content-disposition'), f'attachment; filename="{assignment_attempt.get_file_name()}"')

    @freeze_time("2022-11-25 12:00:00")
    @patch.object(google_storage, 'download_file_from_google_bucket')
    def test_serve_submitted_assignment_when_request_is_valid_but_attempt_not_exist(self, mocked_download):
        event_participation = self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee)
        assignment_attempt = event_participation.get_assignment_attempt(self.assignment)
        if assignment_attempt:
            del assignment_attempt

        client = APIClient()
        client.force_authenticate(user=self.assessee)
        parameterized_url = f'{GET_AND_DOWNLOAD_ATTEMPT_URL}' \
                            f'?assessment-event-id={self.assessment_event.event_id}' \
                            f'&assessment-tool-id={self.assignment.assessment_id}'

        response = client.get(parameterized_url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), 'No attempt found')

    @freeze_time('2022-11-25 13:51:00')
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_assignment_has_been_released_but_deadline_has_passed(self, mock_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), CANNOT_SUBMIT_AT_THIS_TIME)

    @freeze_time('2022-11-25 11:49:59')
    @patch.object(google_storage, 'upload_file_to_google_bucket')
    def test_serve_submit_assignment_when_assignment_has_not_been_released_and_deadline_has_not_passed(self, mock_upload):
        response = submit_file_and_get_request(self.request_data, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), CANNOT_SUBMIT_AT_THIS_TIME)


class ActiveAssignmentTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company12943@email.com',
            password='Password1232944',
            company_name='Company 2945',
            description='A description 2946',
            address='Gedung ABRR Jakarta Pusat, no 2947'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor@email.com',
            password='Password2952',
            phone_number='+9123122953',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee = Assessee.objects.create_user(
            email='assessee2959@gmail.com',
            password='password2960',
            first_name='Assessee2061',
            last_name='Ajax2962',
            phone_number='+621234562963',
            date_of_birth=datetime.datetime.now(),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee2969@gmail.com',
            password='password2970',
            first_name='Assessee2971',
            last_name='Ajax2972',
            phone_number='+621234562973',
            date_of_birth=datetime.datetime.now(),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment = Assignment.objects.create(
            name='Esai Singkat: The Power of Mass Media',
            description='Kerjakan sesuai pemahaman Anda',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow_used = TestFlow.objects.create(
            name='Test Flow 2967',
            owning_company=self.company
        )

        self.test_flow_used.add_tool(
            assessment_tool=self.assignment,
            release_time=datetime.time(11, 50),
            start_working_time=datetime.time(11, 50)
        )

        self.test_flow_tool = self.test_flow_used.testflowtool_set.all()[0]

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 2978',
            start_date_time=datetime.datetime(2022, 11, 25, 8, 0),
            owning_company=self.company,
            test_flow_used=self.test_flow_used
        )

        self.expected_tool_data = {
            'id': str(self.assignment.assessment_id),
            'type': 'assignment',
            'name': self.assignment.name,
            'description': self.assignment.description,
            'additional_info': {
                'duration': self.assignment.duration_in_minutes,
                'expected_file_format': self.assignment.expected_file_format
            },
            'released_time': '2022-11-25T11:50:00',
            'end_working_time': '2022-11-25T13:50:00+00:00'
        }

        self.assessment_event.add_participant(
            assessee=self.assessee,
            assessor=self.assessor
        )

    @freeze_time("2022-11-25 12:00:00")
    def test_release_time_has_passed_on_event_day_when_time_has_passed_on_event_day(self):
        self.assertTrue(self.test_flow_tool.release_time_has_passed_on_event_day(
            self.assessment_event.start_date_time.date()))

    @freeze_time("2022-11-25 10:00:00")
    def test_release_time_has_passed_on_event_day_when_time_has_not_passed_on_event_day(self):
        self.assertFalse(self.test_flow_tool.release_time_has_passed_on_event_day(
            self.assessment_event.start_date_time.date()))

    @freeze_time("2022-11-26 12:00:00")
    def test_release_time_has_passed_on_event_day_when_time_has_passed_not_on_event_day(self):
        self.assertFalse(self.test_flow_tool.release_time_has_passed_on_event_day(
            self.assessment_event.start_date_time.date()))

    @freeze_time("2022-11-26 10:00:00")
    def test_release_time_has_passed_on_event_day_when_time_has_not_passed_not_on_event_day(self):
        self.assertFalse(self.test_flow_tool.release_time_has_passed_on_event_day(
            self.assessment_event.start_date_time.date()))

    def test_get_released_tool_data(self):
        tool_data = self.test_flow_tool.get_released_tool_data(self.assessment_event.start_date_time.date())
        self.assertDictEqual(tool_data, self.expected_tool_data)

    @freeze_time("2022-11-25 10:00:00")
    def get_released_assignments_when_its_event_day_but_no_assignment_is_released(self):
        released_assignments = self.assessment_event.get_released_assignments()
        self.assertEqual(len(released_assignments), 0)

    @freeze_time("2022-11-25 12:00:00")
    def get_released_assignments_when_its_event_day_and_assignment_has_been_released(self):
        released_assignments = self.assessment_event.get_released_assignments()
        self.assertEqual(len(released_assignments), 1)
        released_assignment = released_assignments[0]
        self.assertDictEqual(released_assignment, self.expected_tool_data)

    @freeze_time("2022-11-26 12:00:00")
    def get_released_assignments_when_its_not_event_day_but_time_has_passed(self):
        released_assignments = self.assessment_event.get_released_assignments()
        self.assertEqual(len(released_assignments), 0)

    @freeze_time("2022-11-26 10:00:00")
    def get_released_assignments_when_its_not_event_day_and_time_has_not_passed(self):
        released_assignments = self.assessment_event.get_released_assignments()
        self.assertEqual(len(released_assignments), 0)

    def test_serve_get_all_active_assignment_when_event_with_id_does_not_exist(self):
        invalid_id = str(uuid.uuid4())
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(invalid_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'), EVENT_DOES_NOT_EXIST.format(invalid_id)
        )

    @freeze_time("2022-11-24 08:00:00")
    def test_serve_get_all_active_assignment_when_event_is_not_active(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'), EVENT_IS_NOT_ACTIVE.format(self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 08:00:00")
    def test_serve_get_all_active_assignment_when_user_is_not_assessee(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.company
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'), USER_IS_NOT_ASSESSEE.format(self.company.email)
        )

    @freeze_time("2022-11-25 08:00:00")
    def test_serve_get_all_active_assignment_when_user_is_non_participating_assessee(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.assessee_2
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            NOT_PART_OF_EVENT.format(self.assessee_2.email, self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 08:00:00")
    def test_serve_get_all_active_assignment_when_its_event_day_but_time_has_not_passed(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content, [])

    @freeze_time("2022-11-24 08:00:00")
    def test_serve_get_all_active_assignment_when_its_not_event_day(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'), EVENT_IS_NOT_ACTIVE.format(self.assessment_event.event_id)
        )

    @freeze_time("2022-11-25 12:00:00")
    def test_serve_get_all_active_assignment_when_its_event_day_and_time_has_passed(self):
        response = get_fetch_and_get_response(
            base_url=GET_RELEASED_ASSIGNMENTS,
            request_param=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        response_content = json.loads(response.content)
        self.assertEqual(response_content, [self.expected_tool_data])


class AssessmentToolDeadlineTest(TestCase):
    def setUp(self) -> None:
        self.company = Company.objects.create_user(
            email='company2942@email.com',
            password='Password1232943',
            company_name='Company 2945',
            description='A description 2945',
            address='Gedung ABRR Jakarta Pusat, no 2946'
        )

        self.assessor = Assessor.objects.create(
            email='assessor2927@gmail.com',
            password='Password2798',
            first_name='First 2799',
            last_name='Last 2800',
            phone_number='+182312332801',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment = Assignment.objects.create(
            name='Esai Singkat: Menilik G20 untuk Perusahaan Tuitter',
            description='Kerjakan sesuai pemahaman Anda',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow_used = TestFlow.objects.create(
            name='Test Flow 2958',
            owning_company=self.company
        )

        self.test_flow_used.add_tool(
            assessment_tool=self.assignment,
            release_time=datetime.time(12, 00),
            start_working_time=datetime.time(12, 00)
        )

        self.assessment_event: AssessmentEvent = AssessmentEvent.objects.create(
            name='Assessment Event 2969',
            start_date_time=datetime.datetime(2022, 11, 25, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow_used
        )

        self.response_test = ResponseTest.objects.create(
            name='Response Test 2823',
            description='A response test 2824',
            owning_company=self.company,
            sender=self.assessor,
            subject='ASAP Contact Me',
            prompt='Contact me ASAP'
        )

        self.test_flow_used.add_tool(
            self.response_test,
            release_time=datetime.time(13, 00),
            start_working_time=datetime.time(13, 00)
        )

    @freeze_time('2022-11-25 14:00:00')
    def test_check_if_it_is_submittable_when_tool_is_released_and_deadline_has_not_passed(self):
        self.assertTrue(
            self.test_flow_used.check_if_is_submittable(
                self.assignment, self.assessment_event.start_date_time.date()
            )
        )

    @freeze_time('2022-11-25 15:00:00')
    def test_check_if_it_is_submittable_when_tool_is_released_and_deadline_has_passed(self):
        self.assertFalse(
            self.test_flow_used.check_if_is_submittable(
                self.assignment, self.assessment_event.start_date_time.date()
            )
        )

    @freeze_time('2022-11-25 11:00:00')
    def test_check_if_it_is_submittable_when_tool_has_not_been_released_and_deadline_has_not_passed(self):
        self.assertFalse(
            self.test_flow_used.check_if_is_submittable(
                self.assignment, self.assessment_event.start_date_time.date()
            )
        )

    @freeze_time('2022-11-24 15:00:00')
    def test_check_if_it_is_submittable_when_tool_has_not_been_released_and_deadline_has_passed(self):
        self.assertFalse(
            self.test_flow_used.check_if_is_submittable(
                self.assignment, self.assessment_event.start_date_time.date()
            )
        )

    def test_check_if_it_is_submittable_when_tool_is_a_response_test(self):
        self.assertTrue(
            self.test_flow_used.check_if_is_submittable(
                self.response_test, self.assessment_event.start_date_time.date()
            )
        )

    @patch.object(AssessmentEvent, 'check_if_tool_is_submittable')
    def test_validate_if_attempt_is_submittable_when_tool_is_submittable(self, mocked_check):
        mocked_check.return_value = True
        try:
            assessment_event_attempt.validate_attempt_is_submittable(self.assignment, self.assessment_event)
        except Exception as exception:
            self.fail(f'{exception} is raised')
        finally:
            mocked_check.assert_called_with(self.assignment)

    @patch.object(AssessmentEvent, 'check_if_tool_is_submittable')
    def test_validate_if_attempt_is_submittable_when_tool_is_not_submittable(self, mocked_check):
        mocked_check.return_value = False
        try:
            assessment_event_attempt.validate_attempt_is_submittable(self.assignment, self.assessment_event)
        except InvalidRequestException as exception:
            self.assertEqual(str(exception), CANNOT_SUBMIT_AT_THIS_TIME)
        finally:
            mocked_check.assert_called_with(self.assignment)