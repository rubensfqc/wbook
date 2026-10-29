from django.contrib import admin

from .models import GalleryImage, LandingPage, Lead

admin.site.register([LandingPage, GalleryImage, Lead])
