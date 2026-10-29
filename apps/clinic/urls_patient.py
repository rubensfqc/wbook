from django.urls import path

from . import views_patient as v

app_name = "patient"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("agendar/", v.book, name="book"),
    path("agendar/horarios/", v.book_times, name="book_times"),
    path("agendar/confirmar/", v.book_confirm, name="book_confirm"),
    path("consultas/", v.appointments, name="appointments"),
    path("consultas.ics", v.appointments_ics, name="appointments_ics"),
    path("consultas/<int:pk>/", v.appointment, name="appointment"),
    path("consultas/<int:pk>.ics", v.appointment_ics, name="appointment_ics"),
    path("consultas/<int:pk>/cancelar/", v.appointment_cancel, name="appointment_cancel"),
    path("consultas/<int:pk>/cancelar-tarde/", v.appointment_late_cancel, name="late_cancel"),
    path("tratamentos/<int:pk>/", v.treatment, name="treatment"),
    path("tratamentos/<int:pk>/mensagem/", v.treatment_message, name="treatment_message"),
    path("faturas/<int:pk>/", v.invoice, name="invoice"),
    path("faturas/<int:pk>/ja-paguei/", v.invoice_paid, name="invoice_paid"),
    path("meus-dados/", v.my_data, name="my_data"),
    path("configuracoes/", v.settings_view, name="settings"),
]
