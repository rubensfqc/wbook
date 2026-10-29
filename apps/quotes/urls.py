from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.quote_list, name="list"),
    path("novo/", views.quote_create, name="create"),
    path("<int:pk>/", views.quote_detail, name="detail"),
    path("<int:pk>/editar/", views.quote_edit, name="edit"),
    path("<int:pk>/enviar/", views.quote_send, name="send"),
    path("<int:pk>/link/", views.quote_link, name="link"),
    path("<int:pk>/duplicar/", views.quote_duplicate, name="duplicate"),
    path("<int:pk>/tratamento/", views.quote_to_treatment, name="create_treatment"),
    path("<int:pk>/remover/", views.quote_delete, name="delete"),
]
