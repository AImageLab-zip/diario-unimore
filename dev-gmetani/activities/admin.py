from django.contrib import admin
from .models import AcademicActivity, GoogleCalendarCredential


@admin.register(AcademicActivity)
class AcademicActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'start_time', 'duration_minutes', 'category', 'sync_status')
    list_filter = ('sync_status', 'category', 'user')
    search_fields = ('title', 'description')


@admin.register(GoogleCalendarCredential)
class GoogleCalendarCredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    readonly_fields = ('refresh_token', 'token', 'client_secret')