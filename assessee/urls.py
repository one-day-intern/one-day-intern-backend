from django.urls import path
from .views import assessee_dashboard, serve_get_assessment_events_of_assessee


urlpatterns = [
    path('dashboard/', assessee_dashboard, name='assessee_dashboard'),
    path('assessment-events/', serve_get_assessment_events_of_assessee, name='get-assessee-assessment-events'),
]
