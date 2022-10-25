from django.urls import path
from .views import serve_create_assignment, serve_create_interactive_quiz

urlpatterns = [
    path('create/assignment/', serve_create_assignment),
    path('create/interactive-quiz/', serve_create_interactive_quiz),
]
