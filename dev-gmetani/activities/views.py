from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .models import GoogleCalendarCredential

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def _build_flow():
    return Flow.from_client_secrets_file(
        str(settings.GOOGLE_CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


@login_required
def dashboard(request):
    credenziali = list(request.user.google_credentials.all())

    selezionata = None
    pk = request.GET.get('cal')
    if pk:
        selezionata = next((c for c in credenziali if str(c.pk) == pk), None)

    return render(request, 'activities/dashboard.html', {
        'credenziali': credenziali,
        'selezionata': selezionata,
        'collegato': bool(credenziali),
    })


@login_required
def collega_calendar(request):
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent select_account',   # forza la scelta dell'account
        include_granted_scopes='true',
    )
    request.session['oauth_state'] = state
    request.session['code_verifier'] = flow.code_verifier
    return redirect(auth_url)


@login_required
def oauth2callback(request):
    flow = _build_flow()
    flow.code_verifier = request.session.get('code_verifier')
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    c = flow.credentials

    servizio = build('calendar', 'v3', credentials=c)
    email = servizio.calendarList().get(calendarId='primary').execute()['id']

    GoogleCalendarCredential.objects.update_or_create(
        user=request.user,
        google_email=email,
        defaults={
            'refresh_token': c.refresh_token,
            'token': c.token,
            'token_uri': c.token_uri,
            'client_id': c.client_id,
            'client_secret': c.client_secret,
            'scopes': ' '.join(c.scopes),
        },
    )
    request.session.pop('code_verifier', None)
    request.session.pop('oauth_state', None)
    return redirect('dashboard')


@login_required
def scollega_calendar(request, pk):
    cred = get_object_or_404(GoogleCalendarCredential, pk=pk, user=request.user)
    cred.delete()
    return redirect('dashboard')


@login_required
def esci(request):
    django_logout(request)
    return redirect(
        'https://services-host.ing.unimore.it/Shibboleth.sso/Logout'
        '?return=https://diario.ing.unimore.it/'
    )