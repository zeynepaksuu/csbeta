import os
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_superuser(sender, **kwargs):
    from django.contrib.auth import get_user_model

    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
    if not username or not password:
        return

    User = get_user_model()
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(create_default_superuser, sender=self)
