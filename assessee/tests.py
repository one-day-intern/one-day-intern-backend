from django.test import TestCase
from freezegun import freeze_time
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from http import HTTPStatus
from users.models import OdiUser, Assessee, AuthenticationService, Company, Assessor
from assessment.models import AssessmentEvent, Assignment, TestFlow, AssessmentEventSerializer
from .services import assessee_assessment_events
import datetime
import json
import pytz

GET_ASSESSEE_EVENTS_URL = reverse('get-assessee-assessment-events')


class ViewsTestCase(TestCase):
    def setUp(self):
        self.url = reverse("assessee_dashboard")    # use the view url
        self.user = OdiUser.objects.create(email="complete@email.co", password="password")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get(self):
        response = self.client.get(self.url)
        response.render()
        self.assertEquals(200, response.status_code)

        expected_content = {
            'past_events': [],
            'current_events': [],
            'future_events': [],
        }

        self.assertDictEqual(expected_content, json.loads(response.content))


class GetAssessmentEventTest(TestCase):
    def setUp(self) -> None:
        self.assessee = Assessee.objects.create_user(
            email='assessee_32@email.com',
            password='Password12334',
            first_name='Bambang',
            last_name='Haryono',
            phone_number='+62312334672',
            date_of_birth=datetime.date(2000, 11, 1),
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.company = Company.objects.create_user(
            email='gojek@gojek.com',
            password='Password12344',
            company_name='Gojek',
            description='A ride hailing application',
            address='Jl. The Gojek Street'
        )

        self.assessor = Assessor.objects.create_user(
            email='assessor51@gojek.com',
            password='Password12352',
            first_name='Robert',
            last_name='Journey',
            employee_id='AX123123',
            associated_company=self.company,
            authentication_service=AuthenticationService.DEFAULT.value
        )

        self.assignment = Assignment.objects.create(
            name='ASG Penelusuran Kasus',
            description='Menelusur kasus Korupsi PT A',
            owning_company=self.company,
            expected_file_format='pdf',
            duration_in_minutes=180
        )

        self.test_flow = TestFlow.objects.create(
            name='KPK Subdit 5 Lat 1',
            owning_company=self.company
        )
        self.test_flow.add_tool(
            assessment_tool=self.assignment,
            release_time=datetime.time(10, 30),
            start_working_time=datetime.time(10, 50)
        )

        self.assessment_event = AssessmentEvent.objects.create(
            name='Assessment Event 80',
            start_date_time=datetime.datetime(2022, 12, 12, hour=8, minute=0, tzinfo=pytz.utc),
            owning_company=self.company,
            test_flow_used=self.test_flow
        )
        self.expected_assessment_event = {
            'event_id': str(self.assessment_event.event_id),
            'name': self.assessment_event.name,
            'owning_company_id': str(self.company.company_id),
            'start_date_time': '2022-12-12T08:00:00+00:00',
            'end_date_time': '2022-12-12T14:00:00+00:00',
            'test_flow_id': str(self.test_flow.test_flow_id)
        }

        self.assessment_event.add_participant(self.assessee, self.assessor)

        self.assessee_2 = Assessee.objects.create_user(
            email='assessee_98@email.com',
            password='Password123499',
            first_name='Bambang',
            last_name='Haryono',
            phone_number='+6231233467102',
            date_of_birth=datetime.date(2000, 11, 1),
            authentication_service=AuthenticationService.DEFAULT.value
        )

    def test_all_assessment_events_from_assessee_when_has_events(self):
        assessment_events = assessee_assessment_events.all_assessment_events(self.assessee)
        self.assertEquals(assessment_events, [self.assessment_event])

    def test_all_assessment_events_from_assessee_when_no_events(self):
        assessment_events = assessee_assessment_events.all_assessment_events(self.assessee_2)
        self.assertEquals(assessment_events, [])

    @freeze_time('2022-11-01')
    def test_filter_active_assessment_events_when_no_assessment_events_is_active(self):
        assessment_events = [self.assessment_event]
        filtered_events = assessee_assessment_events.filter_active_assessment_events(assessment_events)
        self.assertEqual(filtered_events, [])

    @freeze_time('2022-12-12 09:00:00')
    def test_filter_active_assessment_events_when_assessment_event_is_active(self):
        assessment_events = [self.assessment_event]
        filtered_events = assessee_assessment_events.filter_active_assessment_events(assessment_events)
        self.assertEqual(filtered_events, assessment_events)

    @freeze_time('2022-11-01')
    def test_get_assessee_assessment_events(self):
        assessment_events = assessee_assessment_events.get_assessee_assessment_events(self.assessee, 'false')
        self.assertEquals(assessment_events, [self.assessment_event])

    @freeze_time('2022-11-01')
    def test_get_assessee_assessment_events_when_find_active_true_but_no_active_events(self):
        assessment_events = assessee_assessment_events.get_assessee_assessment_events(self.assessee, 'true')
        self.assertEquals(assessment_events, [])

    @freeze_time('2022-12-12 09:00:00')
    def test_get_assessee_assessment_events_when_find_active_true_and_exist_active_events(self):
        assessment_events = assessee_assessment_events.get_assessee_assessment_events(self.assessee, 'true')
        self.assertEquals(assessment_events, [self.assessment_event])

    def test_get_assessee_assessment_events_end_to_end(self):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        response = client.get(GET_ASSESSEE_EVENTS_URL)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        self.assertEqual(len(response_content), 1)
        fetched_event = response_content[0]
        self.assertDictEqual(fetched_event, self.expected_assessment_event)

    @freeze_time('2022-11-01')
    def test_get_assessee_assessment_events_when_find_active_true_but_no_active_events_end_to_end(self):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        response = client.get(GET_ASSESSEE_EVENTS_URL + '?is-active=true')

        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        self.assertEqual(len(response_content), 0)

    @freeze_time('2022-12-12 09:00:00')
    def test_get_assessee_assessment_events_when_find_active_true_and_exist_active_events_end_to_end(self):
        client = APIClient()
        client.force_authenticate(user=self.assessee)
        response = client.get(GET_ASSESSEE_EVENTS_URL + '?is-active=true')

        self.assertEquals(response.status_code, HTTPStatus.OK)
        response_content = json.loads(response.content)
        self.assertTrue(isinstance(response_content, list))
        self.assertEqual(len(response_content), 1)

        fetched_event = response_content[0]
        self.assertEqual(fetched_event, self.expected_assessment_event)
