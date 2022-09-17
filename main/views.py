from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view


@api_view(['GET'])
def test_end_point(request):
    return Response(data={
        'message': 'Hello, World!'
    })
