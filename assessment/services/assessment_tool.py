from assessment.services.assessment import get_assessor_or_raise_exception
from users.models import Assessor, Company
from assessment.models import AssessmentTool, AssessmentToolSerializer


def get_assessment_tool_by_company(user) -> list:
    # For now, this function can be utilised by the assessors
    assessor: Assessor = get_assessor_or_raise_exception(user)
    company: Company = assessor.associated_company
    list_of_assessment_tools = AssessmentTool.objects.filter(owning_company=company)
    return list_of_assessment_tools


def serialize_assignment_list_using_serializer(assignments):
    serialized_assignment_list = []
    for assignment in assignments:
        data = AssessmentToolSerializer(assignment).data
        data["type"] = type(assignment).__name__.lower()
        serialized_assignment_list.append(data)
    return serialized_assignment_list