from assessment.models import (
    AssessmentTool,
    Assignment,
    TestFlow,
    AssessmentEvent,
    AssessmentEventSerializer,
    AssignmentAttempt,
    PolymorphicAssessmentToolSerializer,
    AssessmentEventParticipation
)
from django.test import TestCase
from freezegun import freeze_time
from http import HTTPStatus
from unittest.mock import patch
from users.models import OdiUser, Assessee, AuthenticationService, Company, Assessor, AssesseeSerializer
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
import datetime
import json
import pytz
import uuid

GET_ACTIVE_ASSESSEES = reverse('assessee_list') + '?assessment-event-id='
GET_ACTIVE_EVENT_PARTICIPATIONS = reverse('assessment_event_list')


def fetch_all_active_assessees(event_id, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    response = client.get(GET_ACTIVE_ASSESSEES + event_id)
    return response


def fetch_all_assessment_events(authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    response = client.get(GET_ACTIVE_EVENT_PARTICIPATIONS)
    return response


def fetch_all_active_assessees(event_id, authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    response = client.get(GET_ACTIVE_ASSESSEES + event_id)
    return response


class ActiveAssessmentEventParticipationTest(TestCase):
    def setUp(self) -> None:
        self.assessee_1 = Assessee.objects.create_user(
            email='assessee_132@gmail.com',
            password='password123',
            phone_number='+621234123',
            date_of_birth=datetime.date(2000, 10, 10),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee_208@gmail.com',
            password='password123',
            phone_number='+6212331232',
            date_of_birth=datetime.date(2000, 10, 11),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='company_1607@gmail.com',
            password='Password123',
            company_name='Company Name',
            description='Description Company 1610',
            address='Address 1611'
        )

        self.assessor_1 = Assessor.objects.create_user(
            email='assessor_1@gmail.com',
            password='password12A',
            first_name='Assessor',
            last_name='A',
            phone_number='+12312312312',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessor_2 = Assessor.objects.create_user(
            email='assessor_2@gmail.com',
            password='password123',
            first_name='Assessor',
            last_name='B',
            phone_number='+621234123',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
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
            start_date_time=datetime.datetime(2022, 3, 30, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow
        )

        self.assessment_event.add_participant(
            assessee=self.assessee_1,
            assessor=self.assessor_1
        )

        self.assessment_event.add_participant(
            assessee=self.assessee_2,
            assessor=self.assessor_1
        )

        self.expected_assessees = [
            AssesseeSerializer(self.assessee_1).data,
            AssesseeSerializer(self.assessee_2).data,
        ]

    def test_get_all_active_assessees_when_event_id_is_invalid(self):
        invalid_event_id = str(uuid.uuid4())
        response = fetch_all_active_assessees(invalid_event_id, authenticated_user=self.assessor_1)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(response_content.get('message'), f'Assessment Event with ID {invalid_event_id} does not exist')

    @freeze_time("2022-02-27")
    def test_get_all_active_assessees_when_event_is_not_active(self):
        response = fetch_all_active_assessees(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessor_1
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'Assessment Event with ID {str(self.assessment_event.event_id)} is not active'
        )

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assessees_when_user_not_assessor(self):
        response = fetch_all_active_assessees(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessee_1
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'User with email {self.assessee_1.email} is not an assessor'
        )

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assessees_when_user_is_not_a_participant(self):
        response = fetch_all_active_assessees(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessor_2
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assessees_when_request_is_valid(self):
        response = fetch_all_active_assessees(
            event_id=str(self.assessment_event.event_id),
            authenticated_user=self.assessor_1
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        self.assertEqual(response_content, self.expected_assessees)

    @freeze_time("2022-03-30 11:00:00")
    def test_get_all_active_assessment_events_when_user_not_assessor(self):
        response = fetch_all_assessment_events(
            authenticated_user=self.assessee_1
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content.get('message'),
            f'User with email {self.assessee_1.email} is not an assessor'
        )

    @freeze_time("2022-03-30 11:00:00", tz_offset=0)
    def test_get_all_assessment_events_when_request_is_valid(self):
        response = fetch_all_assessment_events(
            authenticated_user=self.assessor_1
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        expected_assessment_event_data = AssessmentEventSerializer(self.assessment_event).data
        expected_assessment_event_data['owning_company_id'] = str(self.company.company_id)
        expected_assessment_event_data['test_flow_id'] = str(self.test_flow.test_flow_id)
        self.assertEqual(response_content, [expected_assessment_event_data])

        response = fetch_all_assessment_events(
            authenticated_user=self.company
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        expected_assessment_event_data = AssessmentEventSerializer(self.assessment_event).data
        expected_assessment_event_data['owning_company_id'] = str(self.company.company_id)
        expected_assessment_event_data['test_flow_id'] = str(self.test_flow.test_flow_id)


class ViewsTestCase(TestCase):
    def setUp(self):
        self.url = reverse("assessor_dashboard")  # use the view url
        self.user = OdiUser.objects.create(email="complete@email.co", password="password")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get(self):
        response = self.client.get(self.url)
        response.render()
        self.assertEquals(200, response.status_code)

        expected_content = {
            'test_flows': [],
            'list_of_assessees': [],
        }

        self.assertDictEqual(expected_content, json.loads(response.content))


class ViewEventProgressTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee249@email.com',
            password='Password250',
            first_name='Assessee 251',
            last_name='Assessee 252',
            phone_number='+628123253',
            date_of_birth=datetime.date(1998, 12, 25),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee275@email.com',
            password='Password276',
            first_name='Assessee 277',
            last_name='Assessee 2578',
            phone_number='+628123279',
            date_of_birth=datetime.date(1998, 12, 26),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessee_3 = Assessee.objects.create_user(
            email='assessee287@email.com',
            password='Password286',
            first_name='Assessee 287',
            last_name='Assessee 2588',
            phone_number='+628123289',
            date_of_birth=datetime.date(1998, 12, 26),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='company259@email.com',
            password='Password260',
            company_name='Company 261',
            description='Description 262',
            address='Address 263'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor267@email.com',
            password='Password268',
            first_name='Assessor 269',
            last_name='Assessor 270',
            phone_number='+62823271',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessor_2 = Assessor.objects.create_user(
            email='assessor290@email.com',
            password='Password291',
            first_name='Assessor 292',
            last_name='Assessor 293',
            phone_number='+62823294',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assessor_3 = Assessor.objects.create_user(
            email='assessor314@email.com',
            password='Password314',
            first_name='Assessor 314',
            last_name='Assessor 317',
            phone_number='+62823314',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment_1 = Assignment.objects.create(
            name='Assignment 277',
            description='Assignment Description 278',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=180
        )
        self.assignment_1_data = PolymorphicAssessmentToolSerializer(self.assignment_1).data

        self.test_flow = TestFlow.objects.create(
            name='Test Flow 285',
            owning_company=self.company
        )

        self.test_flow.add_tool(
            self.assignment_1,
            release_time=datetime.time(10, 30),
            start_working_time=datetime.time(10, 30)
        )

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 296',
            start_date_time=datetime.datetime(2022, 11, 22, 1, 30, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow
        )

        self.assessment_event.add_participant(
            assessee=self.assessee,
            assessor=self.assessor
        )

        self.assessment_event.add_participant(
            assessee=self.assessee_3,
            assessor=self.assessor_3
        )

        self.assessment_event_participation = \
            self.assessment_event.get_assessment_event_participation_by_assessee(self.assessee)

        self.event_tool = self.test_flow.testflowtool_set.get(assessment_tool=self.assignment_1)

        self.assignment_start_date_time = \
            self.event_tool.get_iso_start_working_time_on_event_date(self.assessment_event.start_date_time)

        self.expected_attempt_data = {
            'start_working_time': self.assignment_start_date_time,
            'tool-data': self.assignment_1_data,
            'attempt-id': None
        }

    def test_get_assessment_tool_attempt_when_no_attempt_has_been_submitted(self):
        attempt = self.assessment_event_participation.get_assessment_tool_attempt(self.assignment_1)
        self.assertIsNone(attempt)

    def test_get_assessment_tool_attempt_when_an_attempt_has_been_submitted(self):
        assignment_attempt = self.assessment_event_participation.create_assignment_attempt(self.assignment_1)
        attempt = self.assessment_event_participation.get_assessment_tool_attempt(self.assignment_1)
        self.assertIsNotNone(attempt)
        self.assertTrue(isinstance(attempt, AssignmentAttempt))
        self.assertEqual(attempt.tool_attempt_id, assignment_attempt.tool_attempt_id)
        assignment_attempt.delete()

    @patch.object(AssessmentEventParticipation, 'get_assessment_tool_attempt')
    def test_get_event_progress_when_no_attempt_has_been_submitted(self, mock_get_attempt):
        mock_get_attempt.return_value = None
        progress_data = self.assessment_event_participation.get_event_progress()
        mock_get_attempt.assert_called_with(self.assignment_1)
        self.assertEqual(len(progress_data), 1)
        attempt_data = progress_data[0]
        self.assertDictEqual(attempt_data, self.expected_attempt_data)

    @patch.object(AssessmentEventParticipation, 'get_assessment_tool_attempt')
    def test_get_event_progress_when_an_attempt_has_been_submitted(self, mock_get_attempt):
        temporary_attempt = AssignmentAttempt.objects.create(
            test_flow_attempt=self.assessment_event_participation.attempt,
            assessment_tool_attempted=self.assignment_1,
        )
        mock_get_attempt.return_value = temporary_attempt
        progress_data = self.assessment_event_participation.get_event_progress()
        mock_get_attempt.assert_called_with(self.assignment_1)
        self.assertEqual(len(progress_data), 1)
        attempt_data = progress_data[0]
        expected_attempt_data = self.expected_attempt_data.copy()
        expected_attempt_data['attempt-id'] = temporary_attempt.tool_attempt_id
        self.assertDictEqual(attempt_data, expected_attempt_data)
        temporary_attempt.delete()