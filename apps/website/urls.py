from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("planos/", views.plans, name="plans"),
    path("contato/", views.contact, name="contact"),
    path("obrigado/", views.thanks, name="thanks"),
    path("termos/", views.terms, name="terms"),
    path("privacidade/", views.privacy, name="privacy"),
]
