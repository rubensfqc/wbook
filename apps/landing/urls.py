from django.urls import path

from . import views

app_name = "landing"

urlpatterns = [
    path("", views.lead_list, name="lead_list"),
    path("novo/", views.lead_create, name="lead_create"),
    path("exportar.csv", views.lead_export, name="lead_export"),
    path("minha-pagina/", views.editor, name="editor"),
    path("minha-pagina/galeria/", views.gallery_add, name="gallery_add"),
    path("minha-pagina/galeria/<int:pk>/remover/", views.gallery_delete, name="gallery_delete"),
    path("<int:pk>/", views.lead_detail, name="lead_detail"),
    path("<int:pk>/remover/", views.lead_delete, name="lead_delete"),
]
