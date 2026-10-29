from django.urls import path

from . import views_dentist as v

app_name = "agenda"

urlpatterns = [
    path("configuracoes/agenda/", v.agenda_settings, name="settings"),
    path("agenda/", v.calendar, name="calendar"),
    path("agenda/nova/", v.create, name="create"),
    path("agenda/bloqueios/", v.blocks, name="blocks"),
    path("agenda/bloqueios/<int:pk>/remover/", v.block_delete, name="block_delete"),
    path("agenda/exportar/", v.export, name="export"),
    path("agenda/sincronizar/", v.sync, name="sync"),
    path("agenda/sincronizar/novo-link/", v.sync_rotate, name="sync_rotate"),
    path("agenda/<int:pk>/", v.detail, name="detail"),
    path("agenda/<int:pk>/remarcar/", v.reschedule, name="reschedule"),
    path("agenda/<int:pk>/<str:action>/", v.action, name="action"),
]
