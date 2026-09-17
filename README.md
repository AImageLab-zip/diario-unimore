# Diario

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

In **sviluppo** la stack bypassa Traefik e pubblica la porta `8101` direttamente
sull'host (`http://diario.ing.unimore.it:8101`). Shibboleth non è disponibile in
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
GOOGLE_REDIRECT_URI=http://localhost:8101/oauth2callback/
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

Il servizio risponde su `http://diario.ing.unimore.it:8101` — oppure su
`http://localhost:8101` se usi il port forwarding di VS Code Remote.

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
docker compose ps        # tre container Up, diario-db healthy
```

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

### Progetto Google Cloud

> **Questo è il punto aperto più importante del progetto.**

Al momento della scrittura, l'applicazione usa un progetto Google Cloud
**personale in modalità test**. Questo comporta due limiti che impediscono
l'uso reale da parte dei docenti:

- solo gli account inseriti manualmente nella lista utenti di test possono
  autorizzare l'applicazione;
- i refresh token **scadono dopo 7 giorni**, interrompendo la sincronizzazione.

La soluzione è creare il progetto **dentro l'organizzazione `unimore.it`** e
configurarlo come applicazione **Internal**: in quel caso non serve la verifica
di Google, non ci sono liste di autorizzazione e i token non scadono.
Richiede un account con permessi sul Workspace di ateneo.

Una volta ottenuto il nuovo progetto, basta sostituire `credentials.json`:
il codice non cambia.

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
