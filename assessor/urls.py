from django.urls import path
from .views import (
    assessor_dashboard,
    serve_get_all_active_assessees,
    serve_get_all_assessment_events,
    serve_get_assessee_progress_on_event
)

urlpatterns = [
    path('dashboard/', assessor_dashboard, name='assessor_dashboard'),
    path('assessment-event-list/', serve_get_all_assessment_events, name='assessment_event_list'),
    path('assessee-list/', serve_get_all_active_assessees, name='assessee_list'),
    path('assessment-event/progress/', serve_get_assessee_progress_on_event, name='get-assessee-progress')
]
