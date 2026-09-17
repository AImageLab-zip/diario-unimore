import time

from django.core.management.base import BaseCommand

from activities.models import GoogleCalendarCredential
from activities.calendar_service import get_calendar_service_for, sync_events_from_google


class Command(BaseCommand):
    help = "Controlla periodicamente Google Calendar di ogni account collegato e aggiorna MySQL"

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=5, help="Intervallo in minuti")

    def handle(self, *args, **options):
        interval_seconds = options['interval'] * 60
        self.stdout.write(self.style.SUCCESS(
            f"Watcher avviato (ogni {options['interval']} min)..."
        ))

        while True:
            credenziali = GoogleCalendarCredential.objects.select_related('user')

            if not credenziali.exists():
                self.stdout.write("Nessun account collegato.")

            for cred in credenziali:
                etichetta = f"{cred.user} → {cred.google_email}"
                try:
                    service = get_calendar_service_for(cred)
                    if service is None:
                        continue
                    up, rm = sync_events_from_google(cred, service)
                    self.stdout.write(self.style.SUCCESS(
                        f"{etichetta}: {up} aggiornati/creati, {rm} eliminati."
                    ))
                except Exception as e:
                    # un token revocato non deve bloccare gli altri account
                    self.stderr.write(self.style.ERROR(f"{etichetta}: errore — {e}"))

            time.sleep(interval_seconds)