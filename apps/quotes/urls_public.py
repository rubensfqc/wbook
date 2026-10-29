from django.urls import path

from . import views

app_name = "quote_public"

urlpatterns = [
    path("<uuid:uuid>/", views.public_page, name="page"),
    path("<uuid:uuid>/pdf/", views.public_pdf, name="pdf"),
    path("<uuid:uuid>/beacon/", views.beacon, name="beacon"),
    path("<uuid:uuid>/evento/", views.event, name="event"),
    path("<uuid:uuid>/responder/", views.respond, name="respond"),
]
