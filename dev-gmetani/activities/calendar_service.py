from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import AcademicActivity
from .ai_service import classify_activity

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def get_calendar_service_for(user):
    """Costruisce il client Calendar usando le credenziali salvate per l'utente."""
    cred = getattr(user, 'google_credential', None)
    if cred is None:
        return None

    creds = Credentials(
        token=cred.token or None,
        refresh_token=cred.refresh_token,
        token_uri=cred.token_uri,
        client_id=cred.client_id,
        client_secret=cred.client_secret,
        scopes=cred.scopes.split(),
    )
    return build('calendar', 'v3', credentials=creds)


def sync_events_from_google(user, service, calendar_id='primary'):
    time_min = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        showDeleted=True,
        singleEvents=True,
        maxResults=250,
    ).execute()

    events = events_result.get('items', [])
    updated_or_created = 0
    deleted_count = 0

    for event in events:
        google_id = event.get('id')

        # 1. Gestione cancellazioni
        if event.get('status') == 'cancelled':
            deleted, _ = AcademicActivity.objects.filter(
                user=user, google_event_id=google_id
            ).delete()
            if deleted:
                deleted_count += 1
            continue

        start_raw = event['start'].get('dateTime')
        end_raw = event['end'].get('dateTime')
        if not start_raw or not end_raw:
            continue

        start_time = datetime.fromisoformat(start_raw)
        end_time = datetime.fromisoformat(end_raw)
        title = event.get('summary', 'Senza Titolo')
        description = event.get('description', '')

        activity = AcademicActivity.objects.filter(
            user=user, google_event_id=google_id
        ).first()

        # 2. Evento esistente: verifica modifiche
        if activity:
            has_changed = (
                activity.title != title
                or activity.description != description
                or activity.start_time != start_time
                or activity.end_time != end_time
            )
            if has_changed:
                activity.title = title
                activity.description = description
                activity.start_time = start_time
                activity.end_time = end_time

                predicted_category = classify_activity(title, description)
                activity.category = predicted_category

                if predicted_category == "NON_ACCADEMICO":
                    activity.sync_status = 'IGNORED'
                elif activity.sync_status == 'SYNCED':
                    activity.sync_status = 'PENDING'

                activity.save()
                updated_or_created += 1

        # 3. Nuovo evento: classificazione AI
        else:
            predicted_category = classify_activity(title, description)
            initial_status = 'IGNORED' if predicted_category == "NON_ACCADEMICO" else 'PENDING'

            AcademicActivity.objects.create(
                user=user,
                google_event_id=google_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                category=predicted_category,
                sync_status=initial_status,
            )
            updated_or_created += 1

    return updated_or_created, deleted_count