from .assessment import get_assessor_or_company_or_raise_exception, get_assessor_or_raise_exception
from users.models import Assessor, Company
from assessment.models import AssessmentTool, AssessmentToolSerializer, TestFlow, TestFlowSerializer


def get_assessment_tool_by_company(user):
    # For now, this function can be utilised by the assessors
    assessor: Assessor = get_assessor_or_raise_exception(user)
    company: Company = assessor.associated_company
    list_of_assessment_tools = AssessmentTool.objects.filter(owning_company=company)
    return list_of_assessment_tools


def get_test_flow_by_company(user):
    found_user = get_assessor_or_company_or_raise_exception(user)
    if found_user.get("type") == "assessor":
        assessor: Assessor = found_user.get("user")
        company: Company = assessor.associated_company
    else:
        company: Company = found_user.get("user")
    list_of_test_flows = TestFlow.objects.filter(owning_company=company)
    return list_of_test_flows


def serialize_assignment_list_using_serializer(assignments):
    serialized_assignment_list = []
    for assignment in assignments:
        data = AssessmentToolSerializer(assignment).data
        data["type"] = type(assignment).__name__.lower()
        serialized_assignment_list.append(data)
    return serialized_assignment_list


def serialize_test_flow_list(test_flows):
    return [TestFlowSerializer(test_flow).data for test_flow in test_flows]
