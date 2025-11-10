import os, subprocess
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

class Command(BaseCommand):
    help = 'Создание резервной копии PostgreSQL базы данных'

    def handle(self, *args, **kwargs):
        db_settings = settings.DATABASES['default']
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        now = timezone.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(backup_dir, f"{db_settings['NAME']}_backup_{now}.sql")

        command = [
            "pg_dump",
            "-h", db_settings['HOST'],
            "-p", str(db_settings['PORT']),
            "-U", db_settings['USER'],
            "-F", "c",  # формат custom
            "-b",       # include blobs
            "-f", backup_file,
            db_settings['NAME']
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = db_settings['PASSWORD']

        try:
            subprocess.run(command, check=True, env=env)
            self.stdout.write(self.style.SUCCESS(f"Резервная копия создана: {backup_file}"))
        except subprocess.CalledProcessError:
            self.stderr.write(self.style.ERROR("Ошибка при создании резервной копии"))