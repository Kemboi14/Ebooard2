from django.apps import AppConfig


class VotingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voting'

    def ready(self):
        """
        Import signal handlers when app is ready.
        """
        import apps.voting.signals
