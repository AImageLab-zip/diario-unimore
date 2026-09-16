from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from google_auth_oauthlib.flow import Flow
from django.contrib.auth import logout as django_logout
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
    collegato = hasattr(request.user, 'google_credential')
    return render(request, 'activities/dashboard.html', {'collegato': collegato})


@login_required
def collega_calendar(request):
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true',
        #hd='unimore.it',         # mostra solo account del dominio di ateneo
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

    GoogleCalendarCredential.objects.update_or_create(
        user=request.user,
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
def scollega_calendar(request):
    GoogleCalendarCredential.objects.filter(user=request.user).delete()
    return redirect('dashboard')




@login_required
def esci(request):
    django_logout(request)
    return redirect(
        'https://services-host.ing.unimore.it/Shibboleth.sso/Logout'
        '?return=https://diario.ing.unimore.it/'
    )