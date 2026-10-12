import json
import uuid
from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from procrastinate.contrib.django.models import ProcrastinateJob
from core.centrifugo import publish_event_sync
from core.forms import AgentSettingsForm, CompanyForm, CompanyPromptForm
from core.models import AgentSettings, ChatSession, Company, TaskResult
from core.prompts import build_system_prompt, render_system_prompt
from core.tasks import process_agent_task


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def htmx_trigger(response, **events):
    response["HX-Trigger"] = json.dumps(events)
    return response


def dashboard(request):
    status_counts = {
        row["status"]: row["count"]
        for row in TaskResult.objects.order_by().values("status").annotate(count=Count("pk"))
    }
    context = {
        "company_count": Company.objects.count(),
        "active_company_count": Company.objects.filter(is_active=True).count(),
        "task_count": TaskResult.objects.count(),
        "status_counts": status_counts,
        "recent_tasks": TaskResult.objects.select_related("company")[:8],
        "top_companies": Company.objects.annotate(task_total=Count("tasks")).order_by("-task_total")[:5],
    }
    return render(request, "core/dashboard.html", context)


def company_list(request):
    query = request.GET.get("q", "").strip()
    companies = Company.objects.annotate(task_total=Count("tasks"))
    if query:
        companies = companies.filter(
            Q(name__icontains=query) | Q(sector__icontains=query) | Q(email__icontains=query)
        )
    template = "core/companies/_rows.html" if is_htmx(request) else "core/companies/list.html"
    return render(request, template, {"companies": companies, "query": query})


def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    return render(request, "core/companies/detail.html", {
        "company": company,
        "tasks": company.tasks.all()[:10],
        "full_system_prompt": build_system_prompt(company),
    })


def company_form(request, pk=None):
    company = get_object_or_404(Company, pk=pk) if pk else None
    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        message = f"{saved.name} güncellendi" if company else f"{saved.name} eklendi"
        return htmx_trigger(HttpResponse(""), companiesChanged=True, toast=message)
    return render(request, "core/companies/_form.html", {"form": form, "company": company})


@require_POST
def company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk)
    name = company.name
    company.delete()
    response = HttpResponse("")
    if request.GET.get("redirect"):
        response["HX-Redirect"] = reverse("core:company_list")
        return response
    return htmx_trigger(response, toast=f"{name} silindi")


def company_prompt(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == "GET" and not request.GET.get("edit"):
        return render(request, "core/companies/_prompt_card.html", {
            "company": company, "full_system_prompt": build_system_prompt(company),
        })

    form = CompanyPromptForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        response = render(request, "core/companies/_prompt_card.html", {
            "company": company, "full_system_prompt": build_system_prompt(company),
        })
        return htmx_trigger(response, toast="Firma talimatları kaydedildi")
    return render(request, "core/companies/_prompt_form.html", {"company": company, "form": form})


def agent_settings(request):
    settings_obj = AgentSettings.load()
    form = AgentSettingsForm(request.POST or None, instance=settings_obj)
    saved = request.method == "POST" and form.is_valid()
    if saved:
        form.save()
    context = {"form": form, "companies": Company.objects.all(), "selected": request.GET.get("company", "")}
    if not is_htmx(request):
        return render(request, "core/agent_settings.html", context)
    response = render(request, "core/agent_settings/_form.html", context)
    return htmx_trigger(response, toast="Agent ayarları kaydedildi") if saved else response


@require_POST
def agent_settings_reset(request):
    settings_obj = AgentSettings.load()
    settings_obj.system_prompt = AgentSettings._meta.get_field("system_prompt").default
    settings_obj.save()
    form = AgentSettingsForm(instance=settings_obj)
    response = render(request, "core/agent_settings/_form.html", {"form": form, "companies": Company.objects.all()})
    response["HX-Trigger-After-Swap"] = "previewRefresh"
    return htmx_trigger(response, toast="Varsayılana döndürüldü")


def agent_settings_company(request):
    company_id = request.POST.get("preview_company") or request.GET.get("preview_company") or None
    company = Company.objects.filter(pk=company_id).first()
    form = CompanyPromptForm(request.POST or None, instance=company) if company else None
    saved = request.method == "POST" and form is not None and form.is_valid()
    if saved:
        form.save()
    response = render(request, "core/agent_settings/_company_instructions.html", {"company": company, "form": form})
    # Önizleme, talimat alanı yerine oturduktan sonra yenilensin.
    response["HX-Trigger-After-Swap"] = "previewRefresh"
    return htmx_trigger(response, toast=f"{company.name} talimatları kaydedildi") if saved else response


@require_POST
def agent_settings_preview(request):
    company = Company.objects.filter(pk=request.POST.get("preview_company") or None).first()
    if company is not None and "system_prompt" in request.POST:
        company.system_prompt = request.POST["system_prompt"]
    preview = render_system_prompt(request.POST.get("agent-system_prompt", ""), company)
    return render(request, "core/agent_settings/_preview.html", {"preview": preview, "company": company})


def recent_sessions(limit=50):
    # GROUP BY sorgularında Meta.ordering uygulanmıyor, sıralamayı açıkça ver.
    sessions = ChatSession.objects.select_related("company").annotate(message_count=Count("tasks"))
    return sessions.order_by("-updated_at")[:limit]


def chat(request, session_id=None):
    session = None
    if session_id is not None:
        session = get_object_or_404(ChatSession.objects.select_related("company"), pk=session_id)
    return render(request, "core/chat.html", {
        "session": session,
        "history": session.tasks.select_related("company").order_by("created_at") if session else [],
        "sessions": recent_sessions(),
        "companies": Company.objects.filter(is_active=True),
        "selected": request.GET.get("company", ""),
        "centrifugo_ws_url": settings.CENTRIFUGO_WS_URL,
    })


def chat_sessions(request):
    sessions = recent_sessions()
    return render(request, "core/chat/_sessions.html", {"sessions": sessions})


@require_POST
def chat_session_delete(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id)
    session.delete()
    response = HttpResponse("")
    if request.POST.get("session") == str(session_id):
        response["HX-Redirect"] = reverse("core:chat")
        return response
    return htmx_trigger(response, sessionsChanged=True, toast="Sohbet silindi")


@require_POST
def task_create(request):
    prompt = request.POST.get("prompt", "").strip()
    if not prompt:
        return HttpResponse(status=204)

    session_id = request.POST.get("session") or None
    is_new_session = session_id is None
    if is_new_session:
        company_id = request.POST.get("company") or None
        company = get_object_or_404(Company, pk=company_id, is_active=True) if company_id else None
        session = ChatSession.objects.create(company=company, title=prompt[:80])
    else:
        session = get_object_or_404(ChatSession.objects.select_related("company"), pk=session_id)
        company = session.company
        session.save(update_fields=["updated_at"])

    task = TaskResult.objects.create(task_id=uuid.uuid4().hex[:10], prompt=prompt, company=company, session=session)
    process_agent_task.defer(task_id=task.task_id)

    payload = {"task_id": task.task_id, "status": task.status, "prompt": prompt}
    publish_event_sync(channel=f"tasks:{task.task_id}", event_type="task_queued", payload=payload)
    publish_event_sync(channel="public:stream", event_type="feed_update", payload=payload)

    response = render(request, "core/chat/_message.html", {
        "task": task, "session": session, "is_new_session": is_new_session,
    })
    if is_new_session:
        response["HX-Push-Url"] = reverse("core:chat_session", args=[session.pk])
    return htmx_trigger(response, sessionsChanged=True)


def task_status(request, task_id):
    task = get_object_or_404(TaskResult, pk=task_id)
    return JsonResponse({"task_id": task.task_id, "status": task.status, "result": task.result})


def task_detail(request, task_id):
    task = get_object_or_404(TaskResult.objects.select_related("company", "session"), pk=task_id)
    return render(request, "core/tasks/_detail.html", {"task": task})


def jobs_partial(request):
    jobs = ProcrastinateJob.objects.order_by("-id")[:25]
    return render(request, "core/partials/_jobs.html", {"jobs": jobs})
