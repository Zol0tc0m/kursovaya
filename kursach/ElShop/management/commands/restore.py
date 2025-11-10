# myapp/management/commands/restore_pg.py
import os, subprocess
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Восстановление PostgreSQL базы данных из резервной копии'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Путь к файлу резервной копии (.sql)',
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        if not os.path.exists(backup_file):
            self.stderr.write(self.style.ERROR(f"Файл не найден: {backup_file}"))
            return

        db_settings = settings.DATABASES['default']

        # Удаляем старую базу и создаём заново
        drop_command = [
            "dropdb",
            "-h", db_settings['HOST'],
            "-p", str(db_settings['PORT']),
            "-U", db_settings['USER'],
            db_settings['NAME']
        ]

        create_command = [
            "createdb",
            "-h", db_settings['HOST'],
            "-p", str(db_settings['PORT']),
            "-U", db_settings['USER'],
            db_settings['NAME']
        ]

        restore_command = [
            "pg_restore",
            "-h", db_settings['HOST'],
            "-p", str(db_settings['PORT']),
            "-U", db_settings['USER'],
            "-d", db_settings['NAME'],
            "-c",  # drop objects before recreating
            backup_file
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = db_settings['PASSWORD']

        try:
            subprocess.run(drop_command, check=True, env=env)
            subprocess.run(create_command, check=True, env=env)
            subprocess.run(restore_command, check=True, env=env)
            self.stdout.write(self.style.SUCCESS(f"База восстановлена из {backup_file}"))
        except subprocess.CalledProcessError:
            self.stderr.write(self.style.ERROR("Ошибка при восстановлении базы данных"))
