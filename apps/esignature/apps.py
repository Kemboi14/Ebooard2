from django.apps import AppConfig


class EsignatureConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.esignature"
    verbose_name = "Electronic Signatures"

    def ready(self):
        # Import signal handlers when the app is ready
        try:
            import apps.esignature.signals  # noqa: F401
        except ImportError:
            pass
