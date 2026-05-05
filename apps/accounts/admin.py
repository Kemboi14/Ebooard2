from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import UserCreationForm
from .models import User, Language, Translation

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'mfa_enabled', 'date_joined']
    list_filter = ['role', 'is_active', 'mfa_enabled', 'department']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']

    # Fields shown when editing an existing user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'profile_photo')}),
        ('Professional info', {'fields': ('role', 'department', 'job_title')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    # Fields shown on the "Add User" page — uses email instead of username
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2', 'is_active'),
        }),
    )


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'native_name', 'code', 'locale_code', 'direction', 'status']
    list_filter = ['status', 'direction']
    search_fields = ['name', 'native_name', 'code']
    ordering = ['name']


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ['key', 'module', 'context', 'get_translation_count']
    list_filter = ['module', 'context']
    search_fields = ['key', 'module', 'context']
    ordering = ['key']
    
    def get_translation_count(self, obj):
        return len(obj.translations)
    get_translation_count.short_description = 'Languages'
