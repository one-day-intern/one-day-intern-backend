from django.contrib import admin
from .models import AssessmentTool, Assignment, InteractiveQuiz, Question, MultipleChoiceQuestion, \
    MultipleChoiceAnswerOption, TextQuestion, ResponseTest

admin.site.register(AssessmentTool)
admin.site.register(Assignment)
admin.site.register(InteractiveQuiz)
admin.site.register(Question)
admin.site.register(MultipleChoiceQuestion)
admin.site.register(MultipleChoiceAnswerOption)
admin.site.register(TextQuestion)
admin.site.register(ResponseTest)
