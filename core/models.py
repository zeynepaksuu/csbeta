from django.db import models


class Company(models.Model):
    name = models.CharField("Firma adı", max_length=200, unique=True)
    sector = models.CharField("Sektör", max_length=120, blank=True)
    website = models.URLField("Web sitesi", blank=True)
    email = models.EmailField("E-posta", blank=True)
    phone = models.CharField("Telefon", max_length=40, blank=True)
    address = models.TextField("Adres", blank=True)
    description = models.TextField("Açıklama", blank=True)
    knowledge = models.TextField(
        "Bilgi bankası",
        blank=True,
        help_text="Ürünler, hizmetler, fiyatlar, SSS gibi agent'ın bilmesi gereken her şey.",
    )
    system_prompt = models.TextField(
        "System prompt",
        blank=True,
        help_text="Bu firma için agent'ın nasıl davranacağı (ton, kurallar, sınırlar).",
    )
    is_active = models.BooleanField("Aktif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Firma"
        verbose_name_plural = "Firmalar"

    def __str__(self):
        return self.name

    def profile_text(self):
        fields = [
            ("Firma adı", self.name),
            ("Sektör", self.sector),
            ("Web sitesi", self.website),
            ("E-posta", self.email),
            ("Telefon", self.phone),
            ("Adres", self.address),
            ("Açıklama", self.description),
            ("Bilgi bankası", self.knowledge),
        ]
        return "\n".join(f"{label}: {value}" for label, value in fields if value)


class ChatSession(models.Model):
    title = models.CharField("Başlık", max_length=200, blank=True)
    company = models.ForeignKey(
        Company,
        verbose_name="Firma",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Sohbet"
        verbose_name_plural = "Sohbetler"

    def __str__(self):
        return self.title or f"Sohbet #{self.pk}"


class TaskResult(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Sırada"
        RUNNING = "running", "Çalışıyor"
        COMPLETED = "completed", "Tamamlandı"
        FAILED = "failed", "Hata"

    task_id = models.CharField(max_length=32, primary_key=True)
    company = models.ForeignKey(
        Company,
        verbose_name="Firma",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    session = models.ForeignKey(
        ChatSession,
        verbose_name="Sohbet",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    prompt = models.TextField("Soru")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    result = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Görev"
        verbose_name_plural = "Görevler"

    def __str__(self):
        return f"{self.task_id} ({self.status})"


DEFAULT_SYSTEM_PROMPT = """Sen yardımsever bir asistansın. Kullanıcı hangi dilde yazıyorsa o dilde, kısa ve net cevap ver.
Bir firma adına konuşuyorsan soruları yalnızca sana verilen firma bilgilerine dayanarak yanıtla.
Bilgilerde olmayan bir şey sorulursa bunu bilmediğini açıkça söyle, uydurma."""


class AgentSettings(models.Model):
    system_prompt = models.TextField(
        "System prompt",
        default=DEFAULT_SYSTEM_PROMPT,
        help_text="Her soruda agent'a giden prompt. Firma seçilmişse sonuna o firmanın bilgileri ve talimatları eklenir.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Agent ayarları"
        verbose_name_plural = "Agent ayarları"

    def __str__(self):
        return "Agent ayarları"

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
