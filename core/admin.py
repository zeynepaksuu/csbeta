from django.contrib import admin
from core.models import AgentSettings, ChatSession, Company, TaskResult


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "sector", "email", "is_active", "updated_at")
    list_filter = ("is_active", "sector")
    search_fields = ("name", "sector", "description")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "company", "created_at", "updated_at")
    list_filter = ("company",)
    search_fields = ("title",)


@admin.register(TaskResult)
class TaskResultAdmin(admin.ModelAdmin):
    list_display = ("task_id", "company", "session", "status", "created_at", "completed_at")
    list_filter = ("status", "company")
    search_fields = ("task_id", "prompt", "result")
    readonly_fields = ("created_at", "completed_at")


@admin.register(AgentSettings)
class AgentSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not AgentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
