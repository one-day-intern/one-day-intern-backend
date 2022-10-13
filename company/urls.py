from django.urls import path
from .views import serve_send_one_time_code_to_assessors


urlpatterns = [
    path('one-time-code/generate/', serve_send_one_time_code_to_assessors)
]
