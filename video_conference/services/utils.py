import datetime
import jwt
import uuid
import os
from assessment.models import AssessmentEventParticipation, VideoConferenceRoom
from assessment.services.assessment import get_assessor_or_raise_exception
from assessment.services.utils import get_active_assessment_event_from_id, get_assessee_from_email
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from users.models import Assessee, Assessor
from django.core.exceptions import ObjectDoesNotExist


def generate_management_token():
    expires = 24 * 3600  # 30 minutes
    now = datetime.datetime.utcnow()
    exp = now + datetime.timedelta(seconds=expires)
    return jwt.encode(payload={
        'access_key': os.getenv("VIDEO_CONFERENCE_APP_ACCESS_KEY"),
        'type': 'management',
        'version': 2,
        'jti': str(uuid.uuid4()),
        'iat': now,
        'exp': exp,
        'nbf': now
    }, key=os.getenv("VIDEO_CONFERENCE_APP_SECRET"))


def generate_join_room_token(user_id, room_id, role):
    expires = 24 * 3600
    now = datetime.datetime.utcnow()
    exp = now + datetime.timedelta(seconds=expires)
    return jwt.encode(payload={
        "access_key": os.getenv("VIDEO_CONFERENCE_APP_ACCESS_KEY"),
        "type": "app",
                "version": 2,
                "room_id": room_id,
                "user_id": user_id,
                "role": role,
                "jti": str(uuid.uuid4()),
                "exp": exp,
                "iat": now,
                "nbf": now,
    }, key=os.getenv("VIDEO_CONFERENCE_APP_SECRET"))


def get_assessor_from_email(email):
    try:
        return Assessor.objects.get(email=email)
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f'Assessor with email {email} not found')


def get_video_conference_from_request_as_assessor(request_data, user):
    assessment_event_id = request_data.get("assessment_event_id")
    conference_assessee_email = request_data.get("conference_assessee_email")

    if type(assessment_event_id) != str:
        raise InvalidRequestException("Invalid assessment event id value in request body")
    if type(conference_assessee_email) != str:
        raise InvalidRequestException("Invalid conference assessee email value in request body")

    assessee: Assessee = get_assessee_from_email(conference_assessee_email)
    assessor: Assessor = get_assessor_or_raise_exception(user)
    assessment_event = get_active_assessment_event_from_id(assessment_event_id)
    assessment_event_participation = AssessmentEventParticipation.objects.filter(assessment_event=assessment_event, assessee=assessee, assessor=assessor)
    if not assessment_event_participation:
        raise RestrictedAccessException(f"{assessor.email} is not the host for conference room with assessee {assessee.email}")

    assessment_event_participation = assessment_event_participation[0]
    video_conference_room: VideoConferenceRoom = VideoConferenceRoom.find_by_assessment_event_participation(assessment_event_participation)

    if not video_conference_room:
        raise InvalidRequestException(f"Video conference room not found")

    return video_conference_room[0]    