from django.urls import path

from . import views_public as v

app_name = "booking_public"

urlpatterns = [
    path("horarios/", v.times, name="times"),
    path("agendar/", v.request_view, name="request"),
    path("agendar/obrigado/<uuid:token>/", v.thanks, name="thanks"),
    path("consulta/<uuid:token>/", v.status, name="status"),
    path("consulta/<uuid:token>/cancelar/", v.cancel, name="cancel"),
    path("consulta/<uuid:token>/cancelar-tarde/", v.late_cancel, name="late_cancel"),
    path("consulta/<uuid:token>.ics", v.ics_view, name="ics"),
]
