from django.urls import path

from . import views_files as v

app_name = "files"

urlpatterns = [
    path("documento/<int:pk>/", v.document, name="document"),
    path("foto/<int:pk>/", v.photo, name="photo"),
    path("fatura/<int:pk>/", v.invoice, name="invoice"),
    path("orcamento/<int:pk>/", v.quote_attachment, name="quote_attachment"),
]
