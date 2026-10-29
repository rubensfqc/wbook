"""ORDER MATTERS: dentist public pages (/<slug>/...) are the LAST patterns. New top-level segments go above them
and into apps/core/slugs.RESERVED_SLUGS."""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.agenda import views_public as agenda_public
from apps.core.views import set_language
from apps.website.views import SITEMAPS, favicon, robots

feed_patterns = ([path("<uuid:token>.ics", agenda_public.feed, name="feed")], "agenda_feed")

app_patterns = [
    path("", include("apps.clinic.urls_dentist")),
    path("", include("apps.agenda.urls")),
    path("leads/", include("apps.landing.urls")),
    path("orcamentos/", include("apps.quotes.urls")),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("idioma/", set_language, name="set_language"),
    path("robots.txt", robots),
    path("favicon.ico", favicon),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("conta/", include("apps.accounts.urls")),
    path("app/", include(app_patterns)),
    path("paciente/", include("apps.clinic.urls_patient")),
    path("arquivos/", include("apps.clinic.urls_files")),
    path("operador/", include("apps.operator.urls")),
    path("calendario/", include(feed_patterns)),
    path("", include("apps.website.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static("/media/logos/", document_root=settings.MEDIA_ROOT / "logos")
    urlpatterns += static("/media/dentists/", document_root=settings.MEDIA_ROOT / "dentists")
    urlpatterns += static("/media/landing/", document_root=settings.MEDIA_ROOT / "landing")

# dentist public pages — keep LAST
urlpatterns += [
    path("<slug:slug>/orcamento/", include("apps.quotes.urls_public")),
    path("<slug:slug>/", include("apps.agenda.urls_public")),
    path("<slug:slug>/", include("apps.landing.urls_public")),
]
