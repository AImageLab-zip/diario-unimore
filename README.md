# Diario
<p align="center">
  <img src="https://github.com/user-attachments/assets/fc4b8017-39fb-47ba-b366-72c88378627f" alt="La dashboard di Diario" width="700">
</p>
---

Applicazione Django che legge gli impegni dal Google Calendar dei docenti,
li classifica automaticamente nelle categorie del registro attività di Esse3
tramite un modello linguistico, e li salva su database in attesa di essere
riportati sul registro.

Il servizio è in produzione su **https://diario.ing.unimore.it**, ospitato
sull'infrastruttura AImageLab (`services-host.ing.unimore.it`).

---

## Indice

- [Come funziona](#come-funziona)
- [Struttura del repository](#struttura-del-repository)
- [Architettura](#architettura)
- [Configurazione](#configurazione)
- [Avvio in sviluppo](#avvio-in-sviluppo)
- [Avvio in produzione](#avvio-in-produzione)
- [Autenticazione Shibboleth](#autenticazione-shibboleth)
- [Collegamento Google Calendar](#collegamento-google-calendar)
- [Classificazione AI](#classificazione-ai)
- [Comandi utili](#comandi-utili)
- [Problemi noti e cose da fare](#problemi-noti-e-cose-da-fare)

---

## Come funziona

Il flusso completo, dal punto di vista di un docente:

1. Apre `diario.ing.unimore.it` e viene autenticato da **Shibboleth** con le
   credenziali di ateneo. Django riceve l'identità tramite header HTTP e crea
   l'utente al primo accesso.
2. Clicca "Collega il calendario" e autorizza l'applicazione tramite **OAuth**
   a leggere il proprio Google Calendar. Può collegare più account.
3. Un container separato (il **watcher**) interroga periodicamente i calendari
   collegati, scarica gli eventi e li fa classificare a un modello linguistico
   in una delle categorie del registro Esse3.
4. Gli eventi classificati come `NON_ACCADEMICO` (palestra, visite mediche,
   impegni privati) vengono marcati come ignorati e non sincronizzati.

L'interfaccia web serve **solo** a collegare e scollegare i calendari: i docenti
consultano le attività su Esse3, non qui.
<p align="center">
  <img src="https://github.com/user-attachments/assets/6f5254c8-597a-4200-9df7-4ae1a5711a4c" alt="La dashboard di Diario" width="500">
</p>

---

## Struttura del repository

```
diario/
├── dev-gmetani/              # il codice dell'applicazione
│   ├── activities/           # app Django principale
│   │   ├── management/commands/run_watcher.py
│   │   ├── static/activities/diario.css
│   │   ├── templates/activities/
│   │   ├── ai_service.py     # classificazione degli eventi
│   │   ├── calendar_service.py  # lettura da Google Calendar
│   │   ├── middleware.py     # autenticazione Shibboleth
│   │   ├── models.py
│   │   └── views.py          # flusso OAuth + dashboard
│   ├── config/               # settings, urls, wsgi
│   ├── Dockerfile
│   ├── docker-compose.yml    # stack di SVILUPPO
│   ├── requirements.txt
│   └── .env                  # NON versionato
└── production/
    ├── docker-compose.yml    # stack di PRODUZIONE
    └── .env                  # NON versionato
```

> **Nota sulla struttura.** Il codice sta dentro `dev-gmetani/` per ragioni
> storiche: era la cartella creata da `add-user.sh`. La stack di produzione non
> duplica il codice, lo costruisce dalla stessa sorgente con
> `build.context: ../dev-gmetani`. **Non clonare il codice in `production/`**:
> due copie divergono e diventano impossibili da mantenere allineate.
> Se hai tempo, la cosa giusta è rinominare `dev-gmetani/` in `app/` e
> aggiornare i due compose.

---

## Architettura

In **produzione** girano tre container:

| Container | Ruolo | Reti |
|---|---|---|
| `diario` | Django + gunicorn, porta 8000 | `proxy-net`, `internal` |
| `diario-db` | MySQL 8.0 | `internal` |
| `diario-watcher` | Sincronizzazione periodica | `proxy-net`, `internal` |

Le due reti hanno uno scopo preciso:

- **`internal`** è dichiarata `internal: true`, quindi non ha gateway verso
  l'esterno. MySQL sta solo qui: non può raggiungere internet né essere
  raggiunto da fuori.
- **`proxy-net`** è la rete condivisa di Traefik, già esistente sul server
  (`external: true`). Dà a Django sia l'ingresso dal reverse proxy sia l'uscita
  verso le API di Google.

Django e il watcher stanno su entrambe perché devono parlare con il database
*e* con internet. **Nessuna porta è pubblicata sull'host**: l'unico ingresso è
Traefik, che termina il TLS con un certificato Let's Encrypt.

In **sviluppo** la stack bypassa Traefik e pubblica la porta `<port>` direttamente
sull'host (`http://diario.ing.unimore.it:<port>`). Shibboleth non è disponibile in
sviluppo.

---

## Configurazione

I file `.env` **non sono versionati**. Vanno creati a mano partendo da
`.env.example`.

### `production/.env`

```dotenv
DEBUG=False
SECRET_KEY=<generare, vedi sotto>
ALLOWED_HOSTS=diario.ing.unimore.it

# Django → MySQL
DB_NAME=diario
DB_USER=diario
DB_PASSWORD=<password>
DB_HOST=diario-db
DB_PORT=3306

# Inizializzazione del container MySQL (stessi valori di DB_*)
MYSQL_DATABASE=diario
MYSQL_USER=diario
MYSQL_PASSWORD=<stessa di DB_PASSWORD>
MYSQL_ROOT_PASSWORD=<password root>

# OpenAI per la classificazione
OPENAI_API_KEY=<chiave>

# OAuth Google
GOOGLE_REDIRECT_URI=https://diario.ing.unimore.it/oauth2callback/
OAUTHLIB_RELAX_TOKEN_SCOPE=1

# Account autorizzati in deroga al filtro sull'affiliazione (uid, separati da virgola)
UID_IN_DEROGA=
```

Per generare la `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### `dev-gmetani/.env`

Uguale, con queste differenze:

```dotenv
DEBUG=True
ALLOWED_HOSTS=diario.ing.unimore.it,localhost,127.0.0.1
DB_HOST=db-dev-gmetani
GOOGLE_REDIRECT_URI=http://localhost:<port>/oauth2callback/
OAUTHLIB_INSECURE_TRANSPORT=1
```

> `OAUTHLIB_INSECURE_TRANSPORT` permette il flusso OAuth su HTTP.
> **Non metterlo mai in produzione.**

### `credentials.json`

Il file delle credenziali OAuth di Google va in `dev-gmetani/credentials.json`.
Non è versionato. Deve essere di tipo **applicazione web** (la prima chiave del
JSON è `"web"`, non `"installed"`).

---

## Avvio in sviluppo

```bash
cd dev-gmetani
docker compose up -d --build
docker compose exec diario-dev-gmetani python manage.py migrate
docker compose exec diario-dev-gmetani python manage.py createsuperuser
```

Il servizio risponde su `http://diario.ing.unimore.it:<port>` — oppure su
`http://localhost:port` se usi il port forwarding di VS Code Remote.

In sviluppo il codice è **montato come volume** (`.:/app`), quindi le modifiche
sono immediate e `runserver` ricarica da solo. Serve ricostruire solo se cambi
`requirements.txt` o il `Dockerfile`.

---

## Avvio in produzione

```bash
cd production
docker compose up -d --build
docker compose logs -f diario
```

In produzione il codice è **dentro l'immagine**: ogni modifica richiede
`--build`. Migrazioni e `collectstatic` girano automaticamente all'avvio,
come da `command` nel compose.

Verifica che tutto sia in piedi:

```bash
docker compose ps        # tre container UP, diario-db healthy
```

<p align="center">
   <img width="1017" height="83" alt="image" src="https://github.com/user-attachments/assets/e9af9187-c0dc-478a-bcaa-311f98dfe737" />
</p>

---

## Autenticazione Shibboleth

Si attiva con una singola label Traefik nel compose di produzione:

```yaml
- "traefik.http.routers.diario.middlewares=shib-auth@file"
```

Traefik intercetta ogni richiesta, verifica la sessione SAML e inoltra a Django
una serie di header con l'identità dell'utente:

| Header | Contenuto | Esempio |
|---|---|---|
| `X-Shib-Eppn` | identificativo univoco | `339664@unimore.it` |
| `X-Shib-Uid` | matricola | `339664` |
| `X-Shib-Mail` | casella di posta | `339664@studenti.unimore.it` |
| `X-Shib-Cn` | nome completo | `MARIO ROSSI` |
| `X-Shib-Affiliation` | ruolo | `member@unimore.it;student@unimore.it` |

Django li legge come `HTTP_X_SHIB_*` in `request.META`.

`activities/middleware.py` fa due cose:

1. autentica l'utente usando `X-Shib-Eppn` come username, creandolo al primo
   accesso (`RemoteUserBackend`);
2. **filtra per affiliazione**: entrano solo `faculty`, `staff` o `employee`.
   Chi non rientra vede la pagina `accesso_negato.html` con status 403.

La variabile `UID_IN_DEROGA` permette di far entrare account specifici a
prescindere dall'affiliazione — serve per lo sviluppo, dato che gli studenti
sarebbero altrimenti bloccati. Si configura nel `.env`, senza toccare il codice.

> **Attenzione.** Con Shibboleth attivo non si può accedere all'admin Django
> con username e password: il middleware riautentica dall'header a ogni
> richiesta, sovrascrivendo il login. Per accedere all'admin bisogna promuovere
> a superuser l'utente creato da Shibboleth (vedi *Comandi utili*).

---

## Collegamento Google Calendar

Il flusso OAuth è in `activities/views.py`, in tre viste:

- `collega_calendar` costruisce l'URL di consenso e ci reindirizza l'utente;
- `oauth2callback` riceve il codice da Google, lo scambia con un refresh token
  e lo salva nel database associato all'utente;
- `scollega_calendar` rimuove una credenziale.

Ogni utente può collegare **più account Google**: il modello
`GoogleCalendarCredential` ha una ForeignKey verso l'utente e il campo
`google_email` per distinguerli.

### Dettagli che rompono il flusso se sbagliati

- `access_type='offline'` con `prompt='consent'` sono **obbligatori**, altrimenti
  Google restituisce solo un access token di un'ora e la sincronizzazione muore
  quasi subito.
- Il **code verifier PKCE** va salvato in sessione tra le due viste, perché sono
  due istanze diverse di `Flow`. Senza, il callback fallisce con
  `Missing code verifier`.
- Il `redirect_uri` deve combaciare **esattamente** con uno di quelli registrati
  in Google Cloud Console, barra finale compresa.
- Dietro Traefik serve `SECURE_PROXY_SSL_HEADER` in `settings.py`, altrimenti
  `request.build_absolute_uri()` produce `http://` e il token scambio fallisce.

---

## Google Cloud Console

L'applicazione accede a Google Calendar tramite OAuth 2.0. Tutta la
configurazione lato Google vive in un progetto su
[Google Cloud Console](https://console.cloud.google.com), ed è il punto in cui
più facilmente le cose si rompono: vale la pena leggere questa sezione prima
di toccare qualsiasi cosa.

### Lo stato attuale e perché è un problema

Il progetto in uso è **personale** e la sua schermata di consenso è in
**modalità test**. Questo comporta due limiti che rendono il servizio
inutilizzabile nella pratica:

- **Lista chiusa di utenti.** Solo gli account inseriti a mano tra gli "utenti
  di prova" possono autorizzare l'applicazione. Chiunque altro riceve
  "Accesso bloccato: questa app non ha completato la procedura di verifica di
  Google". Il limite è di 100 utenti.
- **Token che scadono dopo 7 giorni.** In modalità test Google invalida i
  refresh token dopo una settimana. Il watcher smette di sincronizzare e ogni
  docente deve ricollegare il calendario. Non è un bug dell'applicazione.

Per superarli **non** serve chiedere la verifica a Google: quella procedura
richiede privacy policy pubblica, dominio verificato, un video dimostrativo e
settimane di attesa, perché `calendar.readonly` è considerato uno scope
sensibile. Per un servizio di ateneo è la strada sbagliata.

### La soluzione: un progetto Internal

Se il progetto Cloud appartiene all'**organizzazione `unimore.it`**, la
schermata di consenso può essere configurata come **Internal**. In quel caso:

| | Test (attuale) | Internal (obiettivo) |
|---|---|---|
| Chi può autorizzare | solo utenti in lista | qualsiasi account dell'organizzazione |
| Verifica Google | non richiesta | non richiesta |
| Scadenza refresh token | 7 giorni | nessuna |
| Avviso "app non verificata" | sì | no |

L'opzione Internal **compare solo per progetti che appartengono a
un'organizzazione**: su un progetto personale è disabilitata, e non esiste
modo di aggirarlo lato codice. Serve un account con permessi sul Google
Workspace di ateneo — quindi è una richiesta da fare al referente, non
qualcosa che si risolve da soli.

### Creare il progetto da zero

1. Accedere a `console.cloud.google.com` con un account `@unimore.it`.

2. Aprire il selettore dei progetti in alto e scegliere **Nuovo progetto**.
   Alla voce *Organizzazione* (o *Località*) selezionare `unimore.it` invece di
   "Nessuna organizzazione". **È il passaggio determinante**: se il progetto
   nasce senza organizzazione, l'opzione Internal non sarà disponibile e
   bisognerà ricominciare.

3. Da *API e servizi → Libreria*, cercare **Google Calendar API** e attivarla.

4. Da *API e servizi → Schermata consenso OAuth* — nella nuova interfaccia
   *Google Auth Platform → Pubblico* — selezionare **Internal** come tipo di
   utente, poi compilare nome dell'applicazione (`Diario`), email di supporto e
   email di contatto.

5. Nella sezione degli ambiti — *Accesso ai dati* nella nuova interfaccia —
   aggiungere lo scope:

```
   https://www.googleapis.com/auth/calendar.readonly
```

   Non aggiungere scope più ampi di quelli necessari: l'applicazione legge il
   calendario e non scrive nulla.

6. Da *Credenziali* — o *Client* — scegliere **Crea credenziali → ID client
   OAuth**, poi **Applicazione web** come tipo. Alla voce *URI di
   reindirizzamento autorizzati* inserire esattamente:

```
   https://diario.ing.unimore.it/oauth2callback/
```

   Per poter sviluppare in locale, aggiungere come secondo URI:

```
   http://localhost:port/oauth2callback/
```

7. Scaricare il file JSON e salvarlo come `dev-gmetani/credentials.json`,
   sostituendo quello esistente. **Il codice non va modificato**: legge il
   percorso da `GOOGLE_CREDENTIALS_PATH` in `settings.py`.

### Verificare di aver fatto la cosa giusta

Apri `credentials.json` e guarda la prima chiave:

- `"web"` → corretto, è un client di tipo applicazione web;
- `"installed"` → **sbagliato**, è un client desktop. Non supporta il flusso
  con redirect verso un URL esterno e l'applicazione fallirà. Va creato un
  nuovo client di tipo web.

### Cose che fanno fallire il flusso OAuth

Gli errori più comuni, con il loro sintomo esatto:

**`Error 400: redirect_uri_mismatch`**
L'URI che l'applicazione invia non corrisponde a nessuno di quelli registrati.
La corrispondenza è letterale: `http` contro `https`, la porta, e anche la
**barra finale** contano. Confronta il valore di `GOOGLE_REDIRECT_URI` nel
`.env` con la lista in Console, carattere per carattere. Dopo una modifica
Google avvisa che l'applicazione delle impostazioni può richiedere *da cinque
minuti a qualche ora*: se hai appena salvato, aspetta prima di concludere che
sia sbagliato.

**`invalid_grant: Missing code verifier`**
La libreria usa PKCE: genera un valore casuale, ne manda l'hash nella prima
richiesta e deve rimandare l'originale nella seconda. Poiché
`collega_calendar` e `oauth2callback` creano due oggetti `Flow` distinti, il
verifier va salvato in sessione dal primo e riassegnato al secondo. È già
gestito in `views.py`: se tocchi quelle viste, non rimuoverlo.

**Il refresh token non arriva**
Google lo rilascia solo con `access_type='offline'` **e** `prompt='consent'`.
Senza, ottieni un access token valido un'ora e la sincronizzazione muore quasi
subito senza errori evidenti.

**Il selettore dell'account non compare quando se ne collega un secondo**
Serve `prompt='consent select_account'`, altrimenti Google riusa
silenziosamente l'account già autenticato nel browser.

**`redirect_uri` con `http://` invece di `https://`**
Dietro Traefik, `request.build_absolute_uri()` produce lo schema sbagliato se
manca `SECURE_PROXY_SSL_HEADER` in `settings.py`. Non rimuoverlo.

**In sviluppo: `InsecureTransportError`**
`google-auth-oauthlib` rifiuta OAuth su HTTP. In sviluppo serve
`OAUTHLIB_INSECURE_TRANSPORT=1` nel `.env`. **Mai in produzione.**

### Branding

Il nome che i docenti vedono nella schermata di consenso ("Continua su …") si
imposta in *Google Auth Platform → Branding*. È il nome dell'applicazione, non
quello del progetto Cloud: vale la pena che dica `Diario` e non il nome tecnico
del progetto.

Il logo è opzionale. Su un'app External il caricamento di un logo può far
scattare il processo di verifica di Google; su un'app Internal no.

### Limitare gli account proponibili

La vista `collega_calendar` può passare il parametro `hd='unimore.it'`, che
filtra il selettore degli account mostrando solo quelli del dominio di ateneo.
Due avvertenze: è un **suggerimento**, non un vincolo — un utente può
comunque autenticarsi con un altro account, quindi se serve una garanzia va
verificata l'email nel callback; e se il progetto deve permettere anche il
collegamento di account personali, questo filtro lo impedisce.

---

## Classificazione AI

`activities/ai_service.py` invia titolo e descrizione di ogni evento a un
modello linguistico, che risponde con **una** delle categorie in
`ESSE3_CATEGORIES`. La temperatura è impostata a `0` perché la stessa attività
riceva sempre la stessa categoria — importante per un registro.

Se la risposta non corrisponde a nessuna categoria valida, o se la chiamata
fallisce, il risultato è `NON_ACCADEMICO` e l'evento viene ignorato. Questo
significa che **un errore dell'API si traduce in un evento non sincronizzato,
non in un crash** — ma anche che errori silenziosi possono passare inosservati.

Le categorie sono quelle del registro Esse3 e vanno tenute allineate se l'ateneo
le modifica.
<p align="center">
<img width="1571" height="654" alt="image" src="https://github.com/user-attachments/assets/f7c76828-b439-43a2-86dd-c1bd6fe7916d" />
</p>

---

## Comandi utili

Sostituisci `diario` con `diario-dev-gmetani` per lo sviluppo.

**Log del watcher** (il posto dove si vede se la sincronizzazione funziona):

```bash
docker compose logs -f diario-watcher
```

**Sincronizzazione manuale**, senza aspettare il ciclo:

```bash
docker compose exec diario python manage.py run_watcher --interval 1
```

**Promuovere un utente Shibboleth a superuser**:

```bash
docker compose exec diario python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.get(username='MATRICOLA@unimore.it')
u.is_superuser = True
u.is_staff = True
u.save()
"
```

**Elencare gli utenti**:

```bash
docker compose exec diario python manage.py shell -c "
from django.contrib.auth.models import User
for u in User.objects.all():
    print(u.username, u.is_superuser)
"
```

**Ispezionare il database** (non ha porte pubblicate, si entra dal container):

```bash
docker compose exec diario-db mysql -u diario -p diario
```

**Log di Traefik** per problemi di certificato o routing:

```bash
docker logs traefik --tail 100 2>&1 | grep -i -E "acme|certificate|diario"
```

---

## Problemi noti e cose da fare

### Da risolvere

- **Progetto Google Cloud personale** (vedi sopra). È il blocco principale:
  finché non è Internal sotto `unimore.it`, il servizio non è usabile dai
  docenti. Tutto il resto funziona.
- **Nessuna scrittura su Esse3.** L'applicazione classifica e salva le attività,
  ma il trasferimento vero e proprio sul registro non è implementato. Il campo
  `sync_status` è predisposto (`PENDING` / `SYNCED` / `FAILED`) ma nulla lo porta
  mai a `SYNCED`. È la funzionalità grossa che manca.
- **Logout Shibboleth non verificato.** La vista `esci` chiude la sessione
  Django e reindirizza a `/Shibboleth.sso/Logout`, ma il comportamento del
  Single Logout sul SP di ateneo non è stato testato a fondo.

### Migliorie sensate

- Spostare il codice da `dev-gmetani/` a `app/`, aggiornando i due compose.
  La cartella ha un nome fuorviante.
- Popolare `first_name`, `last_name` ed `email` dell'utente Django dagli header
  Shibboleth al primo accesso: gli attributi arrivano già, basta leggerli.
- Aggiungere un healthcheck al watcher: oggi se va in errore riparte, ma non
  c'è modo di accorgersene senza guardare i log.
- I valori accettati per l'affiliazione (`faculty`, `staff`, `employee`) sono
  un'ipotesi ragionevole ma non confermata con l'IdP. Se un docente si vedesse
  negare l'accesso, la pagina 403 mostra l'affiliazione ricevuta: basta
  aggiungerla alla lista in `middleware.py`.
- Valutare il **service account con delega domain-wide** come alternativa
  all'OAuth per-utente: eliminerebbe la necessità che ogni docente autorizzi
  manualmente, ma richiede l'intervento dell'amministratore del Workspace e
  concede accesso a tutti i calendari del dominio.

### Trappole in cui è facile cadere

- In produzione il codice è **dentro l'immagine**: senza `--build` le modifiche
  non hanno effetto. In sviluppo è montato come volume, quindi il comportamento
  è diverso.
- `docker compose down -v` **cancella il database**, superuser e token OAuth
  compresi. Il `-v` rimuove i volumi.
- Il DNS di `diario.ing.unimore.it` è un CNAME gestito dall'infrastruttura. Se
  il sito non risponde, controlla prima che il nome risolva e poi i log di
  Traefik per l'emissione del certificato.
- I file `.env`, `credentials.json` e `token.json` contengono segreti e sono in
  `.gitignore`. Non committarli.
