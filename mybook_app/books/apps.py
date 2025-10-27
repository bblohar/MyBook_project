from django.apps import AppConfig

class BooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'books'

    # --- ADD THIS METHOD ---
    def ready(self):
        import books.signals # This line imports and connects your signals