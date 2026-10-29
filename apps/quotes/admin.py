from django.contrib import admin

from .models import Quote, QuoteEvent, QuoteItem, QuoteVisit

admin.site.register([Quote, QuoteItem, QuoteVisit, QuoteEvent])
