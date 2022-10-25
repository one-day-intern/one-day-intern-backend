from django.test import TestCase
from one_day_intern.exceptions import RestrictedAccessException, InvalidAssignmentRegistration, InvalidRequestException
from rest_framework.test import APIClient
from unittest.mock import patch
from users.models import (
    Company,
    Assessor,
    Assessee,
    AuthenticationService,
    AssessorSerializer
)
from .exceptions.exceptions import AssessmentToolDoesNotExist
from .models import Assignment, AssignmentSerializer, TestFlow, TestFlowTool
from .services import assessment, utils, test_flow
import datetime
import json
import uuid

EXCEPTION_NOT_RAISED = 'Exception not raised'
TEST_FLOW_INVALID_NAME = 'Test Flow name must exist and must be at most 50 characters'
CREATE_ASSIGNMENT_URL = '/assessment/create/assignment/'
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
        mocked_get_tool.side_effect = ValueError(expected_error_message)

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
