from django.db import models
from rest_framework import serializers
import uuid


class AssessmentTool(models.Model):
    assessment_id = models.UUIDField(primary_key=True, auto_created=True, default=uuid.uuid4)
    name = models.CharField(max_length=50, null=False)
    description = models.TextField(null=True)
    owning_company = models.ForeignKey('users.Company', on_delete=models.CASCADE)


class Assignment(AssessmentTool):
    expected_file_format = models.CharField(max_length=5, null=True)
    duration_in_minutes = models.IntegerField(null=False)


class AssignmentSerializer(serializers.ModelSerializer):
    owning_company_name = serializers.ReadOnlyField(source='owning_company.company_name')

    class Meta:
        model = Assignment
        fields = [
            'assessment_id',
            'name',
            'description',
            'expected_file_format',
            'duration_in_minutes',
            'owning_company_id',
            'owning_company_name'
        ]


class InteractiveQuiz(AssessmentTool):
    duration_in_minutes = models.IntegerField(null=False)
    total_points = models.IntegerField(null=False)


class Question(models.Model):
    TYPES_CHOICES = [
        ('text', 'Text Question'),
        ('multiple_choice', 'Multiple Choice Question')
    ]

    interactive_quiz = models.ForeignKey(InteractiveQuiz, related_name='questions', on_delete=models.CASCADE)
    prompt = models.TextField(null=False)
    points = models.IntegerField(default=0)
    question_type = models.CharField(choices=TYPES_CHOICES, null=False, max_length=16)


class MultipleChoiceQuestion(Question):
    def get_answer_options(self):
        return self.multiplechoiceansweroption_set


class MultipleChoiceAnswerOption(models.Model):
    question = models.ForeignKey('MultipleChoiceQuestion', related_name='questions', on_delete=models.CASCADE)
    content = models.TextField(null=False)
    correct = models.BooleanField(default=False)


class TextQuestion(Question):
    answer_key = models.TextField(null=True)


class MultipleChoiceAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MultipleChoiceAnswerOption
        fields = [
            'content',
            'correct'
        ]


class MultipleChoiceQuestionSerializer(serializers.ModelSerializer):

    class Meta:
        model = MultipleChoiceQuestion
        fields = [
            'prompt',
            'points',
            'question_type',
        ]


class TextQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextQuestion
        fields = [
            'prompt',
            'points',
            'question_type',
            'answer_key'
        ]


class QuestionSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        if isinstance(instance, MultipleChoiceQuestion):
            return MultipleChoiceQuestionSerializer(instance=instance).data
        elif isinstance(instance, TextQuestion):
            return TextQuestionSerializer(instance=instance).data


class InteractiveQuizSerializer(serializers.ModelSerializer):
    owning_company_name = serializers.ReadOnlyField(source='owning_company.company_name')

    class Meta:
        model = InteractiveQuiz
        fields = [
            'assessment_id',
            'name',
            'description',
            'total_points',
            'duration_in_minutes',
            'owning_company_id',
            'owning_company_name'
        ]

