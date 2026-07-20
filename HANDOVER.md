# Handover — ha-zyxel EX3301-T0 / NWA50AX Integration

**Branch:** `mjp-76-remove-device-prefix-entities`  
**Fork:** `MJP-76/ha-zyxel`  
**Upstream:** `zulufoxtrot/ha-zyxel`  
**Last commit on `main`:** `d2caa9a` — Add HANDOVER.md for cross-device continuation  
**Updated:** 2026-07-20  

---

## What this branch does

Adds full EX3301-T0 support and improves NWA50AX support on top of the upstream `ha-zyxel` integration. Introduces a shared Zyxel dashboard, curated entity model, and consistent naming across all device types. Legacy router support is untouched.

---

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
- [x] NWA50AX default-enabled allowlist added for the AP/status sensors from the supplied list
- [x] NWA50AX everything else stays disabled, with `zyshdata*` removed from display
- [x] NWA50AX MAC address entries are included by default
- [x] NWA50AX skips noisy `zyshdata*` duplicate entities
- [x] Legacy sensor defaults preserved; only the device picker changed on the legacy side
- [x] Uptime sensors formatted as `d/h/m/s`
- [x] Shared Zyxel dashboard — auto-created on first device add
- [x] Dashboard refreshes on entity registry create/remove/update events
- [x] Dashboard uses per-device section headings with host/IP for uniqueness
- [x] Entity names without "Zyxel" prefix (prefix lives in device/integration group)
- [x] Integration group titles without "Zyxel" prefix (uses model/system name)
- [x] Unified device naming: system-name-first, then host/IP fallback, all models
- [x] Duplicate `[Core] Hardware Version` sensor removed

---

## Key files

| File | What changed / what it does |
|---|---|
| `custom_components/ha_zyxel/backend.py` | EX3301 login/crypto/probe; NWA50AX `get_device_model()` + language-filter fix |
| `custom_components/ha_zyxel/__init__.py` | Setup entry, coordinator, dashboard lifecycle, WiFi signature + auto-reload |
| `custom_components/ha_zyxel/sensor.py` | KNOWN_SENSORS map, WiFi curation, section prefixes, default-enabled allowlist |
| `custom_components/ha_zyxel/button.py` | Reboot button — system-name-first DeviceInfo naming |
| `custom_components/ha_zyxel/config_flow.py` | Device-picker flow, NWA50AX multi-host onboarding |

### Key line references

| Symbol | File | ~Line |
|---|---|---|
| `_normalize_device_type()` | `__init__.py` | 110 |
| `_ex3601_wifi_signature()` | `__init__.py` | 130 |
| `async_setup_entry` | `__init__.py` | 328 |
| `_dashboard_device_cards()` | `__init__.py` | 190 |
| `_handle_entity_registry_update` | `__init__.py` | 480 |
| `EX3301T0Client` | `backend.py` | 236 |
| `_encrypt_login_payload()` | `backend.py` | 290 |
| `NWA50AXClient.get_device_model()` | `backend.py` | 232 |
| `KNOWN_SENSORS` | `sensor.py` | 120–535 |
| `_ex3301_sensor_enabled_by_default()` | `sensor.py` | ~540 |
| `EX3301WiFiBandStateSensor` | `sensor.py` | ~845 |

---

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

Additional curated sensors exist (DSL rates, Is Default Route, etc.) but are disabled by default and can be enabled individually.

### WAN layout note
WAN 0 = LAN-side (172.16.x.x), WAN 1 = inactive slot, WAN 2 = active PPPoE (public IP). `DefaultGateway` is a boolean flag (is default route), not an IP.

---

## Important technical notes

- **`device_type` normalisation is critical.** Stored value may be `ex3301-t0` (hyphens). All EX3301 conditional logic requires `_normalize_device_type()` → `ex3301_t0`. Without this, EX3301 falls through to generic sensor creation and generates 500+ entities.
- **EX3301 crypto:** RSA must encrypt the base64 string of the AES key (not raw bytes). Login POST must use `data=json.dumps(payload)`, not `json=payload`.
- **Encrypted API responses:** After login, all CGI endpoints return `{"content":"<b64>","iv":"<b64>"}` — decrypt with session AES key.
- **No `/cgi-bin/` prefix on EX3301.** All endpoints work at root (`/CardInfo`, `/DAL?oid=...`). Using `/cgi-bin/` causes timeout.
- **`available` property:** HA checks `available` before `state`. `_flat_state` must be pre-populated in `__init__` from `coordinator.data`; do not rely solely on the update callback.
- **Dashboard panel re-registration:** `frontend.async_register_built_in_panel()` raises `ValueError` if panel already registered. Guard with `update=True` or try/except.

---

## Known remaining issues / next steps

1. **EX3301 WiFi telemetry entities** — Active-radio WiFi sensors (SSID, channel, link rate) are curated and filter-ready but the `DAL?oid=wlan` probe needs live verification. After reload check HA logs for `WLAN-related data keys` INFO entries to confirm returned keys.

2. **Dashboard dynamic update** — Entity registry `update` events now trigger a refresh. If sections still don't update after an HA restart, check whether `_schedule_dashboard_refresh` is firing (add a debug log in `_handle_entity_registry_update`).

3. **NWA50AX device name showing IP** — System-name extraction is implemented. If the device still shows an IP after reload, check which zysh command returns the system hostname and expand `get_status()` (e.g. `show system info` or `show running-config`).

4. **Upstream PR** — Draft PR body is embedded below. PR targets `MJP-76/ha-zyxel` from the current feature branch.

5. **Control mode** — Read-only by design. Roadmap for optional write/control mode is documented in `README.md`.

---

## How to resume

```bash
# Fresh clone
git clone https://github.com/MJP-76/ha-zyxel.git
cd ha-zyxel
git checkout mjp-76-nwa50ax-integration

# Already cloned
git fetch origin
git checkout mjp-76-nwa50ax-integration
git rebase origin/main
```

The integration is installed at `/config/custom_components/ha_zyxel/` on the HA instance.  
EX3301-T0 is at `http://172.16.1.254` — credentials are in the HA config entry.

---

## Upstream PR — ready to open

**Title:** Improve EX3301-T0 and NWA50AX support, clean up entity names, and stabilize Zyxel onboarding/dashboard

**Body:**

```
## Summary
This PR strengthens model-specific support for EX3301-T0 and NWA50AX while keeping
the original legacy flow intact. It also cleans up entity naming and dashboard behavior.

## Config flow changes (shared + model-specific)
- Kept the original legacy config path for existing generic-supported devices.
- Added dedicated per-model setup/validation paths for NWA50AX and EX3301-T0.

## EX3301-T0 changes
### Connectivity/runtime
- Hardened EX3301 login/session flow.
- Added encrypted CGI response decryption handling.
- Improved probe strategy and session-expiry recovery (re-login + retry).
- Increased EX3301 polling timeout for multi-endpoint status collection.

### Entity model
- Replaced broad generic flattening with curated/mapped entity creation.
- Added stale entity cleanup for no-longer-created entities.
- Added migration cleanup for old sensor.zyxel_dal_oid_* entities.
- Normalised device_type aliases so EX3301 always follows EX3301-specific logic.

### EX3301 entity coverage
- Device info: firmware, hardware, model, serial, uptime.
- WAN/LAN: IPs, gateway, route status, PPP status, Ethernet status, DNS, DHCP.
- Uptime/connection durations formatted as d/h/m/s.
- Curated Wi-Fi telemetry: guest Wi-Fi enabled, one SSID mode, SSID/channel/band/bandwidth/
  standards/link rate/main SSID per active radio.
- Excludes noisy/sensitive/unhelpful WLAN fields and raw DAL-style clutter.

## NWA50AX changes
### Connectivity/runtime
- Preserved NWA50AX zysh-cgi behaviour and model-specific validation flow.
- Added multi-device onboarding from a single comma/newline-separated field.
- Each address creates its own config entry using the same username/password.
- Ensured host normalisation and correct AP client routing.
- NWA50AX now exposes the supplied AP/status sensors by default and keeps the rest disabled.
- NWA50AX ignores noisy `zyshdata*` duplicates in the generic entity set.

### Entity model
- NWA50AX continues to expose AP-focused telemetry through dynamic status normalisation,
  including WLAN/radio status, channel/wireless-hal derived state, Nebula status surfaces,
  and device identity/status fields.

## Shared integration/dashboard improvements
- Unified dashboard behaviour across device types.
- Each config entry is isolated at the device level; EX3301, NWA50AX, and legacy devices
  are tracked separately, not as one combined device.
- Fixed panel re-registration conflict on reload.
- Dashboard excludes disabled entities/devices.
- Improved naming consistency (model-aware integration/group context, stable host/IP-based
  device identity).

## Additional changes
- Removed `Zyxel` prefix from integration/group titles (new and migrated existing entries on reload).
- Fixed NWA50AX title detection to avoid locale placeholders like `English`; now prefers
  model/system-name values.
- Unified device naming policy across all models: system-name-first with host/model fallback,
  applied consistently in sensor and button platforms.
- Dashboard grouping uses per-device sections with host/IP suffix for uniqueness.
- Removed duplicate EX3301 `Hardware Version` sensor.
- Added EX3301 default-enabled allowlist so only essential Core/Network/Uptime/WiFi state
  sensors are enabled by default.
- Added EX3301 WiFi profile-band state sensors (Private/Guest × 2.4GHz/5GHz) and automatic
  entry reload when WiFi radio layout changes.
- Curated EX3301 WiFi entities use friendly names grouped by Private/Guest + band + radio;
  raw `DAL?oid=...` WiFi clutter removed.
- Uptime sensors display in d/h/m/s format.

## User-visible outcomes
- Clear setup: pick device type first, then model-specific flow.
- Cleaner EX3301 entities (major noise reduction).
- NWA50AX behaviour retained and aligned with shared logic.
- More stable dashboard and entity lifecycle across reloads/upgrades.
- Legacy device behaviour remains unchanged except for the initial device picker.

## Attribution
- This PR was coded with assistance from GitHub Copilot.
```

**Command to open PR:**
```bash
gh pr create \
  --repo zulufoxtrot/ha-zyxel \
  --head MJP-76:main \
  --title "Improve EX3301-T0 and NWA50AX support, add device-picker config flow, and stabilize Zyxel entities/dashboard" \
  --body-file /tmp/pr-body.txt
```
