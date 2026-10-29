from django.urls import path

from . import views_dentist as v
from . import views_export as e

app_name = "clinic"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("comecar/", v.onboarding, name="onboarding"),
    path("configuracoes/", v.settings_view, name="settings"),
    path("assinatura/", v.expired, name="expired"),
    path("pacientes/", v.patient_list, name="patient_list"),
    path("pacientes/convidar/", v.patient_create, name="patient_create"),
    path("pacientes/<int:pk>/", v.patient_detail, name="patient_detail"),
    path("pacientes/<int:pk>/editar/", v.patient_edit, name="patient_edit"),
    path("pacientes/<int:pk>/remover/", v.patient_delete, name="patient_delete"),
    path("pacientes/<int:pk>/reenviar-convite/", v.patient_reinvite, name="patient_reinvite"),
    path("pacientes/<int:pk>/dados.zip", v.patient_data_zip, name="patient_data_zip"),
    path("tratamentos/", v.treatment_list, name="treatment_list"),
    path("tratamentos/novo/", v.treatment_create, name="treatment_create"),
    path("tratamentos/<int:pk>/", v.treatment_detail, name="treatment_detail"),
    path("tratamentos/<int:pk>/editar/", v.treatment_edit, name="treatment_edit"),
    path("tratamentos/<int:pk>/status/", v.treatment_status, name="treatment_status"),
    path("tratamentos/<int:pk>/mensagem/", v.treatment_message, name="treatment_message"),
    path("tratamentos/<int:pk>/arquivos/enviar/", v.treatment_upload, name="treatment_upload"),
    path("tratamentos/<int:pk>/fase/<str:phase>/compartilhar/", v.phase_share, name="phase_share"),
    path("tratamentos/<int:pk>/remover/", v.treatment_delete, name="treatment_delete"),
    path("tratamentos/<int:pk>/faturas/nova/", v.invoice_create, name="invoice_create"),
    path("arquivos/<int:pk>/compartilhar/", v.file_share, name="file_share"),
    path("arquivos/<int:pk>/remover/", v.file_delete, name="file_delete"),
    path("faturas/", v.invoice_list, name="invoice_list"),
    path("faturas/<int:pk>/", v.invoice_detail, name="invoice_detail"),
    path("faturas/<int:pk>/<str:action>/", v.invoice_action, name="invoice_action"),
    path("exportar/", e.exports, name="exports"),
    path("exportar/backup.zip", e.export_backup, name="export_backup"),
    path("exportar/<str:what>.<str:fmt>", e.export, name="export"),
]
