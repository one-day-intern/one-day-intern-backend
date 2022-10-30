from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, Client
from django.urls import reverse
from freezegun import freeze_time
from http import HTTPStatus
from one_day_intern.exceptions import RestrictedAccessException, InvalidAssignmentRegistration
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
    TestFlow,
    TestFlowTool,
    AssessmentEvent,
    TestFlowAttempt,
    AssessmentEventParticipation
)
from .services import assessment, utils, test_flow, assessment_event, assessment_event_attempt, TaskGenerator
import datetime
import json
import schedule
import uuid

EXCEPTION_NOT_RAISED = 'Exception not raised'
TEST_FLOW_INVALID_NAME = 'Test Flow name must exist and must be at most 50 characters'
TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT = 'Assessment tool with id {} belonging to company {} does not exist'
ASSESSMENT_EVENT_INVALID_NAME = 'Assessment Event name must be minimum of length 3 and at most 50 characters'
ACTIVE_TEST_FLOW_NOT_FOUND = 'Active test flow of id {} belonging to {} does not exist'
INVALID_DATE_FORMAT = '{} is not a valid ISO date string'
ASSESSMENT_EVENT_OWNERSHIP_INVALID = 'Event with id {} does not belong to company with id {}'
NOT_PART_OF_EVENT = 'Assessee with email {} is not part of assessment with id {}'
CREATE_ASSIGNMENT_URL = '/assessment/create/assignment/'
CREATE_TEST_FLOW_URL = reverse('test-flow-create')
CREATE_ASSESSMENT_EVENT_URL = reverse('assessment-event-create')
ADD_PARTICIPANT_URL = reverse('event-add-participation')
EVENT_SUBSCRIPTION_URL = reverse('event-subscription')
GET_RELEASED_ASSIGNMENTS = reverse('event-active-assignments') + '?assessment-event-id='
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
        self.assertEqual(response_content.get('owning_company_name'), self.company.company_name)


def fetch_and_get_response(path, request_data, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    request_data_json = json.dumps(request_data)
    response = client.post(path, data=request_data_json, content_type='application/json')
    return response


class TestFlowTest(TestCase):
    def setUp(self) -> None:
        self.company_1 = Company.objects.create_user(
            email='companytestflow@company.com',
            password='password',
            company_name='Company',
            description='Company Description',
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
        retrieved_assessment_tool = utils.get_tool_of_company_from_id(tool_id, self.company_1)
        self.assertEqual(str(retrieved_assessment_tool.assessment_id), tool_id)
        self.assertEqual(retrieved_assessment_tool.name, self.assessment_tool_1.name)
        self.assertEqual(retrieved_assessment_tool.description, self.assessment_tool_1.description)
        self.assertEqual(retrieved_assessment_tool.expected_file_format, self.assessment_tool_1.expected_file_format)
        self.assertEqual(retrieved_assessment_tool.duration_in_minutes, self.assessment_tool_1.duration_in_minutes)

    def test_et_tool_of_company_from_id_when_tool_does_not_exist(self):
        tool_id = str(uuid.uuid4())
        expected_message = TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(tool_id, self.company_1.company_name)

        try:
            utils.get_tool_of_company_from_id(tool_id, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except AssessmentToolDoesNotExist as exception:
            self.assertEqual(str(exception), expected_message)

    def test_get_tool_from_id_when_tool_exists_but_does_not_belong_to_company(self):
        tool_id = str(self.assessment_tool_3.assessment_id)
        expected_message = TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(tool_id, self.company_1.company_name)

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
        time_: datetime.time = utils.get_time_from_date_time_string(valid_iso_date)
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

        test_flow_.add_tool(self.assessment_tool_1, release_time=release_time, start_working_time=start_working_time)
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
            test_flow.validate_test_flow_registration(request_data, self.company_1)
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
            test_flow.validate_test_flow_registration(request_data, self.company_1)
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
            test_flow.validate_test_flow_registration(request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_contain_tool_used(self, mocked_get_tool, mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()

        try:
            test_flow.validate_test_flow_registration(request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_validate_test_flow_when_tool_does_not_exist(self, mocked_get_tool, mocked_get_time):
        invalid_tool_id = str(uuid.uuid4())
        expected_error_message = f'Assessment tool with id {invalid_tool_id} does not exist'
        mocked_get_time.return_value = None
        mocked_get_tool.side_effect = AssessmentToolDoesNotExist(expected_error_message)
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = [{
            'tool_id': invalid_tool_id,
            'release_time': '2022-10-25T01:20:00.000Z',
            'start_working_time': '2022-10-25T04:20:00.000Z'
        }]

        try:
            test_flow.validate_test_flow_registration(request_data, self.company_1)
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
            test_flow.validate_test_flow_registration(request_data, self.company_1)
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
            test_flow.validate_test_flow_registration(request_data, self.company_1)
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
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data, self.company_1)
        self.assertEqual(converted_tool, [])

    @patch.object(utils, 'get_time_from_date_time_string')
    @patch.object(utils, 'get_tool_of_company_from_id')
    def test_convert_assessment_tool_id_to_assessment_tool_when_tools_used_is_empty(self, mocked_get_tool,
                                                                                    mocked_get_time):
        mocked_get_tool.return_value = None
        mocked_get_time.return_value = None
        request_data = self.base_request_data.copy()
        request_data['tools_used'] = []
        converted_tool = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data, self.company_1)
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
        converted_tools = test_flow.convert_assessment_tool_id_to_assessment_tool(request_data, self.company_1)

        self.assertEqual(len(converted_tools), number_of_assessment_tools)
        tool_data_assessment_1 = converted_tools[1]
        self.assertIsNotNone(tool_data_assessment_1.get('tool'))
        self.assertIsNotNone(tool_data_assessment_1.get('release_time'))
        self.assertIsNotNone(tool_data_assessment_1.get('start_working_time'))

        tool = tool_data_assessment_1['tool']
        release_time = tool_data_assessment_1['release_time']
        start_working_time = tool_data_assessment_1['start_working_time']
        self.assertEqual(tool.assessment_id, self.assessment_tool_1.assessment_id)
        self.assertEqual(release_time, expected_returned_time)
        self.assertEqual(start_working_time, expected_returned_time)

    @patch.object(TestFlow, 'save')
    @patch.object(TestFlow, 'add_tool')
    def test_save_test_flow_to_database_when_converted_tools_is_empty(self, mocked_add_tool, mocked_save):
        converted_tools = []
        request_data = self.base_request_data.copy()
        saved_test_flow = test_flow.save_test_flow_to_database(request_data, converted_tools, self.company_1)
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

        saved_test_flow = test_flow.save_test_flow_to_database(request_data, converted_tools, self.company_1)
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
            expected_message=
            TEST_FLOW_OF_COMPANY_DOES_NOT_EXIST_FORMAT.format(non_exist_tool_id, self.company_1.company_name)
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
        self.assertEqual(assessment_tool_data.get('name'), assessment_tool.name)
        self.assertEqual(assessment_tool_data.get('description'), assessment_tool.description)
        self.assertEqual(assessment_tool_data.get('owning_company_id'), str(assessment_tool.owning_company.company_id))

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
        self.assert_tool_data_correctness(test_flow_tool_1, self.assessment_tool_1)

        test_flow_tool_2 = tools[1]
        self.assert_tool_data_correctness(test_flow_tool_2, self.assessment_tool_2)

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

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_name_is_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['name']
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
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
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), ASSESSMENT_EVENT_INVALID_NAME)

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_name_is_too_long(self):
        request_data = self.base_request_data.copy()
        request_data['name'] = 'asjdnakjsdnaksjdnaskdnaskjdnaksdnasjdnaksdjansjdkansdkjnsad'
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), ASSESSMENT_EVENT_INVALID_NAME)

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_start_date_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['start_date']
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), 'Assessment Event should have a start date')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_id_does_not_exist(self):
        request_data = self.base_request_data.copy()
        del request_data['test_flow_id']
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), 'Assessment Event should use a test flow')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_start_date_is_invalid_iso(self):
        request_data = self.base_request_data.copy()
        request_data['start_date'] = '2022-01-99T01:01:01'
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), INVALID_DATE_FORMAT.format(request_data['start_date']))

    @freeze_time('2022-12-03')
    def test_validate_assessment_event_when_start_date_is_a_previous_date(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), 'The assessment event must not begin on a previous date.')

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_is_not_owned_by_company(self):
        request_data = self.base_request_data.copy()
        expected_message = ACTIVE_TEST_FLOW_NOT_FOUND.format(request_data["test_flow_id"], self.company_2.company_name)

        try:
            assessment_event.validate_assessment_event(request_data, self.company_2)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception),
                expected_message
            )

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_test_flow_is_not_active(self):
        request_data = self.base_request_data.copy()
        request_data['test_flow_id'] = str(self.test_flow_2.test_flow_id)
        expected_message = ACTIVE_TEST_FLOW_NOT_FOUND.format(request_data["test_flow_id"], self.company_2.company_name)

        try:
            assessment_event.validate_assessment_event(request_data, self.company_2)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(
                str(exception),
                expected_message
            )

    @freeze_time('2022-12-01')
    def test_validate_assessment_event_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_assessment_event(request_data, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(AssessmentEvent, 'save')
    def test_save_assessment_event_called_save(self, mocked_save):
        request_data = self.base_request_data.copy()
        assessment_event.save_assessment_event(request_data, self.company_1)
        mocked_save.assert_called_once()

    def test_save_assessment_event_add_event_to_company(self):
        request_data = self.base_request_data.copy()
        saved_event = assessment_event.save_assessment_event(request_data, self.company_1)
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
            expected_message=INVALID_DATE_FORMAT.format(request_data['start_date'])
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
        expected_start_date_in_response = request_data['start_date'] + 'T00:00:00Z'
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

    @patch.object(TestFlowAttempt.objects, 'create')
    @patch.object(AssessmentEventParticipation.objects, 'create')
    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_add_participation_when_assessee_has_been_registered(self, mocked_check, mocked_create_participation,
                                                                 mocked_create_attempt):
        mocked_check.return_value = False
        self.assessment_event.add_participant(self.assessee, self.assessor_1)
        mocked_create_participation.assert_called_once()

    def test_get_assessee_from_email_when_assessee_exist(self):
        found_assessee = utils.get_assessee_from_email(self.assessee.email)
        self.assertEqual(found_assessee, self.assessee)

    def test_get_assessee_from_email_when_assessee_does_not_exist(self):
        try:
            utils.get_assessee_from_email('email12@email.com')
            self.fail(EXCEPTION_NOT_RAISED)
        except ObjectDoesNotExist as exception:
            self.assertEqual(str(exception), f'Assessee with email email12@email.com not found')

    def test_get_assessor_from_email_when_assessor_exist(self):
        found_assessor = utils.get_company_assessor_from_email(self.assessor_1.email, self.company_1)
        self.assertEqual(found_assessor, self.assessor_1)

    def test_get_assessor_from_email_when_assessor_does_not_exist(self):
        try:
            utils.get_company_assessor_from_email('email@email.com', self.company_1)
            self.fail(EXCEPTION_NOT_RAISED)
        except ObjectDoesNotExist as exception:
            self.assertEqual(
                str(exception),
                f'Assessor with email email@email.com associated with {self.company_1.company_name} is not found'
            )

    def test_get_assessor_from_email_when_assessor_exist_but_is_not_associated_with_company(self):
        try:
            utils.get_company_assessor_from_email(self.assessor_1, self.company_2)
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
            self.assertEqual(str(exception), 'Assessment Event Id should be present in the request body')

    def test_validate_add_event_participation_when_list_of_participants_not_present(self):
        request_data = self.base_request_data.copy()
        del request_data['list_of_participants']
        try:
            assessment_event.validate_add_assessment_participant(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), 'The request should include a list of participants')

    def test_validate_add_event_participation_when_list_of_participants_not_a_list(self):
        request_data = self.base_request_data.copy()
        request_data['list_of_participants'] = 'email@email.com'
        try:
            assessment_event.validate_add_assessment_participant(request_data)
            self.fail(EXCEPTION_NOT_RAISED)
        except InvalidAssessmentEventRegistration as exception:
            self.assertEqual(str(exception), 'List of participants should be a list')

    def test_validate_add_event_participation_when_request_is_valid(self):
        request_data = self.base_request_data.copy()
        try:
            assessment_event.validate_add_assessment_participant(request_data)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    def test_validate_assessment_event_ownership_when_assessment_event_does_not_belong_to_company(self):
        try:
            assessment_event.validate_assessment_event_ownership(self.assessment_event, self.company_2)
        except RestrictedAccessException as exception:
            self.assertEqual(
                str(exception),
                ASSESSMENT_EVENT_OWNERSHIP_INVALID.format(self.assessment_event.event_id, self.company_2.company_id)
            )

    def test_validate_assessment_event_ownership_when_assessment_event_belongs_to_company(self):
        try:
            assessment_event.validate_assessment_event_ownership(self.assessment_event, self.company_1)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    def test_convert_list_of_participants_emails_to_user_objects_when_participants_inexist(self):
        converted_list = assessment_event.convert_list_of_participants_emails_to_user_objects([], self.company_1)
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
    def test_convert_list_of_participants_emails_to_user_objects_when_user_does_not_exist(self, mocked_get_assessee,                                                                              mocked_get_assessor):
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
        assessment_event.add_list_of_participants_to_event(self.assessment_event, [])
        mocked_add_participant.assert_not_called()

    @patch.object(AssessmentEvent, 'add_participant')
    def test_add_list_of_participants_to_event_when_list_of_participants_not_empty(self, mocked_add_participant):
        assessment_event.add_list_of_participants_to_event(self.assessment_event, self.list_of_participants)
        mocked_add_participant.assert_called_with(assessee=self.assessee, assessor=self.assessor_1)

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
                'duration': self.assignment_1.duration_in_minutes
            }
        }

        self.tool_2_expected_data = {
            'type': 'assignment',
            'name': self.assignment_2.name,
            'description': self.assignment_2.description,
            'additional_info': {
                'duration': self.assignment_2.duration_in_minutes
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

        self.assessment_event.add_participant(
            assessee=self.assessee,
            assessor=self.assessor
        )

    def test_get_tool_data_of_assessment_tool(self):
        tool_data = self.assignment_1.get_tool_data()
        self.assertTrue(isinstance(tool_data, dict))
        self.assertEqual(tool_data.get('name'), self.assignment_1.name)
        self.assertEqual(tool_data.get('description'), self.assignment_1.description)

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
        self.assertEqual(tool_2_release_time,  str(self.tool_2_release_time))
        assessment_data_2 = flow_tool_2_data.get('assessment_data')
        self.assertDictEqual(assessment_data_2, self.tool_2_expected_data)

    @patch.object(schedule.Job, 'at')
    def test_task_generator_of_assessment_event(self, mocked_job_at):
        task_generator = TaskGenerator.TaskGenerator()
        expected_job_do_call = call().do(task_generator._get_message_to_returned_value, 'message')
        task_generator.add_task(message='message', time_to_send='10:10:10')
        mocked_job_at.assert_called_with('10:10:10')
        job_do_call = mocked_job_at.mock_calls[1]
        self.assertEqual(job_do_call, expected_job_do_call)

    @patch.object(TaskGenerator.TaskGenerator, 'add_task')
    def test_get_task_generator(self, mocked_add_task):
        expected_calls = [
            call(self.assignment_1.get_tool_data(), str(self.tool_1_release_time)),
            call(self.assignment_2.get_tool_data(), str(self.tool_2_release_time))
        ]
        self.assessment_event.get_task_generator()
        mocked_add_task.assert_has_calls(expected_calls)

    def test_check_assessee_participation_when_assessee_is_a_participant(self):
        self.assertTrue(self.assessment_event.check_assessee_participation(self.assessee))

    def test_check_assessee_participation_when_assessee_is_not_a_participant(self):
        self.assertFalse(self.assessment_event.check_assessee_participation(self.assessee_2))

    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_validate_user_participation_when_user_participates_in_test_flow(self, mocked_check_participation):
        mocked_check_participation.return_value = True
        try:
            assessment_event_attempt.validate_user_participation(self.assessment_event, self.assessee)
        except Exception as exception:
            self.fail(f'{exception} is raised')

    @patch.object(AssessmentEvent, 'check_assessee_participation')
    def test_validate_user_participation_when_user_does_not_participate_in_test_flow(self, mocked_check_participation):
        mocked_check_participation.return_value = False
        try:
            assessment_event_attempt.validate_user_participation(self.assessment_event, self.assessee_2)
            self.fail(EXCEPTION_NOT_RAISED)
        except RestrictedAccessException as exception:
            self.assertEqual(str(exception), NOT_PART_OF_EVENT.format(self.assessee_2, self.assessment_event.event_id))

    def fetch_and_get_response_subscription(self, access_token, assessment_event_id):
        client = Client()
        auth_headers = {'HTTP_AUTHORIZATION': 'Bearer ' + str(access_token)}
        response = client.get(
            EVENT_SUBSCRIPTION_URL + '?assessment-event-id=' + str(assessment_event_id),
            **auth_headers
        )
        return response

    def test_subscribe_when_user_is_not_an_assessee(self):
        response = self.fetch_and_get_response_subscription(
            access_token=self.company_token.access_token,
            assessment_event_id=self.assessment_event.event_id,
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), 'User with email company@company.com is not an assessee')

    def test_subscribe_when_assessee_does_not_participate_in_event(self):
        response = self.fetch_and_get_response_subscription(
            access_token=self.assessee_2_token.access_token,
            assessment_event_id=self.assessment_event.event_id
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'Assessee with email {self.assessee_2} is not part of assessment with id {self.assessment_event.event_id}'
        )

    def test_subscribe_when_assessment_id_is_not_present(self):
        invalid_assessment_id = str(uuid.uuid4())
        response = self.fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=invalid_assessment_id
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'Assessment with id {invalid_assessment_id} does not exist'
        )

    def test_subscribe_when_assessment_id_is_random_string(self):
        invalid_assessment_id = 'assessment-id'
        response = self.fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=invalid_assessment_id
        )

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch.object(TaskGenerator.TaskGenerator, 'generate')
    def test_subscribe_when_request_is_valid(self, mocked_generate):
        response = self.fetch_and_get_response_subscription(
            access_token=self.assessee_token.access_token,
            assessment_event_id=self.assessment_event.event_id
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mocked_generate.assert_called_once()


class ActiveAssessmentToolTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee_132@gmail.com',
            password='password123',
            phone_number='+621234123',
            date_of_birth=datetime.date(2000, 10, 10),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee_1608@gmail.com',
            password='password123',
            phone_number='+621234123',
            date_of_birth=datetime.date(2000, 10, 10),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='company_1607@gmail.com',
            password='Password123',
            company_name='Company Name',
            description='Description Company 1610',
            address='Address 1611'
        )

        self.assessment_tool = AssessmentTool.objects.create(
            name='Assignment Name 1615',
            description='Assignment description 1616',
            owning_company=self.company
        )

        self.assignment = Assignment.objects.create(
            name='Assignment Name 1615',
            description='Assignment description 1616',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=120
        )

        self.test_flow = TestFlow.objects.create(
            name='Asisten Manajer Sub Divisi 1623',
            owning_company=self.company
        )

        self.tool_1_release_time = datetime.time(10, 30)
        self.test_flow.add_tool(
            assessment_tool=self.assignment,
            release_time=self.tool_1_release_time,
            start_working_time=self.tool_1_release_time
        )

        self.test_flow.add_tool(
            assessment_tool=self.assessment_tool,
            release_time=datetime.time(10, 40),
            start_working_time=datetime.time(10, 40)
        )

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 1635',
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

        self.assessment_event.add_participant(
            assessee=self.assessee,
            assessor=self.assessor
        )

        self.expected_flow_tool_data = {
            'name': self.assignment.name,
            'description': self.assignment.description,
            'type': 'assignment',
            'additional_info': {
                'duration': self.assignment.duration_in_minutes,
                'expected_file_format': self.assignment.expected_file_format
            },
            'id': str(self.assignment.assessment_id),
            'released_time': str(self.tool_1_release_time),
            'end_working_time': str(datetime.time(12, 30))
        }

    def test_get_end_working_time_of_assignment(self):
        expected_end_work_time = datetime.time(12, 30)
        returned_time = self.assignment.get_end_working_time(self.tool_1_release_time)
        self.assertEqual(returned_time, expected_end_work_time)

    @freeze_time("2012-01-14 10:29")
    def test_release_time_has_passed_when_time_has_not_passed(self):
        test_flow_tool = self.test_flow.testflowtool_set.all()[0]
        self.assertFalse(test_flow_tool.release_time_has_passed())

    @freeze_time("2012-01-14 10:30")
    def test_release_time_has_passed_when_time_has_not_passed(self):
        test_flow_tool = self.test_flow.testflowtool_set.all()[0]
        self.assertTrue(test_flow_tool.release_time_has_passed())

    def test_get_released_tool_data_when_tool_is_assignment(self):
        test_flow_tool = self.test_flow.testflowtool_set.all()[0]
        test_flow_tool_data = test_flow_tool.get_released_tool_data()
        self.assertDictEqual(test_flow_tool_data, self.expected_flow_tool_data)

    @freeze_time("2012-01-14 10:45")
    def test_get_released_assignment_when_assignment_should_be_released(self):
        released_assignments_data = self.assessment_event.get_released_assignments()
        self.assertEqual(released_assignments_data, [self.expected_flow_tool_data])

    @freeze_time("2012-01-14 10:29")
    def test_get_released_assignment_when_assignment_should_not_be_released(self):
        released_assignments_data = self.assessment_event.get_released_assignments()
        self.assertEqual(released_assignments_data, [])

    def fetch_all_active_assignment(self, event_id, authenticated_user):
        client = APIClient()
        client.force_authenticate(user=authenticated_user)
        response = client.get(GET_RELEASED_ASSIGNMENTS + event_id)
        return response

    def test_get_all_active_assignment_when_event_id_is_invalid(self):
        invalid_event_id = str(uuid.uuid4())
        response = self.fetch_all_active_assignment(invalid_event_id, authenticated_user=self.assessee)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), f'Assessment with id {invalid_event_id} does not exist')

    @freeze_time("2022-02-27")
    def test_get_all_active_assignment_when_event_is_not_active(self):
        response = self.fetch_all_active_assignment(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'Assessment with id {str(self.assessment_event.event_id)} is not active'
        )

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assignment_when_user_not_assessee(self):
        response = self.fetch_all_active_assignment(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessor
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'User with email {self.assessor.email} is not an assessee'
        )

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assignment_when_user_is_not_a_participant(self):
        response = self.fetch_all_active_assignment(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessee_2
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assignment_when_request_is_valid(self):
        response = self.fetch_all_active_assignment(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessee
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        self.assertEqual(response_content, [self.expected_flow_tool_data])