from django.urls import path
from .views import serve_create_assignment, serve_create_interactive_quiz, \
    serve_create_test_flow


urlpatterns = [
    path('create/assignment/', serve_create_assignment),
    path('create/interactive-quiz/', serve_create_interactive_quiz),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
]
