# Traspaso seguro: Telegram → Kalshi (Apuesta Segura CS2)

## Instrucción para el próximo agente

Lee este documento completo antes de modificar o ejecutar el proyecto. Continúa en modo lectura o `DRY_RUN=true`. No envíes órdenes reales ni de demo, no crees mercados combinados y no cambies los flags de producción sin una instrucción explícita del usuario. No solicites ni imprimas credenciales en logs o respuestas.

## Objetivo

Escuchar nuevas señales del canal privado de Telegram **APUESTA SEGURA CS2 | SOCIALPRO** y convertirlas en órdenes límite YES en Kalshi.

- URL: `https://web.telegram.org/k/#-2160464787`
- ID configurado para Telethon: `-1002160464787`
- Directorio: `C:\Users\reche\Documents\Projects\telegram-kalshi-automation`
- Python: 3.11
- Entorno virtual ya creado: `.venv`
- No se ha creado `.env` ni se han almacenado credenciales.

## Estado actual

La base funcional está implementada. El canal ya no se procesa con el formato genérico `KALSHI BUY YES`; el parser usa el formato real observado en Telegram.

No hay una suite de tests persistida. Las verificaciones realizadas fueron compilación, comandos CLI y scripts inline con fixtures, respuestas simuladas y consultas públicas reales.

## Arquitectura

- `src/telegram_kalshi/listener.py`: Telethon, escucha `NewMessage` del canal. Usa la API de Telegram; no hace scraping de Telegram Web. No usa webhook.
- `src/telegram_kalshi/parser.py`: interpreta la primera línea de las señales reales.
- `src/telegram_kalshi/models.py`: modelo de señal, cálculo de precio, presupuesto, contratos y payload V2 de Kalshi.
- `src/telegram_kalshi/resolver.py`: relaciona equipos con mercados CS2 abiertos, con caché de 30 segundos.
- `src/telegram_kalshi/processor.py`: riesgo, resolución, preview, deduplicación, combinadas y envío.
- `src/telegram_kalshi/kalshi.py`: cliente REST, consultas públicas, autenticación Ed25519/RSA, creación de combinadas y órdenes.
- `src/telegram_kalshi/store.py`: SQLite, una fila por mensaje procesado.
- `src/telegram_kalshi/cli.py`: comandos `listen`, `parse`, `process`, `check-market`, `check-auth`.
- `src/telegram_kalshi/config.py`: configuración y bloqueos de producción.
- `.env.example`: plantilla sin secretos.
- `.gitignore`: excluye `.env`, sesiones, claves, base de datos y entorno virtual.

## Formatos reconocidos

```text
YOUNGLINGS @1.68 (stake 10)
Inner Circle Academy mapa 2 @1.72 (stake 10)
Hype Tech + Spirit @2.31 (stake 10)
G2 Ares mapa 2 @2.00 (stake 10)
BIG + GamerLegion @1.77 (stake 10)
```

- `+` indica una combinada, no apuestas independientes.
- `mapa N` selecciona el mercado de ganador del mapa.
- Se admiten de 1 a 10 selecciones.
- El parser mira la primera línea y permite texto explicativo posterior.
- Mensajes sin el patrón cuota + stake se ignoran. En particular, la recomendación posterior `Os recomiendo ... Polymarket/Kalshi ... @1.90` no genera otra orden ni actualiza la anterior.

## Conversión de cuota y stake

La cuota decimal se interpreta como precio máximo, no como precio garantizado:

```text
precio implícito = 1 / cuota
precio límite = floor(precio implícito al tick de 0.01 USD)
```

Ejemplos:

- `@1.77` → `0.56 USD`
- `@1.68` → `0.59 USD`
- `@2.00` → `0.50 USD`

Todos los mercados CS2 comprobados tenían `price_level_structure=linear_cent` y step `0.01`. Si se amplía a otros mercados, leer `price_ranges` en lugar de asumir siempre un céntimo.

Configuración de stake:

```env
STAKE_UNIT_USD=1.00
```

Con este valor, `stake 10` significa un presupuesto máximo de 10 USD, no 10 contratos:

```text
presupuesto = stake * STAKE_UNIT_USD
contratos = floor(presupuesto / precio límite)
coste máximo = contratos * precio límite
```

El usuario todavía no ha confirmado cuánto debe valer un punto de stake. Mantener `1.00` y límites pequeños hasta confirmarlo.

## Resolución de mercados

Se consultan los endpoints públicos de eventos con `with_nested_markets=true`:

- Partido: series `KXCS2GAME`
- Mapa: series `KXCS2MAP`

Reglas de seguridad:

- Solo eventos abiertos y mercados `active`.
- Coincidencia exacta normalizada con `yes_sub_title`; no hay fuzzy matching.
- La normalización ignora mayúsculas, acentos y separadores.
- Alias actuales: `Spirit` ↔ `Team Spirit`.
- Si no hay candidato o hay varios partidos posibles, se rechaza la señal.
- CS2 no se confunde con Dota 2 u otros esports porque la serie se filtra.
- No se pueden combinar selecciones del mismo `event_ticker`.
- `ALLOWED_TICKERS`, si tiene valores, se aplica a todos los componentes.

No añadir aliases o coincidencias aproximadas sin fixtures y revisión; un nombre parecido puede seleccionar otro partido.

## Órdenes y combinadas

Las señales se convierten en compras YES:

```json
{
  "ticker": "...",
  "side": "bid",
  "count": "17",
  "price": "0.5600",
  "time_in_force": "immediate_or_cancel",
  "self_trade_prevention_type": "taker_at_cross",
  "client_order_id": "tg-..."
}
```

- Endpoint actual: `POST /trade-api/v2/portfolio/events/orders`.
- Se usa `immediate_or_cancel`; una orden aceptada puede no ejecutarse. No confundir aceptación con fill.
- No se implementa GTC, venta, cancelación, amend ni seguimiento por WebSocket.
- No se reintenta automáticamente un POST de orden.

Para combinadas:

1. Resolver cada selección a `{market_ticker, event_ticker, side: "yes"}`.
2. En modo real, llamar a `POST /multivariate_event_collections/{collection_ticker}`.
3. Obtener `market_ticker` de la respuesta.
4. Enviar una única orden sobre ese ticker.

Colección configurada:

```env
KALSHI_COMBO_COLLECTION=KXMVECROSSCATEGORY-R
```

La colección existe en producción y se comprobó públicamente. La creación autenticada de una combinada solo se ha probado con respuesta simulada; no se ha ejecutado contra demo o producción.

En `DRY_RUN`, una combinada genera un preview con `selected_markets`, pero no crea el mercado y por tanto no tiene todavía un ticker final.

## Safeguards existentes

1. `DRY_RUN=true` por defecto.
2. Producción con escritura exige simultáneamente:
   - `KALSHI_ENV=production`
   - `DRY_RUN=false`
   - `ALLOW_LIVE_TRADING=YES`
3. `MAX_CONTRACTS_PER_ORDER=100`.
4. `MAX_NOTIONAL_PER_ORDER_USD=100.00`.
5. `STAKE_UNIT_USD=1.00` por defecto.
6. Rechazo si el presupuesto no alcanza un contrato.
7. Lista opcional `ALLOWED_TICKERS`.
8. Rechazo de mercados ausentes, inactivos o ambiguos.
9. Rechazo de combinadas del mismo evento.
10. SQLite con clave primaria `(chat_id, message_id)` y `client_order_id` único.
11. `client_order_id` determinista: UUID5 de `telegram:{chat_id}:{message_id}` con prefijo `tg-`.
12. El mismo mensaje no debe generar dos órdenes aunque se procese dos veces en la misma instalación.
13. Los fallos de envío quedan `failed`; no se reintentan automáticamente.
14. No hay credenciales en el código ni en `.env.example`.
15. Claves privadas Ed25519 y RSA soportadas; la ruta firmada excluye query params.
16. Timeout HTTP de 15 segundos.
17. El listener procesa mensajes secuencialmente mediante un lock.

## Limitaciones importantes antes de producción

- El login real de Telethon y la recepción en vivo no se han probado con credenciales.
- No se ha enviado ninguna orden real ni de demo.
- La creación autenticada de combinadas no se ha probado contra Kalshi.
- No hay reconciliación tras un crash entre el POST y la escritura del resultado en SQLite. No reintentar ciegamente: el `client_order_id` no garantiza deduplicación después de que la orden original haya finalizado. Consultar/reconciliar primero.
- Un mensaje que queda en `processing` tras un crash requiere revisión manual.
- No hay límite diario, límite de pérdidas, kill switch externo, control de antigüedad de la señal ni notificaciones de error.
- No hay seguimiento de fills ni posiciones.
- No se compara el precio con el order book antes de enviar; el precio límite e IOC limitan el precio, no garantizan ejecución.
- La cuota específica de Kalshi publicada en un mensaje posterior no se aplica; se usa la cuota del mensaje que contiene `stake`.
- Demo y producción tienen datos y credenciales separados. Para resolver señales contra mercados reales sin operar, usar producción + `DRY_RUN=true`.
- No hay webhook. Telethon es apropiado porque el canal es privado y no se ha confirmado que un bot pueda añadirse como administrador.

## Configuración

```bash
cd /c/Users/reche/Documents/Projects/telegram-kalshi-automation
cp .env.example .env
```

Completar localmente:

```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_CHANNEL=-1002160464787
TELEGRAM_SESSION=data/telegram

KALSHI_ENV=demo
KALSHI_API_KEY_ID=
KALSHI_PRIVATE_KEY_PATH=
KALSHI_COMBO_COLLECTION=KXMVECROSSCATEGORY-R

DRY_RUN=true
ALLOW_LIVE_TRADING=NO

STAKE_UNIT_USD=1.00
MAX_CONTRACTS_PER_ORDER=100
MAX_NOTIONAL_PER_ORDER_USD=100.00
ALLOWED_TICKERS=
DATABASE_PATH=data/orders.db
```

Telegram requiere API ID/hash de `my.telegram.org` y una cuenta miembro del canal. La primera ejecución pedirá teléfono/código. Kalshi requiere Key ID y clave privada del mismo entorno. No compartir secretos en chat.

## Comandos seguros

Interpretar sin red ni orden:

```bash
.venv/Scripts/python -m telegram_kalshi parse --message "BIG + GamerLegion @1.77 (stake 10)"
```

Resolver contra mercados reales sin operar:

```bash
KALSHI_ENV=production DRY_RUN=true .venv/Scripts/python -m telegram_kalshi process --message "Nuclear TigeRES @2.00 (stake 10)" --chat-id -1002160464787 --message-id 1001
```

Escuchar Telegram respetando el `DRY_RUN` configurado:

```bash
.venv/Scripts/python -m telegram_kalshi listen
```

Comprobaciones:

```bash
.venv/Scripts/python -m compileall -q src
.venv/Scripts/python -m pip check
```

`check-auth` consulta balance con firma. `check-market` es lectura pública. Ninguno debe crear órdenes.

## Verificaciones ya realizadas

- Instalación editable y dependencias correctas; `pip check` sin errores.
- Compilación de todos los módulos.
- Siete señales reales del canal parseadas con precios y cantidades esperados.
- Recomendación posterior sin stake ignorada.
- Apuestas simples, `mapa 2` y combinadas verificadas con fixtures.
- Rechazo de combinadas del mismo evento.
- Deduplicación: segundo procesamiento del mismo mensaje devuelve `duplicate` y mantiene una sola fila.
- Firma Ed25519 y RSA verificada localmente.
- Endpoint V2 y respuestas de orden/combinada verificados con HTTP simulado.
- Consulta pública real a Kalshi completada.
- Resolución pública real verificada en `DRY_RUN` para:
  - `KXCS2GAME-26NOV210400HTNTR-NTR`
  - `KXCS2MAP-26NOV210400HTNTR-2-NTR`
  - combinada con el anterior y `KXCS2GAME-26NOV200700HTLC-LC`
- Ninguna llamada real de escritura fue efectuada.

## Orden recomendado para continuar

1. No cambiar flags; ejecutar `parse` y `process` en `DRY_RUN`.
2. Añadir tests persistentes para parser, resolver, riesgo, deduplicación, fallos y combinadas antes de refactorizar.
3. Confirmar con el usuario el valor de `STAKE_UNIT_USD` y si la cuota posterior específica de Kalshi debe sustituir la inicial.
4. Probar Telethon en `DRY_RUN` y comprobar que el ID del evento coincide con la clave SQLite.
5. Añadir observabilidad y reconciliación segura antes de reintentos automáticos.
6. Probar primero una orden simple en demo con un mercado válido de ese entorno, revisando respuesta, fill y `remaining_count`.
7. Probar combinadas solo en demo y con una colección válida para demo; no asumir que los tickers/colecciones de producción existen allí.
8. Añadir límites agregados, seguimiento de fills y procedimiento de recuperación.
9. Solicitar una decisión explícita del usuario antes de cualquier escritura en producción.

## Referencias oficiales

- Autenticación: `https://docs.kalshi.com/getting_started/api_keys`
- Crear órdenes V2: `https://docs.kalshi.com/getting_started/quick_start_create_order`
- Especificación REST: `https://docs.kalshi.com/openapi.yaml`
