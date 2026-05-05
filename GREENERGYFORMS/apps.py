from django.apps import AppConfig


class GreenergyformsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'GREENERGYFORMS'

    def ready(self):
        import GREENERGYFORMS.signals
