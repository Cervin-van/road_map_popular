from django.apps import AppConfig


class LocationsConfig(AppConfig):
    name = "apps.locations"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from .signals import connect_signals

        connect_signals()
