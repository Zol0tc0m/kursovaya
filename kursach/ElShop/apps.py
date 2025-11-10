from django.apps import AppConfig


class ElshopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ElShop'

    def ready(self):
        import ElShop.signals