import json
from django.views.decorators.http import require_POST, require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from assessment.models import VideoConferenceRoomSerializer

from video_conference.services.video_conference import initiate_video_conference_room, get_all_video_conference_room_hosts, get_all_video_conference_room_roleplayers, add_roleplayer_to_video_conference_room, join_conference_room_as_assessee, join_conference_room_as_assessor, lock_conference_room_by_id


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_initiate_video_conference_room(request):
    """
    this view will create a video conference room
    if the room does not exist yet, if it does 
    exist it will respect the initiate property 
    send in the request body
    ---------------------------------------------
    request data must contain:
    assessment_event_id: string,
    conference_assessee_email: string,
    initiate: boolean,
    purge: boolean (OPTIONAL)
    """
    user = request.user
    request_data = json.loads(request.body.decode("utf-8"))
    conference_room = initiate_video_conference_room(request_data, user)
    response_data = VideoConferenceRoomSerializer(conference_room).data
    return Response(data=response_data)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_video_conference_room_hosts(request):
    """
    this view will return all the room objects for 
    hosts of the conference for a particular assessment 
    event
    ----------------------------------------------------------
    request params must contain:
    assessment_event_id: string,
    """
    user = request.user
    request_data = request.GET
    rooms = get_all_video_conference_room_hosts(request_data, user)
    response_data = rooms
    return Response(data=response_data)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_video_conference_room_roleplayers(request):
    """
    this view will return all the room objects for roleplayers 
    of the conference for a particular assessment event
    ----------------------------------------------------------
    request params must contain:
    assessment_event_id: string,
    """
    user = request.user
    request_data = request.GET
    rooms = get_all_video_conference_room_roleplayers(request_data, user)
    response_data = rooms
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_add_roleplayers_to_conference_room(request):
    """
    this view will add a list of roleplayers to a
    conference room
    --------------------------------------------------
    request data must contain:
    assessment_event_id: string,
    conference_assessee_email: string,
    roleplayers: string[]
    """
    user = request.user
    request_data = json.loads(request.body.decode('utf-8'))
    response = add_roleplayer_to_video_conference_room(request_data, user)
    response_data = VideoConferenceRoomSerializer(response).data
    return Response(data=response_data)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_join_conference_room_as_assessee(request):
    """
    this view will return a join room token for an 
    assessee in particular assessment_event
    ------------------------------------------------
    request params must contain:
    assessment_event_id: string,
    """
    user = request.user
    request_data = request.GET
    room_token = join_conference_room_as_assessee(request_data, user)
    response_data = { "token": room_token }
    return Response(data=response_data)
    

@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_join_conference_room_as_assessor(request):
    """
    this view will return a join room token for an 
    assessor in particular assessment_event
    ------------------------------------------------
    request params must contain:
    room_id: string,
    """
    user = request.user
    request_data = request.GET
    room_token = join_conference_room_as_assessor(request_data, user)
    response_data = { "token": room_token }
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_lock_conference_room_by_id(request):
    """
    this view will lock the room based on the
    room id provided. (host only)
    -----------------------------------------
    request params must contain:
    room_id: string,
    """
    user = request.user
    request_data = json.loads(request.body.decode('utf-8'))
    response = lock_conference_room_by_id(request_data, user)
    response_data = VideoConferenceRoomSerializer(response).data
    return Response(data=response_data)