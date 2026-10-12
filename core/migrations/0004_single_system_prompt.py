from django.db import migrations, models

OLD_COMPANY_TEMPLATE_START = 'Sen "{firma_adi}" firması adına çalışan bir asistansın.'

NEW_DEFAULT = """Sen yardımsever bir asistansın. Kullanıcı hangi dilde yazıyorsa o dilde, kısa ve net cevap ver.
Bir firma adına konuşuyorsan soruları yalnızca sana verilen firma bilgilerine dayanarak yanıtla.
Bilgilerde olmayan bir şey sorulursa bunu bilmediğini açıkça söyle, uydurma."""


def drop_old_default_template(apps, schema_editor):
    # Eski varsayılan şablon yer tutucu içeriyordu; elle yazılmış bir prompt ise olduğu gibi kalsın.
    AgentSettings = apps.get_model("core", "AgentSettings")
    for settings in AgentSettings.objects.all():
        if settings.system_prompt.startswith(OLD_COMPANY_TEMPLATE_START):
            settings.system_prompt = NEW_DEFAULT
            settings.save(update_fields=["system_prompt"])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_agentsettings_company_prompt_template'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agentsettings',
            name='default_system_prompt',
        ),
        migrations.RenameField(
            model_name='agentsettings',
            old_name='company_prompt_template',
            new_name='system_prompt',
        ),
        migrations.AlterField(
            model_name='agentsettings',
            name='system_prompt',
            field=models.TextField(default=NEW_DEFAULT, help_text="Her soruda agent'a giden prompt. Firma seçilmişse sonuna o firmanın bilgileri ve talimatları eklenir.", verbose_name='System prompt'),
        ),
        migrations.RunPython(drop_old_default_template, migrations.RunPython.noop),
    ]
