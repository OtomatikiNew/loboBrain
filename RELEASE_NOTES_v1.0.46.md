# Release notes — Homeassistant Sports Club Dashboard API v1.0.46

## Objective

This version fixes the Home Assistant binary sensor state normalization for local / OK Cloud clubs where the backend may publish an OFF state as `false`, `0`, `closed`, `none`, `null`, or an empty value instead of the literal string `off`.

## Problem fixed

In v1.0.45 and earlier, court binary sensors were written using a strict comparison:

```python
"state": "off" if state == "off" else "on"
```

That meant values such as `false` were incorrectly stored in Home Assistant as `on`, while the raw value was still preserved in `meta_state`. This could produce inconsistent entities such as:

```yaml
state: on
brightness: 0
meta_state: "false"
```

As a result, dashboards and automations reading `binary_sensor.pista_1` could treat the court as active even when the backend was actually reporting an OFF state.

## New behavior

The add-on now normalizes incoming light states before writing them to Home Assistant. The following values are treated as OFF:

```text
off, false, 0, none, null, closed, ""
```

`dim` is treated as ON only when the received brightness is greater than 0.

## Files modified

- `homeassistant_club_dashboard_api/config.yaml`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`

## Compatibility

This change does not alter MQTT topics, stable entity names, friendly names, dashboard structure, door handling, or backend IDs. It only corrects how incoming light state values are converted to Home Assistant `on` / `off` binary sensor states.
