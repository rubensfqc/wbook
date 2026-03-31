from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Seller


@admin.register(Seller)
class SellerAdmin(UserAdmin):
    list_display  = ('email', 'name', 'role', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active')
    search_fields = ('email', 'name', 'username')
    ordering      = ('-date_joined',)

    fieldsets = (
        (None,               {'fields': ('username', 'password')}),
        ('Informações pessoais', {'fields': ('name', 'email', 'phone_number', 'address', 'profile_picture', 'slug')}),
        ('wbook365',         {'fields': ('role',)}),
        ('Permissões',       {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas importantes',{'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('username', 'email', 'name', 'role', 'password1', 'password2'),
        }),
    )