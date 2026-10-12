from django.urls import path
from core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("companies/", views.company_list, name="company_list"),
    path("companies/new/", views.company_form, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_form, name="company_edit"),
    path("companies/<int:pk>/delete/", views.company_delete, name="company_delete"),
    path("companies/<int:pk>/prompt/", views.company_prompt, name="company_prompt"),
    path("settings/agent/", views.agent_settings, name="agent_settings"),
    path("settings/agent/reset/", views.agent_settings_reset, name="agent_settings_reset"),
    path("settings/agent/preview/", views.agent_settings_preview, name="agent_settings_preview"),
    path("settings/agent/company/", views.agent_settings_company, name="agent_settings_company"),
    path("chat/", views.chat, name="chat"),
    path("chat/<int:session_id>/", views.chat, name="chat_session"),
    path("chat/<int:session_id>/delete/", views.chat_session_delete, name="chat_session_delete"),
    path("chat/sessions/", views.chat_sessions, name="chat_sessions"),
    path("tasks/", views.task_create, name="task_create"),
    path("tasks/<str:task_id>/", views.task_status, name="task_status"),
    path("tasks/<str:task_id>/detail/", views.task_detail, name="task_detail"),
    path("partials/jobs/", views.jobs_partial, name="jobs_partial"),
]
