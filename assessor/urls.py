from django.urls import path
from .views import assessor_dashboard, serve_get_all_active_assessees

urlpatterns = [
    path('dashboard/', assessor_dashboard, name='assessor_dashboard'),
    path('assessee-list/', serve_get_all_active_assessees, name='assessee_list'),
]
