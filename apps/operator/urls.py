from django.urls import path

from . import views

app_name = "operator"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dentistas/", views.dentist_list, name="dentist_list"),
    path("dentistas/novo/", views.dentist_add, name="dentist_add"),
    path("dentistas/<int:pk>/", views.dentist_edit, name="dentist_edit"),
    path("dentistas/<int:pk>/liberar/", views.dentist_extend, name="dentist_extend"),
    path("dentistas/<int:pk>/suspender/", views.dentist_suspend, name="dentist_suspend"),
    path("dentistas/<int:pk>/apagar/", views.dentist_delete, name="dentist_delete"),
    path("interessados/", views.platform_leads, name="platform_leads"),
    path("configuracoes/", views.settings_view, name="settings"),
    path("atividade/", views.activity_view, name="activity"),
    path("atividade/baixar/", views.activity_download, name="activity_download"),
    path("dados/", views.data, name="data"),
    path("dados/importar/", views.data_import, name="data_import"),
    path("dados/importar/confirmar/", views.data_import_confirm, name="data_import_confirm"),
    path("dados/importar/cancelar/", views.data_import_cancel, name="data_import_cancel"),
]
