from django.urls import path

from . import views

app_name = "landing_public"

urlpatterns = [
    path("", views.public_page, name="page"),
    path("contato/", views.contact, name="contact"),
    path("login/", views.branded_login, name="login"),
]
