from django.urls import path
from .views import serve_send_one_time_code_to_assessors, serve_get_company_assessors


urlpatterns = [
    path('one-time-code/generate/', serve_send_one_time_code_to_assessors),
    path('assessors/', serve_get_company_assessors, name='get-company-assessors'),
]
