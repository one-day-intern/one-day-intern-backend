from django.urls import path
from .views import serve_add_roleplayers_to_conference_room, serve_get_conference_room_by_participation, serve_initiate_video_conference_room, serve_get_all_video_conference_room_hosts, serve_get_all_video_conference_room_roleplayers, serve_join_conference_room_as_assessee, serve_join_conference_room_as_assessor, serve_lock_conference_room_by_id

urlpatterns = [
    path("rooms/initiate/", serve_initiate_video_conference_room, name="initiate-room"),
    path("rooms/add-roleplayers/", serve_add_roleplayers_to_conference_room, name="add-room-roleplayers"),
    path("rooms/get/hosting/", serve_get_all_video_conference_room_hosts, name="get-rooms-as-host"),
    path("rooms/get/roleplaying/", serve_get_all_video_conference_room_roleplayers, name="get-rooms-as-roleplayer"),
    path("rooms/join/assessee/", serve_join_conference_room_as_assessee, name="join-as-assessee"),
    path("rooms/join/assessor/", serve_join_conference_room_as_assessor, name="join-as-assessor"),
    path("rooms/lock/", serve_lock_conference_room_by_id, name="lock-room"),
    path("rooms/get/by-participation", serve_get_conference_room_by_participation, name="get-room-by-participation")
]