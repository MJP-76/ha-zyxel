# Handover — ha-zyxel EX3301-T0 / NWA50AX Integration

**Branch:** `mjp-76-nwa50ax-integration`  
**Fork:** `MJP-76/ha-zyxel`  
**Upstream:** `zulufoxtrot/ha-zyxel`  
**Last commit:** `796a220` — Make dashboard section headings unique per device  
**Date:** 2026-07-20  

---

## What this branch does

This branch adds full EX3301-T0 support and improves NWA50AX support on top of the upstream `ha-zyxel` integration. It also introduces a shared Zyxel dashboard, entity curation, and naming improvements that benefit all device types.

---

## Current state — working

- [x] EX3301-T0 login (RSA/AES crypto), session management, re-login on expiry
- [x] EX3301-T0 CGI endpoint probing and encrypted response decryption
- [x] Curated EX3301-T0 sensor set with friendly names and section prefixes
- [x] EX3301-T0 null/unknown suppression — no firmware-stub entities
- [x] EX3301-T0 stale entity cleanup on each reload
- [x] EX3301-T0 default-enabled allowlist (core/network/uptime/WiFi only)
- [x] EX3301-T0 WiFi band-state sensors (Private/Guest × 2.4GHz/5GHz)
- [x] EX3301-T0 auto-reload when WiFi radio layout changes
- [x] NWA50AX zysh-cgi flow intact; title detection fixed (no longer shows "English")
- [x] Uptime sensors formatted as d/h/m/s
- [x] Shared Zyxel dashboard — auto-created on first device add
- [x] Dashboard refreshes on entity registry create/remove/update events
- [x] Dashboard uses per-device section headings with host/IP for uniqueness
- [x] Entity names without "Zyxel" prefix (prefix lives in device/integration group)
- [x] Integration group titles without "Zyxel" prefix (uses model/system name)
- [x] Unified device naming (system name first, then host/IP fallback) for all models
- [x] PR draft body saved in session SQL (see below)

---

## Key files

| File | What it does |
|---|---|
| `custom_components/ha_zyxel/backend.py` | EX3301 and NWA50AX clients; login/crypto/probe logic |
| `custom_components/ha_zyxel/__init__.py` | Setup entry, coordinator, dashboard lifecycle |
| `custom_components/ha_zyxel/sensor.py` | Entity creation, KNOWN_SENSORS map, WiFi curation |
| `custom_components/ha_zyxel/button.py` | Reboot button with consistent DeviceInfo naming |
| `custom_components/ha_zyxel/config_flow.py` | Device-picker flow + model-specific validation steps |

---

## EX3301-T0 sensor set (default-enabled)

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
[Action]  Reboot Device (button)
```

Additional curated sensors exist (DSL rates, Is Default Route, etc.) but are disabled by default. Users can enable them individually.

---

## Known remaining issues / next steps

1. **EX3301 WiFi telemetry entities not showing yet** — Active-radio WiFi sensors (SSID, channel, link rate) are curated and filter-ready but the `DAL?oid=wlan` probe needs verification. After reload, check HA logs for `WLAN-related data keys` INFO entries to confirm which keys are returned.

2. **Dashboard not updating dynamically** — Entity changes (enable/disable, add/remove) now trigger a refresh via entity_registry_updated events. If sections still don't update, check whether `_schedule_dashboard_refresh` is firing — add a debug log if needed.

3. **NWA50AX device name still showing IP** — System-name extraction from zysh status is implemented. If the device still shows an IP, the `show` command that returns system-name may need expanding in `get_status()` (e.g. `show system info` or `show running-config`).

4. **Upstream PR** — Draft PR body is stored in session SQL (`pr_drafts.upstream-pr-draft`). Retrieve it before opening the PR. The PR targets `zulufoxtrot/ha-zyxel` from `MJP-76/ha-zyxel:main`.

5. **Control mode** — Currently read-only by design. Roadmap for optional write/control mode documented in README.

---

## How to resume

```bash
# Clone the fork and check out the branch
git clone https://github.com/MJP-76/ha-zyxel.git
cd ha-zyxel
git checkout mjp-76-nwa50ax-integration

# Or pull latest if already cloned
git fetch origin
git checkout mjp-76-nwa50ax-integration
git pull origin main --rebase
```

The integration is installed at `/config/custom_components/ha_zyxel/` on the HA instance.  
EX3301-T0 is at `http://172.16.1.254` — credentials in the HA config entry.

---

## PR draft (saved title)

> Improve EX3301-T0 and NWA50AX support, add device-picker config flow, and stabilize Zyxel entities/dashboard

Full body is in session SQL — retrieve with:
```sql
SELECT title, body FROM pr_drafts WHERE id = 'upstream-pr-draft';
```
