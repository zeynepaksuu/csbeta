from core.models import AgentSettings, Company, TaskResult

HISTORY_LIMIT = 20


def render_system_prompt(base_prompt: str, company: Company | None) -> str:
    prompt = base_prompt.strip()
    if company is None:
        return prompt
    prompt += f"\n\n<firma_bilgileri>\n{company.profile_text()}\n</firma_bilgileri>"
    if company.system_prompt:
        prompt += f"\n\n<firma_talimatlari>\n{company.system_prompt}\n</firma_talimatlari>"
    return prompt


def build_system_prompt(company: Company | None, settings: AgentSettings | None = None) -> str:
    settings = settings or AgentSettings.load()
    return render_system_prompt(settings.system_prompt, company)


def build_user_prompt(task: TaskResult) -> str:
    if task.session_id is None:
        return task.prompt
    previous = list(
        TaskResult.objects.filter(
            session_id=task.session_id,
            status=TaskResult.Status.COMPLETED,
            created_at__lt=task.created_at,
        ).order_by("-created_at")[:HISTORY_LIMIT]
    )
    if not previous:
        return task.prompt
    turns = "\n\n".join(f"Kullanıcı: {t.prompt}\nAsistan: {t.result}" for t in reversed(previous))
    return f"<onceki_konusma>\n{turns}\n</onceki_konusma>\n\n{task.prompt}"
