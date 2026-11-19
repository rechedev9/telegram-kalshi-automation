# Telegram-Kalshi CS2 Automation

Escucha señales de apuestas del canal privado de Telegram **APUESTA SEGURA CS2 | SOCIALPRO** y las convierte en ordenes limite YES en Kalshi. Funciona en modo DRY_RUN por defecto (no envia ordenes reales).

## Requisitos previos

- Python 3.11+
- Una cuenta en [Kalshi](https://kalshi.com) (verificada)
- Una cuenta de Telegram con acceso al canal APUESTA SEGURA CS2
- Git

## Setup paso a paso

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/reche-socialpro/telegram-kalshi-automation.git
cd telegram-kalshi-automation
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -e .
pip install pytest
```

### 2. Crear clave API de Kalshi

1. Entra en [kalshi.com/account/profile](https://kalshi.com/account/profile)
2. Baja hasta la seccion **API keys**
3. Haz click en **Create key**
4. Rellena:
   - **Nickname**: lo que quieras, por ejemplo `telegram-kalshi`
   - **Key type**: Ed25519 (recomendado)
   - **Public key**: dejalo vacio (Kalshi genera y descarga la clave privada)
   - **Permissions**: minimo "Read all data" + "Trade". "Full access" incluye transferencias, que el bot no necesita
5. Click en **Create**
6. Se descarga un archivo `.txt` con la clave privada. Muevelo a la carpeta `data/` del proyecto y renombralo a `.pem`:

```bash
# Windows (ajusta el nombre del archivo descargado)
copy %USERPROFILE%\Downloads\telegram-kalshi.txt data\telegram-kalshi.pem
# Linux/Mac
cp ~/Downloads/telegram-kalshi.txt data/telegram-kalshi.pem
```

7. Apunta el **API key id** que se muestra en pantalla (un UUID tipo `5e7ce7f3-a984-...`)

> **Seguridad**: la clave privada esta en `.gitignore`. No la subas a git ni la compartas.

### 3. Crear app de Telegram (API ID y Hash)

1. Entra en [my.telegram.org](https://my.telegram.org) con tu numero de telefono
   - Te llega un codigo **por Telegram** (no SMS)
   - Esa pagina a veces va lenta o da error 500. Reintenta si falla
2. Ve a **API development tools**
3. Si no tienes una app creada, rellena:
   - **App title**: lo que quieras (minimo 7 caracteres, sin la palabra "Telegram")
   - **Short name**: alfanumerico, 5-32 caracteres
   - **Platform**: "Bot / Server" u "Other"
4. Click en **Create application**
5. Apunta el **App api_id** (un numero) y el **App api_hash** (un string hexadecimal de 32 caracteres)

### 4. Configurar .env

```bash
copy .env.example .env
```

Edita `.env` con tus datos:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef0123456789abcdef0123456789
TELEGRAM_CHANNEL=-1002160464787
TELEGRAM_SESSION=data/telegram

KALSHI_ENV=production
KALSHI_API_KEY_ID=tu-api-key-id-aqui
KALSHI_PRIVATE_KEY_PATH=data/telegram-kalshi.pem

DRY_RUN=true
ALLOW_LIVE_TRADING=NO

STAKE_UNIT_USD=1.00
MAX_CONTRACTS_PER_ORDER=100
MAX_NOTIONAL_PER_ORDER_USD=100.00
ALLOWED_TICKERS=
DATABASE_PATH=data/orders.db
KALSHI_COMBO_COLLECTION=KXMVECROSSCATEGORY-R
```

> **DRY_RUN=true**: el bot parsea y resuelve señales contra mercados reales de Kalshi, pero NO envia ordenes. Dejalo asi hasta que estes seguro de que todo funciona.

### 5. Verificar autenticacion con Kalshi

```bash
python -m telegram_kalshi.cli check-auth
```

Deberia devolver un JSON con tu balance. Si da error, revisa `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` y `KALSHI_ENV`.

### 6. Primer login de Telegram (interactivo)

```bash
python -m telegram_kalshi.cli listen
```

La primera vez, Telethon te pedira:

1. **Phone number**: tu numero en formato internacional (`+34612345678`)
2. **Code**: un codigo que te llega por Telegram (no SMS)
3. **2FA password** (solo si tienes verificacion en dos pasos activada)

Despues de autenticarte se crea `data/telegram.session`. Las siguientes ejecuciones no piden credenciales.

El bot empezara a escuchar el canal. En DRY_RUN veras los mensajes procesados en consola sin enviar ordenes.

### 7. Tests

```bash
python -m pytest tests -v
```

47 tests cubriendo parser, modelos, store y processor.

## Comandos utiles

### Parsear una señal offline (sin red)

```bash
python -m telegram_kalshi.cli parse --message "BIG @1.77 (stake 10)"
```

### Procesar una señal contra mercados reales (DRY_RUN)

```bash
python -m telegram_kalshi.cli process --message "BIG @2.00 (stake 10)" --chat-id -1002160464787 --message-id 1001
```

### Consultar un mercado

```bash
python -m telegram_kalshi.cli check-market --ticker KXCS2GAME-26NOV191430BIGGL
```

## Arquitectura

```
src/telegram_kalshi/
  cli.py        - Punto de entrada (listen, parse, process, check-market, check-auth)
  listener.py   - Telethon: escucha NewMessage del canal con lock secuencial
  parser.py     - Regex sobre la primera linea de cada señal
  models.py     - Selection, Signal (precio, budget, contratos), payload Kalshi v2
  resolver.py   - Relaciona equipos con mercados CS2 abiertos via API publica
  processor.py  - Risk checks, dedup, preview, DRY_RUN gate, dispatch
  kalshi.py     - REST client con firma Ed25519/RSA
  store.py      - SQLite con PK (chat_id, message_id) y client_order_id unico
  config.py     - Settings desde .env
```

## Formato de señales del canal

```
EQUIPO @ODDS (stake CANTIDAD)
Texto explicativo opcional...
```

Ejemplos reales:
- `BIG @1.77 (stake 10)` - apuesta simple
- `Inner Circle Academy mapa 2 @1.72 (stake 10)` - apuesta a mapa especifico
- `BIG + GamerLegion @1.77 (stake 10)` - combinada (parlay)

## Seguridad

- `DRY_RUN=true` por defecto. Para operar en real hace falta `DRY_RUN=false` Y `ALLOW_LIVE_TRADING=YES` (exactamente "YES")
- `.env`, `data/`, `*.pem` y `*.session` estan en `.gitignore`
- El bot rechaza combinadas donde ambos equipos juegan el mismo partido
- Risk limits: `MAX_CONTRACTS_PER_ORDER` y `MAX_NOTIONAL_PER_ORDER_USD`
- No imprimas credenciales en logs
