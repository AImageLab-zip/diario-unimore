import os
import sys

from django.contrib.auth.middleware import RemoteUserMiddleware
from django.shortcuts import render

RUOLI_ABILITATI = ('faculty', 'staff', 'employee')

UID_IN_DEROGA = [
    u.strip() for u in os.environ.get('UID_IN_DEROGA', '').split(',') if u.strip()
]


class ShibbolethMiddleware(RemoteUserMiddleware):
    header = 'HTTP_X_SHIB_EPPN'

    def process_request(self, request):
        affiliation = request.META.get('HTTP_X_SHIB_AFFILIATION', '')
        uid = request.META.get('HTTP_X_SHIB_UID', '')

        print('FILTRO — affiliation:', repr(affiliation),
              '| uid:', repr(uid),
              '| deroghe:', UID_IN_DEROGA,
              file=sys.stderr, flush=True)

        if affiliation and uid not in UID_IN_DEROGA:
            ruoli = affiliation.lower()
            abilitato = any(r in ruoli for r in RUOLI_ABILITATI)
            print('FILTRO — abilitato:', abilitato, file=sys.stderr, flush=True)
            if not abilitato:
                print('FILTRO — blocco, rendo accesso_negato', file=sys.stderr, flush=True)
                return render(
                    request,
                    'activities/accesso_negato.html',
                    {'affiliazione': affiliation},
                    status=403,
                )

        return super().process_request(request)