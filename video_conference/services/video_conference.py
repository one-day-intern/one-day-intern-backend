from assessment.services.assessment import get_assessor_or_raise_exception
from assessment.services.utils import get_assessee_from_email
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from assessment.models import AssessmentEvent, AssessmentEventParticipation, VideoConferenceRoom, VideoConferenceRoomSerializer
import requests
from users.models import OdiUser
from .utils import generate_join_room_token, generate_management_token, get_assessor_from_email, get_video_conference_from_request_as_assessor


def initiate_video_conference_room(request_data, user):
    video_conference_room: VideoConferenceRoom = get_video_conference_from_request_as_assessor(
        request_data, user)
    initiate = request_data.get("initiate")
    purge = request_data.get("purge")
    if not isinstance(initiate, bool):
        raise InvalidRequestException("Invalid initiate value in request body")
    if purge and not isinstance(purge, bool):
        raise InvalidRequestException("Invalid purge value in request body")
    video_conference_room.room_opened = initiate
    if video_conference_room.room_id:
        if purge and not initiate:
            purge_video_conference_room(video_conference_room.room_id)
        video_conference_room.save()
        return video_conference_room
    room_id = create_video_conference_room()
    video_conference_room.room_id = room_id
    video_conference_room.save()
    return video_conference_room


def lock_conference_room_by_id(request_data, user: OdiUser):
    room_id = request_data.get("room_id")
    if not isinstance(room_id, str):
        raise InvalidRequestException("Invalid room id value in request body")
    conference_room = VideoConferenceRoom.objects.filter(room_id=room_id)
    if not conference_room:
        raise InvalidRequestException(f"Video Conference room with id {room_id} was not found")
    conference_room: VideoConferenceRoom = conference_room[0]
    conference_host = conference_room.part_of.assessor
    assessor = get_assessor_or_raise_exception(user)
    if conference_host != assessor:
        return RestrictedAccessException(f"{user.email} is not the host of this conference room")
    conference_room.room_opened = False
    conference_room.save()
    return conference_room


def get_all_video_conference_room_hosts(request_data, user: OdiUser):
    assessment_event_id = request_data.get("assessment_event_id")
    assessment_event = AssessmentEvent.objects.filter(
        event_id=assessment_event_id)
    if not assessment_event:
        raise InvalidRequestException(
            f"Assessment event with id {assessment_event_id} does not exist")
    assessor = get_assessor_or_raise_exception(user)
    assessment_event_participations = AssessmentEventParticipation.objects.filter(
        assessment_event=assessment_event[0], assessor=assessor).all()
    conference_rooms = []
    for participation in assessment_event_participations:
        room = VideoConferenceRoom.objects.get(part_of=participation)
        serialized_room = VideoConferenceRoomSerializer(room).data
        conference_rooms.append(serialized_room)
    return conference_rooms


def get_all_video_conference_room_roleplayers(request_data, user: OdiUser):
    assessment_event_id = request_data.get("assessment_event_id")
    assessment_event = AssessmentEvent.objects.filter(
        event_id=assessment_event_id)
    if not assessment_event:
        raise InvalidRequestException(
            f"Assessment event with id {assessment_event_id} does not exist")
    assessor = get_assessor_or_raise_exception(user)
    assessment_event_participations = AssessmentEventParticipation.objects.filter(
        assessment_event=assessment_event[0]).all()
    rooms_roleplaying_in = [room for room in VideoConferenceRoom.objects.filter(
        part_of__in=assessment_event_participations).all() if room.conference_participants.contains(assessor)]
    conference_rooms = []
    for room in rooms_roleplaying_in:
        serialized_room = VideoConferenceRoomSerializer(room).data
        del serialized_room["conference_participants"]
        conference_rooms.append(serialized_room)
    return conference_rooms


def get_conference_room_by_participation(request_data, user: OdiUser):
    assessment_event_id = request_data.get("assessment_event_id")
    assessee_email = request_data.get("conference_assessee_email")
    if not isinstance(assessment_event_id, str):
        raise InvalidRequestException(
            "Invalid assessment event id value in request body")
    if not isinstance(assessee_email, str):
        raise InvalidRequestException(
            "Invalid conference assessee email value in request body")
    assessment_event = AssessmentEvent.objects.filter(event_id=assessment_event_id)
    if not assessment_event:
        raise InvalidRequestException(
            f"Assessment event with id {assessment_event_id} does not exist")
    assessment_event = assessment_event[0]
    assessee = get_assessee_from_email(assessee_email)
    assessor = get_assessor_or_raise_exception(user)
    assessment_event_participation = AssessmentEventParticipation.objects.filter(assessment_event=assessment_event, assessee=assessee, assessor=assessor)
    if not assessment_event_participation:
        raise RestrictedAccessException(
            f"Asessor {user.email} is not the host of this conference room")
    video_conference_room = VideoConferenceRoom.objects.get(part_of=assessment_event_participation)
    return video_conference_room


def add_roleplayer_to_video_conference_room(request_data, user):
    video_conference_room: VideoConferenceRoom = get_video_conference_from_request_as_assessor(
        request_data, user)
    roleplayer_emails = request_data.get("roleplayers")
    if not isinstance(roleplayer_emails, list):
        raise InvalidRequestException(
            "Invalid roleplayer emails value in request body")
    assessors = [get_assessor_from_email(email) for email in roleplayer_emails]
    for assessor in assessors:
        video_conference_room.conference_participants.add(assessor)
    video_conference_room.save()
    return video_conference_room


def join_conference_room_as_assessee(request_data, user: OdiUser):
    assessment_event_id = request_data.get("assessment_event_id")
    assessment_event = AssessmentEvent.objects.filter(
        event_id=assessment_event_id)
    if not assessment_event:
        raise InvalidRequestException(
            f"Assessment event with id {assessment_event_id} does not exist")
    assessee = get_assessee_from_email(user.email)
    assessment_event_participation = AssessmentEventParticipation.objects.filter(
        assessment_event=assessment_event[0], assessee=assessee)
    if not assessment_event_participation:
        raise InvalidRequestException(
            f"Assessee {assessee.email} is not participating in assessment event {assessment_event_id}")
    conference_room = VideoConferenceRoom.objects.get(
        part_of=assessment_event_participation[0])
    if not conference_room.room_opened or not conference_room.room_id:
        raise RestrictedAccessException(
            f"Video conference room is closed"
        )
    room_token = generate_join_room_token(
        user.get_full_name(), conference_room.room_id, "waiting-room")
    return room_token


def join_conference_room_as_assessor(request_data, user: OdiUser):
    room_id = request_data.get("room_id")
    conference_room = VideoConferenceRoom.objects.filter(room_id=room_id)
    assessor = get_assessor_or_raise_exception(user)
    if not conference_room:
        raise InvalidRequestException(
            f"Video Conference Room with room id {room_id} does not exist")
    conference_room = conference_room[0]
    if not conference_room.room_opened:
        raise RestrictedAccessException(
            f"Video conference room is closed"
        )
    role = "participant"
    user_is_host = conference_room.part_of.assessor == assessor
    user_is_roleplayer = conference_room.conference_participants.contains(assessor)
    if user_is_host or user_is_roleplayer:
        if user_is_host:
            role = "host"
        room_token = generate_join_room_token(user.get_full_name(), conference_room.room_id, role)
        return room_token
    raise RestrictedAccessException(f"Assessor with email {user.email} does not have access to this conference room")

def purge_video_conference_room(room_id):
    management_token = generate_management_token()
    request_headers = {"Authorization": f"Bearer {management_token}"}
    response = requests.post(f"https://api.100ms.live/v2/active-rooms/{room_id}/end-room", json={
                             "reason": "Room ended by host"}, headers=request_headers)
    if response.status_code == 500:
        raise InvalidRequestException(
            "There was a problem in locking your video conference room")


def create_video_conference_room() -> VideoConferenceRoom:
    management_token = generate_management_token()
    request_headers = {"Authorization": f"Bearer {management_token}"}
    response = requests.post(
        "https://api.100ms.live/v2/rooms", json={}, headers=request_headers)
    if not response.ok:
        raise InvalidRequestException(
            "There was a problem in creating your video conference room")
    response_data = response.json()
    room_id = response_data.get("id")
    return room_id
