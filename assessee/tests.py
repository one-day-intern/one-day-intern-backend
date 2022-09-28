from django.test import TestCase
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from users.models import OdiUser
import json


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