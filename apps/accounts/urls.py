from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),
    path("entrar/", views.LoginView.as_view(), name="login"),
    path("sair/", views.logout_view, name="logout"),
    path("cadastro/", views.register, name="register"),
    path("verifique-seu-email/", views.verify_email_sent, name="verify_email_sent"),
    path("reenviar-verificacao/", views.resend_verification, name="resend_verification"),
    path("verificar/<str:uidb64>/<str:token>/", views.verify_email, name="verify_email"),
    path("definir-senha/<str:uidb64>/<str:token>/", views.set_password, name="set_password"),
    path("esqueci-a-senha/", views.PasswordResetView.as_view(), name="password_reset"),
    path("esqueci-a-senha/enviado/", views.password_reset_done, name="password_reset_done"),
    path("alterar-senha/", views.change_password, name="change_password"),
    path("consentimento/", views.consent, name="consent"),
]
