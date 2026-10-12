from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.prompts import build_system_prompt, build_user_prompt
from core.models import AgentSettings, ChatSession, Company, TaskResult

HTMX = {"HTTP_HX_REQUEST": "true"}


class CompanyCrudTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("tester", password="pass")
        self.client.force_login(user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_pages_render(self):
        company = Company.objects.create(name="Acme")
        for url in [
            reverse("core:dashboard"),
            reverse("core:company_list"),
            reverse("core:company_detail", args=[company.pk]),
            reverse("core:chat"),
            reverse("core:jobs_partial"),
            reverse("core:company_create"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_create_update_delete(self):
        response = self.client.post(reverse("core:company_create"), {
            "name": "Acme", "sector": "Yazılım", "system_prompt": "Resmi konuş.", "is_active": "on",
        }, **HTMX)
        self.assertIn("companiesChanged", response["HX-Trigger"])
        company = Company.objects.get(name="Acme")

        self.client.post(reverse("core:company_edit", args=[company.pk]), {"name": "Acme AŞ"}, **HTMX)
        company.refresh_from_db()
        self.assertEqual(company.name, "Acme AŞ")

        rows = self.client.get(reverse("core:company_list"), {"q": "acme"}, **HTMX)
        self.assertContains(rows, "Acme AŞ")
        self.assertNotContains(rows, "<html")

        self.client.post(reverse("core:company_delete", args=[company.pk]), **HTMX)
        self.assertFalse(Company.objects.exists())

    def test_invalid_form_rerenders(self):
        response = self.client.post(reverse("core:company_create"), {"name": ""}, **HTMX)
        self.assertNotIn("HX-Trigger", response)
        self.assertContains(response, "text-rose-400")

    @patch("core.views.publish_event_sync")
    @patch("core.views.process_agent_task")
    def test_first_message_starts_session_next_continues(self, task_mock, publish_mock):
        company = Company.objects.create(name="Acme")
        url = reverse("core:task_create")

        first = self.client.post(url, {"prompt": "Ne satıyorsunuz?", "company": company.pk}, **HTMX)
        session = ChatSession.objects.get()
        self.assertEqual(session.company, company)
        self.assertEqual(first["HX-Push-Url"], reverse("core:chat_session", args=[session.pk]))
        self.assertContains(first, f'name="session" value="{session.pk}"')
        task = TaskResult.objects.get()
        self.assertEqual(task.session, session)
        task_mock.defer.assert_called_once_with(task_id=task.task_id)

        second = self.client.post(url, {"prompt": "Fiyatı ne?", "session": session.pk}, **HTMX)
        self.assertNotIn("HX-Push-Url", second)
        self.assertEqual(session.tasks.count(), 2)
        self.assertTrue(all(t.company == company for t in session.tasks.all()))

        self.client.post(url, {"prompt": "Başka konu", "company": ""}, **HTMX)
        self.assertEqual(ChatSession.objects.count(), 2)

        status = self.client.get(reverse("core:task_status", args=[task.task_id])).json()
        self.assertEqual(status["status"], "queued")

    def test_sessions_keep_their_own_history(self):
        company = Company.objects.create(name="Acme")
        old = ChatSession.objects.create(title="Eski", company=company)
        new = ChatSession.objects.create(title="Yeni", company=company)
        TaskResult.objects.create(task_id="t1", prompt="Fiyat?", company=company, session=old, status="completed", result="100 TL")
        TaskResult.objects.create(task_id="t2", prompt="Adres?", company=company, session=new, status="completed", result="Moda")

        detail = self.client.get(reverse("core:task_detail", args=["t1"]), **HTMX)
        self.assertContains(detail, 'data-md="100 TL"')
        self.assertContains(detail, reverse("core:chat_session", args=[old.pk]))

        page = self.client.get(reverse("core:chat_session", args=[old.pk]))
        self.assertContains(page, "Fiyat?")
        self.assertNotContains(page, "Adres?")
        self.assertContains(page, "Yeni")  # diğer sohbet listede duruyor

        empty = self.client.get(reverse("core:chat"))
        self.assertContains(empty, "chat-empty")
        self.assertEqual([s.pk for s in empty.context["sessions"]], [new.pk, old.pk])

    def test_delete_session(self):
        session = ChatSession.objects.create(title="Silinecek")
        TaskResult.objects.create(task_id="t1", prompt="x", session=session)
        url = reverse("core:chat_session_delete", args=[session.pk])
        response = self.client.post(url, {"session": session.pk}, **HTMX)
        self.assertEqual(response["HX-Redirect"], reverse("core:chat"))
        self.assertFalse(ChatSession.objects.exists())
        self.assertFalse(TaskResult.objects.exists())


class ConversationMemoryTests(TestCase):
    def test_previous_turns_are_sent(self):
        session = ChatSession.objects.create()
        TaskResult.objects.create(task_id="a", prompt="Adım Ada", session=session, status="completed", result="Memnun oldum")
        TaskResult.objects.create(task_id="b", prompt="Hata veren", session=session, status="failed", result="err")
        other = ChatSession.objects.create()
        TaskResult.objects.create(task_id="c", prompt="Başka sohbet", session=other, status="completed", result="x")
        current = TaskResult.objects.create(task_id="d", prompt="Adım neydi?", session=session)

        prompt = build_user_prompt(current)
        self.assertIn("Kullanıcı: Adım Ada\nAsistan: Memnun oldum", prompt)
        self.assertNotIn("Hata veren", prompt)
        self.assertNotIn("Başka sohbet", prompt)
        self.assertTrue(prompt.endswith("Adım neydi?"))

    def test_first_message_has_no_history(self):
        session = ChatSession.objects.create()
        task = TaskResult.objects.create(task_id="a", prompt="Merhaba", session=session)
        self.assertEqual(build_user_prompt(task), "Merhaba")


class SystemPromptTests(TestCase):
    def test_company_prompt(self):
        company = Company(name="Acme", sector="Yazılım", knowledge="Ürün: X", system_prompt="Resmi konuş.")
        prompt = build_system_prompt(company)
        self.assertIn("Firma adı: Acme", prompt)
        self.assertIn("Ürün: X", prompt)
        self.assertIn("Resmi konuş.", prompt)

    def test_no_company(self):
        self.assertNotIn("<firma_bilgileri>", build_system_prompt(None))


class PromptEditingTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("tester", password="pass")
        self.client.force_login(user)
        self.company = Company.objects.create(name="Acme", knowledge="Ürün: X")

    def test_single_prompt_for_all_questions(self):
        self.assertEqual(self.client.get(reverse("core:agent_settings")).status_code, 200)
        response = self.client.post(reverse("core:agent_settings"), {
            "agent-system_prompt": "firma sahibi engin, kibar ol",
        }, **HTMX)
        self.assertIn("toast", response["HX-Trigger"])
        self.assertEqual(build_system_prompt(None), "firma sahibi engin, kibar ol")
        prompt = build_system_prompt(self.company)
        self.assertTrue(prompt.startswith("firma sahibi engin, kibar ol"))
        self.assertIn("Bilgi bankası: Ürün: X", prompt)

    def test_reset_to_default(self):
        settings_obj = AgentSettings.load()
        settings_obj.system_prompt = "değişti"
        settings_obj.save()
        self.client.post(reverse("core:agent_settings_reset"), **HTMX)
        self.assertIn("uydurma", build_system_prompt(None))

    def test_preview(self):
        response = self.client.post(reverse("core:agent_settings_preview"), {
            "preview_company": self.company.pk, "agent-system_prompt": "Merhaba",
        }, **HTMX)
        self.assertContains(response, "Merhaba")
        self.assertContains(response, "Ürün: X")

    def test_inline_company_prompt_edit(self):
        url = reverse("core:company_prompt", args=[self.company.pk])
        self.assertContains(self.client.get(url, {"edit": 1}, **HTMX), "<textarea")
        response = self.client.post(url, {"system_prompt": "Kısa cevap ver."}, **HTMX)
        self.assertContains(response, "Kısa cevap ver.")
        self.company.refresh_from_db()
        self.assertEqual(self.company.system_prompt, "Kısa cevap ver.")

    def test_settings_page_edits_company_instructions(self):
        url = reverse("core:agent_settings_company")
        self.assertContains(self.client.get(url, {"preview_company": self.company.pk}, **HTMX), "company-system-prompt")
        response = self.client.post(url, {"preview_company": self.company.pk, "system_prompt": "Firma sahibi Engin."}, **HTMX)
        self.assertIn("toast", response["HX-Trigger"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.system_prompt, "Firma sahibi Engin.")

        preview = self.client.post(reverse("core:agent_settings_preview"), {
            "preview_company": self.company.pk, "agent-system_prompt": "x", "system_prompt": "kaydedilmemiş metin",
        }, **HTMX)
        self.assertContains(preview, "kaydedilmemiş metin")


class McpConfigTests(TestCase):
    def test_external_added_only_when_configured(self):
        from django.test import override_settings
        from core.agent import build_mcp_servers

        with override_settings(EXTERNAL_MCP_URL="", EXTERNAL_MCP_TOKEN=""):
            servers, allowed = build_mcp_servers()
            self.assertNotIn("external", servers)
            self.assertNotIn("mcp__external", allowed)

        with override_settings(EXTERNAL_MCP_URL="https://example.test/mcp", EXTERNAL_MCP_TOKEN="secret"):
            servers, allowed = build_mcp_servers()
            self.assertEqual(servers["external"]["headers"]["Authorization"], "Bearer secret")
            self.assertIn("mcp__external", allowed)
