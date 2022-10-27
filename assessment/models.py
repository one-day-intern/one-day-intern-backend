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
