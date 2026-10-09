---
name: home-assistant-mcp
description: Use when reading or controlling Home Assistant through the home_assistant MCP server, including entities, areas, automations, scripts, helpers, dashboards, history, logs and updates.
---

# home-assistant-mcp

Reach this server through bifrost-gateway (see local-environment): `listToolFiles`, then `readToolFile` on `servers/home_assistant.pyi`, then `executeToolCode`. Read the stub once per session; it has about 100 tools. Results come back as dicts or JSON strings, so wrap prints in `str()` and index defensively.

Expect maintenance and debugging work here (reviewing config, traces, logs, integrations and updates) more than day-to-day device operation, so reach for the read tools and the debugging patterns first.

## Environment (checked 2026-10-06)

- Home Assistant Core 2026.6.0, **Container install** (Docker in LXC 122) at `http://10.1.1.22:8443`. There is no Supervisor, so Apps and Supervisor snapshots do not apply. Do not rely on `ha_get_app`, `ha_manage_app` or `ha_manage_backup` snapshots without testing first.
- The MCP server itself (ha-mcp 8.3.0) runs in Docker on LXC 130. Hosting details are in `Library/AI/Wiki – AI – MCP Server Stack.md`. Never print the access token.
- Timezone `Pacific/Auckland`. Timestamps in tool results are converted to local time, but history query boundaries stay in UTC.
- Scale: 1,746 entities, 151 automations, 24 scripts, 17 areas, 2 floors, 1 label (`timers`). Dashboards are storage mode (3 dashboards, 44 resources, HACS 2.0.5 with 69 repositories), so custom cards are in use.
- 145 config entries, 113 loaded. The 32 that are not loaded are mostly ignored or disabled discoveries, not faults.
- The recorder is sqlite, about 2.2 GB. Keep history queries narrow.
- The host also has vlan20, vlan30 and vlan40 interfaces. The Crow alarm IP module is at 10.1.30.51.

## Layout

| Floor | Areas (area_id) |
|---|---|
| Downstairs (level 0) | Back Yard (`back_yard`), Backend (`backend`), Bathroom Downstairs (`bathroom_2`), Hallway (`downstairs`), Office (`office`), TV Room (`tv_room`) |
| Upstairs (level 1) | Bathroom (`bathroom`), Bedroom (`bedroom`), Celeste (`celeste`), Entrance (`entrance`), Eve (`eve`), Front Yard (`front_yard`), Kitchen (`kitchen`), Lounge (`lounge`), Master Bedroom (`master_bedroom`) |
| No floor | AppleTV (`appletv`), Offsite (`offsite`) |

Quirks: `master_bedroom` is the one in use and `bedroom` and `appletv` hold no entities. The area id `downstairs` is the Hallway. `backend` holds about 250 infrastructure entities (Proxmox, disks, LXCs). People are Tim, Sonya, Celeste, Eve and Guest.

## Integrations that matter

- **Zigbee:** Zigbee2MQTT over the MQTT broker at 10.1.1.25, with an SLZB-06M coordinator (smlight integration). The ZHA entry is ignored, so use the Z2M patterns in the best-practices guide, not the ZHA ones. Matter and Thread are loaded (Nanoleaf bulbs via homekit_controller).
- **Lighting and switching:** Shelly, Tapo light strip, Adaptive Lighting (entries for Celeste, Master Bedroom, Office and a general one), Wemo plugs via homekit_controller, HomeKit bridge (`HASS Bridge:21064`).
- **Entertainment:** Sonos, Apple TV, PS4 (PSN entry is not loaded).
- **Security and cameras:** Crow alarm (`crowipmodule`), Frigate at 10.1.1.28:5000, Hikvision camera, WebRTC Camera.
- **Appliances:** Bosch dishwasher (home_connect and homeconnect_ws).
- **Infrastructure:** Proxmox VE integration (creates the `button.lxc_*` entities), NUT UPS at 10.1.1.20:3493, AdGuard at 10.1.1.23, Synology DSM (calliope, nearline), Wake on LAN (Synology, Mac Mini).
- **Housekeeping:** Pushover, mobile_app (family phones plus Tim's Macs), scheduler, watchman, battery_notes, backup, auto_backup, systemmonitor, ESPHome Bluetooth proxy.
- **Local feeds:** weather (met, metservice_weather, openweathermaphistory, open_meteo), ferry times (gtfs2), waste collection (auckland_waste, waste_collection_schedule).
- **Helpers:** many template helpers prefixed `irrigation_`, group helpers (Doors & Windows, Lounge Lamps, Motion Sensors, TV Room Lights, all_lights, outside_lights, smoke_detectors, bathroom_switches).

## Naming conventions (observed, follow them for new config)

- **Device entities:** type prefix, then brand or place: `lightbulb_hue_stairwell`, `lightswitch_shelly_sidepath`, `smartplug_office`, `watervalve_sprayzone`, `temperature_bathroom`, `smoke_roof`, `motion_stairwell`, `door_bathroom`, `window_master_bedroom`, `lux_office`.
- **Helpers:** feature prefix: `irrigation_*`, `ups_*`, `dogwalk_*`. Timers carry the `timers` label.
- **Automation and script names:** `Area or Topic – Subject – Trigger: Action`, with an en dash and capitalised state words, for example `Bathroom – Humidity RISE: Shower ACTIVE` and `Power Outage – Power OFF 2min: Shutdown LXCs`. Topics in use include Alarm, Security, Irrigation, Entertainment, Lounge, Bathroom, Bathroom2, Office, Kitchen, Location, Dogwalk, Maintenance, Network, Proxmox, Power Outage and Lighting.
- **Retired automations** are kept disabled with an `OLD <Mon YYYY>` suffix instead of being deleted.
- **Automation entity IDs do not follow current names.** Examples: `automation.automation_11` is "Alarm – Disarm if someone arrives home", `automation.new_automation_2` is "Security – Away – Door or Window open". Always find automations with `ha_search` and read the entity ID from the result. Never guess an ID from a name.

## Writing config

The write tools (`ha_config_set_automation`, `_script`, `_scene`, `_helper`, `_dashboard`) are gated by the server's best-practices guide.

1. Call `ha_get_skill_guide(skill="home-assistant-best-practices", file="SKILL.md")` once per session. The result contains an acknowledgment key (a read-receipt that rotates hourly).
2. Pass that key as `BestPracticeKey` on write calls, and pass `MandatoryBPS=false` afterwards in the same session.
3. Follow the guide's rules rather than restating them here: native triggers and conditions before templates, built-in helpers before template sensors, `entity_id` not `device_id`, the right automation `mode`, Z2M triggers for Zigbee buttons, and the purpose-specific triggers introduced in 2026.7.
4. Before renaming entities or restructuring automations, read `references/safe-refactoring.md` from the same guide. Many `irrigation_*` helpers are config entries that other automations depend on.
5. Read before write: `ha_config_get_automation`, `ha_config_get_script` or `ha_config_get_dashboard` first, and keep the returned `config_hash` when updating.

## Safety rules (owner decisions of 2026-10-06)

Act freely: reads, searches, history, logs, lights, media players, and light scenes.

Confirm first (state exactly what will change, then wait for a yes):
- Dishwasher: starting a program, or changing `select.dishwasher_active_program`.
- Notifications or messages to anyone other than Tim. Test notifications go to Tim's devices only (the script named `send_dynamic_notification_tims_iphone`), never to Sonya, Celeste or Eve without asking.
- Camera snapshots, unless the user asked for the camera.
- `ha_restart`, `ha_reload_core`, `ha_manage_updates` (about 25 updates are pending; use its backup option), and anything that deletes or removes (`ha_config_remove_*`, `ha_remove_*`).
- Editing automations in the Alarm, Security, Irrigation, Power Outage or Proxmox groups.

Never touch:
- **Alarm.** Do not arm, disarm or trigger `alarm_control_panel.crow_alarm_system_alarm` unless the owner asks for exactly that in the same request.
- **Irrigation valves are read-only.** Never switch `switch.watervalve_*_state`, and treat the irrigate-now and irrigate-tomorrow input buttons (named `irrigation_irrigatenow` and `irrigation_irrigatetomorrow`) the same way, since they start watering. Read state and history only. If asked to water, say the standing rule is read-only and ask the owner to do it or to change the rule.
- **LXC buttons.** Never press any `button.lxc_*` entity. Pressing `button.lxc_homeassistant_122_*` takes Home Assistant itself offline, and `button.lxc_adguard_123_*` takes household DNS down. Do LXC power operations through the `proxmox` server so its confirmation rules apply.
- Disabling the Irrigation turn-off automations (`Irrigation – Turn OFF after Duration`, `Irrigation – Zone Timers FINISH and Valves OFF`) or any `Power Outage –` automation, unless the owner asks for it explicitly. Those implement UPS shutdown and restart and water safety.

## Patterns

Examples marked (verified) were run on 2026-10-06. The rest follow the stub, so check parameters with `getToolDocs` before first use.

Response shapes (verified): `ha_search` returns a dict with an `entities` list (each has `entity_id`, `friendly_name`, `state`). `ha_get_state` returns `{"data": {"states": {ENTITY_ID: {...}}}, "metadata": {...}}`, so index `result["data"]["states"]`. `ha_get_integration` returns `entries` plus `has_more` and `next_offset`.

Overview (verified). This returns counts and only about 10 sample entities per domain, so use search for exact IDs:

```python
result = home_assistant.ha_get_overview(detail_level="minimal")
```

Find entities (verified). `domain_filter` lists a domain, `query` matches names:

```python
result = home_assistant.ha_search(query="lounge", domain_filter="light", limit=10)
```

Read state, trimmed to the fields you need (verified):

```python
result = home_assistant.ha_get_state(entity_id=["light.lounge_lamps"], fields=["state", "last_changed"])
```

Floors and areas (verified), and integrations with paging (verified):

```python
result = home_assistant.ha_list_floors_areas()
result = home_assistant.ha_get_integration(limit=50, offset=0)
```

Control a device:

```python
result = home_assistant.ha_call_service(domain="light", service="turn_on", entity_id="light.lounge_lamps", data={"brightness_pct": 40})
```

Debug an automation: read its config, then its recent traces, then the logs:

```python
result = home_assistant.ha_config_get_automation(identifier="automation.lounge_lamps_dawn_sleep_mode_off")
result = home_assistant.ha_get_automation_traces(automation_id="automation.lounge_lamps_dawn_sleep_mode_off", limit=3)
result = home_assistant.ha_get_logs(source="error_log", hours_back=24, limit=50)
```

## Noise to expect

- Around 190 entities are `unavailable` or `unknown` at any time, mostly phone sensors, the Mac Studio, dishwasher helpers and spare bulbs. The `Maintenance – Unavailable Entities` automation writes them into a persistent notification. Judge each one before calling it a fault, and use `last_changed` to see how long it has been offline.
- Zigbee2MQTT bridge entities ending in `_2` or `_3` are `unavailable` and look like stale duplicates of the unsuffixed ones. This is not verified, so check before removing anything.
- The irrigation valves (`watervalve_*`) and their battery sensors are offline by design over winter. The owner lets the batteries run flat and only uses irrigation in summer, so do not report them as faults outside the watering season.
- `ha_get_system_health` returns only the recorder, core, Lovelace, HACS and network sections on this install.
