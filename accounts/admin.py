from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Seller


@admin.register(Seller)
class SellerAdmin(UserAdmin):
    list_display  = ('email', 'name', 'role', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active')
    search_fields = ('email', 'name', 'username')
    ordering      = ('-date_joined',)

    fieldsets = UserAdmin.fieldsets + (
        ('wbook365', {'fields': ('role', 'name', 'phone_number', 'address', 'profile_picture', 'slug')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('wbook365', {'fields': ('role', 'name', 'email')}),
    )
