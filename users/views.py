from rest_framework.response import Response
from rest_framework.decorators import api_view


@api_view(['POST'])
def serve_register_company(request):
    return Response(data={})
