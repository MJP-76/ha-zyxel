# Handover notes

Maintainer/developer notes for the ha-zyxel integration — EX3301-T0 /
NWA50AX support work on top of the upstream `zulufoxtrot/ha-zyxel` integration.

**Fork:** `MJP-76/ha-zyxel` &nbsp;·&nbsp; **Upstream:** `zulufoxtrot/ha-zyxel`
&nbsp;·&nbsp; **Updated:** 2026-07-20

## What the integration work covers

Adds full EX3301-T0 support and improves NWA50AX support on top of the upstream
`ha-zyxel` integration. Introduces a curated entity model and consistent naming
across all device types. Legacy router support is untouched.

## Current state — working

- [x] EX3301-T0 login (RSA/AES crypto), session management, re-login on expiry
- [x] EX3301-T0 CGI endpoint probing and encrypted response decryption
- [x] Curated EX3301-T0 sensor set with friendly names and `[Section]` prefixes
- [x] EX3301-T0 null/unknown suppression — no firmware-stub entities
- [x] EX3301-T0 stale entity cleanup on each reload
- [x] EX3301-T0 default-enabled allowlist (Core/Network/Uptime/WiFi state only)
- [x] EX3301-T0 WiFi band-state sensors (Private/Guest × 2.4GHz/5GHz)
- [x] EX3301-T0 auto-reload when WiFi radio layout changes
- [x] NWA50AX zysh-cgi flow intact; title detection fixed (no longer shows "English")
- [x] NWA50AX bulk setup supports comma/newline-separated IPs and creates one entry per host
- [x] NWA50AX generic sensors are hidden by default to avoid exposing extra entities
- [x] NWA50AX default-enabled allowlist added for the AP/status sensors
- [x] NWA50AX everything else stays disabled, with `zyshdata*` removed from display
- [x] NWA50AX MAC address entries are included by default
- [x] NWA50AX skips noisy `zyshdata*` duplicate entities
- [x] Legacy sensor defaults preserved; only the device picker changed
- [x] Legacy Zyxel-prefixed entities are migrated so new names take effect
- [x] Uptime sensors formatted as `d/h/m/s`
- [x] Entity names without "Zyxel" prefix (prefix lives in device/integration group)
- [x] Integration group titles without "Zyxel" prefix (uses model/system name)
- [x] Unified device naming: system-name-first, then host/IP fallback, all models
- [x] Duplicate `[Core] Hardware Version` sensor removed

## Key files

| File | What changed / what it does |
|---|---|
| `custom_components/ha_zyxel/backend.py` | EX3301 login/crypto/probe; NWA50AX `get_device_model()` + language-filter fix |
| `custom_components/ha_zyxel/__init__.py` | Setup entry, coordinator, WiFi signature + auto-reload |
| `custom_components/ha_zyxel/sensor.py` | KNOWN_SENSORS map, WiFi curation, section prefixes, default-enabled allowlist |
| `custom_components/ha_zyxel/button.py` | Reboot button — system-name-first DeviceInfo naming |
| `custom_components/ha_zyxel/config_flow.py` | Device-picker flow, NWA50AX multi-host onboarding |

### Key line references

| Symbol | File | ~Line |
|---|---|---|
| `_normalize_device_type()` | `__init__.py` | 110 |
| `_ex3601_wifi_signature()` | `__init__.py` | 130 |
| `async_setup_entry` | `__init__.py` | 328 |
| `EX3301T0Client` | `backend.py` | 236 |
| `_encrypt_login_payload()` | `backend.py` | 290 |
| `NWA50AXClient.get_device_model()` | `backend.py` | 232 |
| `KNOWN_SENSORS` | `sensor.py` | 120–535 |
| `_ex3301_sensor_enabled_by_default()` | `sensor.py` | ~540 |
| `EX3301WiFiBandStateSensor` | `sensor.py` | ~845 |

## EX3301-T0 default-enabled sensor set

```
[Core]    Firmware Version
[Core]    Model
[Core]    Serial Number
[Network] DHCP Status (LAN)
[Network] DNS Server (DNS 0)
[Network] IP Address
[Network] IP Address (WAN 2)
[Network] PPP Connection Status (WAN 2)
[Network] WAN Ethernet Status
[Network] WAN Gateway IP (WAN 2)
[Uptime]  IPoE Connection Uptime (WAN 2)
[Uptime]  PPPoE Connection Uptime (WAN 2)
[Uptime]  System Uptime
[WiFi]    Private WiFi 2.4GHz Enabled
[WiFi]    Private WiFi 5GHz Enabled
[WiFi]    Guest WiFi 2.4GHz Enabled
[WiFi]    Guest WiFi 5GHz Enabled
[Action]  Reboot Device  (button)
```

Additional curated sensors exist (DSL rates, Is Default Route, etc.) but are
disabled by default and can be enabled individually.

### WAN layout note

WAN 0 = LAN-side (172.16.x.x), WAN 1 = inactive slot, WAN 2 = active PPPoE
(public IP). `DefaultGateway` is a boolean flag (is default route), not an IP.

## Important technical notes

- **`device_type` normalisation is critical.** Stored value may be `ex3301-t0`
  (hyphens). All EX3301 conditional logic requires `_normalize_device_type()` →
  `ex3301_t0`. Without this, EX3301 falls through to generic sensor creation and
  generates 500+ entities.
- **EX3301 crypto:** RSA must encrypt the base64 string of the AES key (not raw
  bytes). Login POST must use `data=json.dumps(payload)`, not `json=payload`.
- **Encrypted API responses:** After login, all CGI endpoints return
  `{"content":"<b64>","iv":"<b64>"}` — decrypt with session AES key.
- **No `/cgi-bin/` prefix on EX3301.** All endpoints work at root
  (`/CardInfo`, `/DAL?oid=...`). Using `/cgi-bin/` causes timeout.
- **`available` property:** HA checks `available` before `state`. `_flat_state`
  must be pre-populated in `__init__` from `coordinator.data`; do not rely
  solely on the update callback.

## Known remaining issues / next steps

1. **EX3301 WiFi telemetry entities** — Active-radio WiFi sensors (SSID,
   channel, link rate) are curated and filter-ready but the `DAL?oid=wlan`
   probe needs live verification. After reload check HA logs for
   `WLAN-related data keys` INFO entries to confirm returned keys.

2. **NWA50AX device name showing IP** — System-name extraction is implemented.
   If the device still shows an IP after reload, check which zysh command
   returns the system hostname and expand `get_status()`.

3. **Upstream PR** — Draft PR body embedded in the branch-era HANDOVER; see the
   open PR against the upstream repo.

4. **Control mode** — Read-only by design. Roadmap for optional write/control
   mode is documented in [Roadmap](../roadmap.md).

## Upstream PR reference

Title: *Improve EX3301-T0 and NWA50AX support, clean up entity names, and
stabilize Zyxel onboarding*.

Attribution: this work was coded with assistance from GitHub Copilot.