from django.db import models
from rest_framework import serializers
from polymorphic.models import PolymorphicModel
import datetime
import uuid


class AssessmentTool(PolymorphicModel):
    assessment_id = models.UUIDField(primary_key=True, auto_created=True, default=uuid.uuid4)
    name = models.CharField(max_length=50, null=False)
    description = models.TextField(null=True)
    owning_company = models.ForeignKey('users.Company', on_delete=models.CASCADE)


class AssessmentToolSerializer(serializers.ModelSerializer):
    owning_company_id = serializers.ReadOnlyField(source='owning_company.company_id')

    class Meta:
        model = AssessmentTool
        fields = ['assessment_id', 'name', 'description', 'owning_company_id']


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

    def save_answer_option_to_database(self, answer: dict):
        content = answer.get('content')
        correct = answer.get('correct')

        answer_option = MultipleChoiceAnswerOption.objects.create(
            question=self,
            content=content,
            correct=correct
        )

        return answer_option


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


def to_representation(instance):
    if isinstance(instance, MultipleChoiceQuestion):
        return MultipleChoiceQuestionSerializer(instance=instance).data
    elif isinstance(instance, TextQuestion):
        return TextQuestionSerializer(instance=instance).data


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextQuestion
        fields = [
            'prompt',
            'points',
            'question_type',
        ]


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


class TestFlow(models.Model):
    test_flow_id = models.UUIDField(default=uuid.uuid4, auto_created=True)
    name = models.CharField(max_length=50)
    owning_company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    tools = models.ManyToManyField(AssessmentTool, through='TestFlowTool')
    is_usable = models.BooleanField(default=False)

    def add_tool(self, assessment_tool, release_time, start_working_time):
        self.is_usable = True
        TestFlowTool.objects.create(
            assessment_tool=assessment_tool,
            test_flow=self,
            release_time=release_time,
            start_working_time=start_working_time
        )
        self.save()

    def get_is_usable(self):
        return self.is_usable


class TestFlowTool(models.Model):
    assessment_tool = models.ForeignKey('assessment.AssessmentTool', on_delete=models.CASCADE)
    test_flow = models.ForeignKey(TestFlow, on_delete=models.CASCADE)
    release_time = models.TimeField(auto_now=False, auto_now_add=False, default=datetime.time(0, 0))
    start_working_time = models.TimeField(auto_now=False, auto_now_add=False, default=datetime.time(0, 0))

    class Meta:
        ordering = ['release_time']
        get_latest_by = 'release_time'


class TestFlowToolSerializer(serializers.ModelSerializer):
    assessment_tool = AssessmentToolSerializer(read_only=True)
    test_flow_id = serializers.ReadOnlyField(source='test_flow.test_flow_id')

    class Meta:
        model = TestFlowTool
        fields = ['assessment_tool', 'test_flow_id', 'release_time']


class TestFlowSerializer(serializers.ModelSerializer):
    owning_company_id = serializers.ReadOnlyField(source='owning_company.company_id')
    tools = TestFlowToolSerializer(source='testflowtool_set', read_only=True, many=True)

    class Meta:
        model = TestFlow
        fields = ['test_flow_id', 'name', 'owning_company_id', 'is_usable', 'tools']


class AssessmentEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, auto_created=True)
    name = models.CharField(max_length=50)
    start_date_time = models.DateTimeField()
    owning_company = models.ForeignKey('users.Company', on_delete=models.CASCADE)
    test_flow_used = models.ForeignKey('assessment.TestFlow', on_delete=models.RESTRICT)

    def check_company_ownership(self, company):
        return self.owning_company.company_id == company.company_id

    def add_participant(self, assessee, assessor):
        if not self.check_assessee_participation(assessee):
            assessment_event_participation = AssessmentEventParticipation.objects.create(
                assessment_event=self,
                assessee=assessee,
                assessor=assessor
            )

            TestFlowAttempt.objects.create(
                event_participation=assessment_event_participation,
                test_flow_attempted=self.test_flow_used
            )

            return assessment_event_participation

    def check_assessee_participation(self, assessee):
        found_assessees = AssessmentEventParticipation.objects.filter(
            assessment_event=self,
            assessee=assessee
        )
        return found_assessees.exists()


class AssessmentEventSerializer(serializers.ModelSerializer):
    owning_company_id = serializers.ReadOnlyField(source='owning_company.company_id')
    test_flow_id = serializers.ReadOnlyField(source='test_flow_used.test_flow_id')

    class Meta:
        model = AssessmentEvent
        fields = ['event_id', 'name', 'start_date_time', 'owning_company_id', 'test_flow_id']


class AssessmentEventParticipation(models.Model):
    assessment_event = models.ForeignKey('assessment.AssessmentEvent', on_delete=models.CASCADE)
    assessee = models.ForeignKey('users.Assessee', on_delete=models.CASCADE)
    assessor = models.ForeignKey('users.Assessor', on_delete=models.RESTRICT)
    attempt = models.OneToOneField('assessment.TestFlowAttempt', on_delete=models.CASCADE, null=True)


class TestFlowAttempt(models.Model):
    attempt_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    note = models.TextField(null=True)
    grade = models.FloatField(default=0)
    event_participation = models.ForeignKey('assessment.AssessmentEventParticipation', on_delete=models.CASCADE)
    test_flow_attempted = models.ForeignKey('assessment.TestFlow', on_delete=models.RESTRICT)
