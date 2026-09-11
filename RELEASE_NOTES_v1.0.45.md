# Release notes — Homeassistant Sports Club Dashboard API v1.0.45

## Version objective

This version introduces a stable naming layer for the binary sensors created in Home Assistant by the add-on.

Until now, the add-on created Home Assistant entities directly using the internal identifiers received from SrLobo / OK Cloud / MQTT. For example:

* `binary_sensor.66`
* `binary_sensor.67`
* `binary_sensor.68`
* `binary_sensor.door33`
* `binary_sensor.door48`

This meant that dashboards and automations depended on internal IDs that could vary between clubs or installations. In one club, courts could appear as `binary_sensor.66`, `binary_sensor.67`, etc.; in another as `binary_sensor.70`, `binary_sensor.71`; and in another as `binary_sensor.72`, `binary_sensor.73`.

With this version, the add-on still internally uses the real IDs received from the backend/MQTT, but now exposes stable and predictable entities in Home Assistant:

* `binary_sensor.pista_1`
* `binary_sensor.pista_2`
* `binary_sensor.pista_3`
* ...
* `binary_sensor.puerta_1`
* `binary_sensor.puerta_2`
* ...

The original `friendly_name` is not modified. This means an entity may internally be named `binary_sensor.pista_1`, while still being displayed in Home Assistant as `Platz 1/ Sport Treff Rorschach`, `Red Court`, `Blue Court`, `Main Door`, etc.

## Previous behavior

Before this version, courts were published in Home Assistant using the internal ID received from the backend. Example:

```text
backend/MQTT id 66 -> binary_sensor.66
backend/MQTT id 67 -> binary_sensor.67
backend/MQTT id 68 -> binary_sensor.68
```

Doors were published using the `door` prefix followed by the internal ID:

```text
backend/MQTT door id 33 -> binary_sensor.door33
backend/MQTT door id 48 -> binary_sensor.door48
```

This forced users to modify blueprints, automations, and dashboards every time a club used different IDs.

## New behavior

The add-on now builds a mapping table during startup, based on the lists of courts and doors received from the backend.

For courts:

```text
first court sensor received  -> binary_sensor.pista_1
second court sensor received -> binary_sensor.pista_2
third court sensor received  -> binary_sensor.pista_3
...
```

For doors:

```text
first door received  -> binary_sensor.puerta_1
second door received -> binary_sensor.puerta_2
third door received  -> binary_sensor.puerta_3
...
```

Example:

```text
backend/MQTT id 66 -> binary_sensor.pista_1
backend/MQTT id 67 -> binary_sensor.pista_2
backend/MQTT id 68 -> binary_sensor.pista_3
backend/MQTT id 69 -> binary_sensor.pista_4

backend/MQTT door id 33 -> binary_sensor.puerta_1
backend/MQTT door id 48 -> binary_sensor.puerta_2
```

## What does NOT change

This version does not change:

* The MQTT topics used by the backend.
* The real IDs received through MQTT.
* The `friendly_name` shown in Home Assistant.
* The `on` / `off` state logic.
* The brightness and `meta_state` attributes of the courts.
* The `device_class` of courts (`light`).
* The `device_class` of doors (`door`).
* The integration with SrLobo / OK Cloud.
* The state update logic back to the backend.

The change mainly affects how the entity is named inside Home Assistant.

## Modified files

### `homeassistant_club_dashboard_api/config.yaml`

The add-on version has been updated:

```diff
-version: "1.0.44"
+version: "1.0.45"
```

### `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`

A stable mapping layer has been added between internal IDs and the entity names exposed in Home Assistant.

## New internal mapping tables

Internal structures were added to translate between received IDs and stable Home Assistant entities:

```python
LIGHT_ENTITY_MAP = {}
LIGHT_ENTITY_REVERSE_MAP = {}
DOOR_ENTITY_MAP = {}
DOOR_ENTITY_REVERSE_MAP = {}
```

These tables allow the add-on to internally receive or process IDs such as `66`, `67`, `33`, `48`, while publishing or updating entities such as `pista_1`, `pista_2`, `puerta_1`, `puerta_2` in Home Assistant.

## New helper functions

Helper functions were added to centralize entity name translation:

```python
def get_stable_light_entity_id(light_id):
    return LIGHT_ENTITY_MAP.get(str(light_id), str(light_id))
```

Returns the stable court name. Example:

```text
66 -> pista_1
67 -> pista_2
```

```python
def get_original_light_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return LIGHT_ENTITY_REVERSE_MAP.get(suffix, suffix)
```

Allows recovery of the original internal ID when sending updates back to the backend.

```python
def get_stable_door_entity_id(door_id):
    return DOOR_ENTITY_MAP.get(str(door_id), 'door{}'.format(door_id))
```

Returns the stable door name. Example:

```text
33 -> puerta_1
48 -> puerta_2
```

```python
def get_original_door_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return DOOR_ENTITY_REVERSE_MAP.get(suffix, suffix.replace('door', ''))
```

Allows recovery of the original door ID when sending updates back to the backend.

## Changes in court sensor creation

Previously, the Home Assistant entity directly used the court ID:

```python
light_id = light[1]
```

Now a stable mapping is created while iterating through the court list:

```python
for index, light in enumerate(lights, start=1):
    stable_entity_id = f"pista_{index}"
    LIGHT_ENTITY_MAP[str(light[1])] = stable_entity_id
    LIGHT_ENTITY_MAP[str(light[0])] = stable_entity_id
    LIGHT_ENTITY_REVERSE_MAP[stable_entity_id] = str(light[0])
```

Then, when creating the entity in Home Assistant:

```python
light_id = get_stable_light_entity_id(light[1])
```

Result:

```text
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.pista_3
...
```

## Changes in court sensor updates

Previously, when an MQTT update arrived, the entity was updated directly using the received ID:

```python
data_from_mqtt = court_id
```

Now the received ID is translated into the stable name:

```python
data_from_mqtt = get_stable_light_entity_id(court_id)
```

So if an update arrives for internal court `66`, the add-on updates:

```text
binary_sensor.pista_1
```

instead of:

```text
binary_sensor.66
```

## Changes in door sensor creation

Previously, doors were created as:

```python
entity_id = "door{}".format(door[1])
```

Now a stable mapping is created while iterating through the door list:

```python
for index, door in enumerate(doors, start=1):
    stable_entity_id = f"puerta_{index}"
    DOOR_ENTITY_MAP[str(door[1])] = stable_entity_id
    DOOR_ENTITY_MAP[str(door[0])] = stable_entity_id
    DOOR_ENTITY_REVERSE_MAP[stable_entity_id] = str(door[1])
```

Then:

```python
stable_door_entity_id = get_stable_door_entity_id(door[1])
```

Result:

```text
binary_sensor.puerta_1
binary_sensor.puerta_2
...
```

## Changes in door sensor updates

Previously, when a door update arrived, the following entity was updated:

```python
data_from_mqtt = "door{}".format(door_id)
```

Now the received ID is translated into the stable name:

```python
data_from_mqtt = get_stable_door_entity_id(door_id)
```

So if an update arrives for internal door `33`, the add-on updates:

```text
binary_sensor.puerta_1
```

instead of:

```text
binary_sensor.door33
```

## Changes in updates sent from Home Assistant back to the backend

The reverse flow was also updated.

Previously, when Home Assistant sent a court update, the code extracted the ID directly from the entity name:

```python
id = entity_id.split('.')[1]
```

This worked for `binary_sensor.66`, but not for `binary_sensor.pista_1`.

Now it uses:

```python
id = get_original_light_id(entity_id)
```

This allows Home Assistant to work with `binary_sensor.pista_1` while the backend still receives the correct internal ID.

For doors, previously:

```python
id = entity_id[len('binary_sensor.door'):]
```

Now:

```python
id = get_original_door_id(entity_id)
```

This allows Home Assistant to work with `binary_sensor.puerta_1` while the backend still receives the correct internal ID.

## Impact on dashboards and automations

From this version onward, dashboards and automations can be configured using stable and generic entities:

```yaml
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.pista_3
...
binary_sensor.puerta_1
binary_sensor.puerta_2
```

This avoids manually adapting dashboards or blueprints whenever a club uses different internal IDs.

Example blueprint:

```yaml
sensor_presencia: binary_sensor.pista_1
```

Example dashboard:

```yaml
sensor: binary_sensor.pista_1
```

## Compatibility

The change maintains full backend compatibility because the internal IDs still exist inside the add-on and are used whenever it is necessary to communicate state changes back to SrLobo / OK Cloud.

The difference is that Home Assistant is no longer exposed to those internal IDs.

## Migration note

After installing this version, old entities such as:

```text
binary_sensor.66
binary_sensor.67
binary_sensor.door33
```

will no longer be the primary entities expected by the new dashboard.

Dashboards and automations should be updated to use:

```text
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.puerta_1
```

as appropriate.

## Review note

During the file comparison for this version, actual changes were detected in:

* `homeassistant_club_dashboard_api/config.yaml`
* `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`

A `__pycache__` file also appeared inside the modified ZIP package. This file is not required for add-on functionality and can be removed before publishing the final version to keep the package clean. 


# Release notes — Homeassistant Sports Club Dashboard API v1.0.45

## Objetivo de la versión

Esta versión introduce una capa de nombres estables para los sensores binarios creados en Home Assistant por el add-on.

Hasta ahora, el add-on creaba las entidades de Home Assistant usando directamente los identificadores internos recibidos desde SrLobo / OK Cloud / MQTT. Por ejemplo:

- `binary_sensor.66`
- `binary_sensor.67`
- `binary_sensor.68`
- `binary_sensor.door33`
- `binary_sensor.door48`

Esto hacía que el dashboard y las automatizaciones dependieran de IDs internos que pueden cambiar entre clubes o instalaciones. En un club las pistas podían aparecer como `binary_sensor.66`, `binary_sensor.67`, etc.; en otro como `binary_sensor.70`, `binary_sensor.71`; y en otro como `binary_sensor.72`, `binary_sensor.73`.

Con esta versión, el add-on sigue usando internamente los IDs reales que recibe del backend/MQTT, pero expone en Home Assistant entidades estables y previsibles:

- `binary_sensor.pista_1`
- `binary_sensor.pista_2`
- `binary_sensor.pista_3`
- ...
- `binary_sensor.puerta_1`
- `binary_sensor.puerta_2`
- ...

El `friendly_name` original no se modifica. Es decir, una entidad puede llamarse internamente `binary_sensor.pista_1`, pero seguir mostrándose en Home Assistant como `Platz 1/ Sport Treff Rorschach`, `Pista roja`, `Pista azul`, `Puerta principal`, etc.

## Comportamiento anterior

Antes de esta versión, las pistas se publicaban en Home Assistant con el ID interno recibido del backend. Por ejemplo:

```text
backend/MQTT id 66 -> binary_sensor.66
backend/MQTT id 67 -> binary_sensor.67
backend/MQTT id 68 -> binary_sensor.68
```

Las puertas se publicaban usando el prefijo `door` seguido del ID interno:

```text
backend/MQTT door id 33 -> binary_sensor.door33
backend/MQTT door id 48 -> binary_sensor.door48
```

Esto obligaba a modificar blueprints, automatizaciones y dashboards cada vez que un club tenía IDs diferentes.

## Comportamiento nuevo

Ahora el add-on construye una tabla de correspondencia al arrancar, a partir de las listas de pistas y puertas que recibe del backend.

Para pistas:

```text
primer sensor de pista recibido  -> binary_sensor.pista_1
segundo sensor de pista recibido -> binary_sensor.pista_2
tercer sensor de pista recibido  -> binary_sensor.pista_3
...
```

Para puertas:

```text
primera puerta recibida  -> binary_sensor.puerta_1
segunda puerta recibida  -> binary_sensor.puerta_2
tercera puerta recibida  -> binary_sensor.puerta_3
...
```

Ejemplo:

```text
backend/MQTT id 66 -> binary_sensor.pista_1
backend/MQTT id 67 -> binary_sensor.pista_2
backend/MQTT id 68 -> binary_sensor.pista_3
backend/MQTT id 69 -> binary_sensor.pista_4

backend/MQTT door id 33 -> binary_sensor.puerta_1
backend/MQTT door id 48 -> binary_sensor.puerta_2
```

## Qué NO cambia

Esta versión no cambia:

- Los topics MQTT usados por el backend.
- Los IDs reales recibidos por MQTT.
- El `friendly_name` mostrado en Home Assistant.
- La lógica de estados `on` / `off`.
- Los atributos de brillo (`brightness`) y `meta_state` de las pistas.
- El `device_class` de las pistas (`light`).
- El `device_class` de las puertas (`door`).
- La integración con SrLobo / OK Cloud.
- La lógica de actualización de estados hacia el backend.

El cambio afecta principalmente a cómo se nombra la entidad expuesta en Home Assistant.

## Archivos modificados

### `homeassistant_club_dashboard_api/config.yaml`

Se actualiza la versión del add-on:

```diff
-version: "1.0.44"
+version: "1.0.45"
```

### `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`

Se añade una capa de mapeo estable entre los IDs internos y los nombres de entidad expuestos en Home Assistant.

## Nuevas tablas internas de mapeo

Se han añadido estructuras internas para traducir entre IDs recibidos y entidades estables de Home Assistant:

```python
LIGHT_ENTITY_MAP = {}
LIGHT_ENTITY_REVERSE_MAP = {}
DOOR_ENTITY_MAP = {}
DOOR_ENTITY_REVERSE_MAP = {}
```

Estas tablas permiten que el add-on reciba o procese internamente IDs como `66`, `67`, `33`, `48`, pero publique o actualice en Home Assistant entidades como `pista_1`, `pista_2`, `puerta_1`, `puerta_2`.

## Nuevas funciones añadidas

Se han añadido funciones auxiliares para centralizar la traducción de nombres:

```python
def get_stable_light_entity_id(light_id):
    return LIGHT_ENTITY_MAP.get(str(light_id), str(light_id))
```

Devuelve el nombre estable de una pista. Por ejemplo:

```text
66 -> pista_1
67 -> pista_2
```

```python
def get_original_light_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return LIGHT_ENTITY_REVERSE_MAP.get(suffix, suffix)
```

Permite recuperar el ID original cuando se necesita enviar una actualización de vuelta al backend.

```python
def get_stable_door_entity_id(door_id):
    return DOOR_ENTITY_MAP.get(str(door_id), 'door{}'.format(door_id))
```

Devuelve el nombre estable de una puerta. Por ejemplo:

```text
33 -> puerta_1
48 -> puerta_2
```

```python
def get_original_door_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return DOOR_ENTITY_REVERSE_MAP.get(suffix, suffix.replace('door', ''))
```

Permite recuperar el ID original de una puerta cuando se necesita enviar una actualización de vuelta al backend.

## Cambios en la creación de sensores de pista

Antes, la entidad de Home Assistant usaba directamente el ID de la pista:

```python
light_id = light[1]
```

Ahora se crea una correspondencia estable al recorrer la lista de pistas:

```python
for index, light in enumerate(lights, start=1):
    stable_entity_id = f"pista_{index}"
    LIGHT_ENTITY_MAP[str(light[1])] = stable_entity_id
    LIGHT_ENTITY_MAP[str(light[0])] = stable_entity_id
    LIGHT_ENTITY_REVERSE_MAP[stable_entity_id] = str(light[0])
```

Después, al crear la entidad en Home Assistant, se usa:

```python
light_id = get_stable_light_entity_id(light[1])
```

Resultado:

```text
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.pista_3
...
```

## Cambios en la actualización de sensores de pista

Antes, cuando llegaba una actualización MQTT, se actualizaba directamente la entidad basada en el ID recibido:

```python
data_from_mqtt = court_id
```

Ahora se traduce el ID recibido al nombre estable:

```python
data_from_mqtt = get_stable_light_entity_id(court_id)
```

Así, si llega una actualización para la pista interna `66`, el add-on actualiza:

```text
binary_sensor.pista_1
```

en vez de:

```text
binary_sensor.66
```

## Cambios en la creación de sensores de puerta

Antes, las puertas se creaban como:

```python
entity_id = "door{}".format(door[1])
```

Ahora se crea una correspondencia estable al recorrer la lista de puertas:

```python
for index, door in enumerate(doors, start=1):
    stable_entity_id = f"puerta_{index}"
    DOOR_ENTITY_MAP[str(door[1])] = stable_entity_id
    DOOR_ENTITY_MAP[str(door[0])] = stable_entity_id
    DOOR_ENTITY_REVERSE_MAP[stable_entity_id] = str(door[1])
```

Después se usa:

```python
stable_door_entity_id = get_stable_door_entity_id(door[1])
```

Resultado:

```text
binary_sensor.puerta_1
binary_sensor.puerta_2
...
```

## Cambios en la actualización de sensores de puerta

Antes, cuando llegaba una actualización de puerta, se actualizaba:

```python
data_from_mqtt = "door{}".format(door_id)
```

Ahora se traduce el ID recibido al nombre estable:

```python
data_from_mqtt = get_stable_door_entity_id(door_id)
```

Así, si llega una actualización para la puerta interna `33`, el add-on actualiza:

```text
binary_sensor.puerta_1
```

en vez de:

```text
binary_sensor.door33
```

## Cambios en actualizaciones desde Home Assistant hacia el backend

También se ha ajustado el flujo inverso.

Antes, cuando Home Assistant enviaba una actualización de una pista, el código extraía el ID directamente desde el nombre de entidad:

```python
id = entity_id.split('.')[1]
```

Esto funcionaba con `binary_sensor.66`, pero no con `binary_sensor.pista_1`.

Ahora se usa:

```python
id = get_original_light_id(entity_id)
```

Esto permite que Home Assistant trabaje con `binary_sensor.pista_1`, pero que el backend siga recibiendo el ID interno correcto.

Para puertas, antes se hacía:

```python
id = entity_id[len('binary_sensor.door'):]
```

Ahora se usa:

```python
id = get_original_door_id(entity_id)
```

Esto permite que Home Assistant trabaje con `binary_sensor.puerta_1`, pero que el backend siga recibiendo el ID interno correcto.

## Impacto en dashboards y automatizaciones

A partir de esta versión, los dashboards y automatizaciones pueden configurarse con entidades genéricas y estables:

```yaml
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.pista_3
...
binary_sensor.puerta_1
binary_sensor.puerta_2
```

Esto evita tener que adaptar manualmente el dashboard o los blueprints cuando un club usa IDs internos diferentes.

Ejemplo de blueprint:

```yaml
sensor_presencia: binary_sensor.pista_1
```

Ejemplo de dashboard:

```yaml
sensor: binary_sensor.pista_1
```

## Compatibilidad

El cambio mantiene la compatibilidad funcional con el backend porque los IDs internos siguen existiendo dentro del add-on y se usan cuando es necesario comunicar estados de vuelta a SrLobo / OK Cloud.

La diferencia es que Home Assistant ya no queda expuesto a esos IDs internos.

## Nota de migración

Después de instalar esta versión, las entidades antiguas como:

```text
binary_sensor.66
binary_sensor.67
binary_sensor.door33
```

dejarán de ser las entidades principales esperadas por el dashboard nuevo.

El dashboard y las automatizaciones deberían actualizarse para usar:

```text
binary_sensor.pista_1
binary_sensor.pista_2
binary_sensor.puerta_1
```

según corresponda.

## Nota de revisión

En la comparación de archivos realizada para esta versión se han detectado cambios reales en:

- `homeassistant_club_dashboard_api/config.yaml`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`

También aparece un archivo `__pycache__` añadido en el ZIP modificado. Este archivo no es necesario para el funcionamiento del add-on y puede eliminarse antes de subir la versión final al repositorio si se quiere mantener el paquete limpio.
