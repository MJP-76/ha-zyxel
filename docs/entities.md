# Available entities

In theory, all items listed in the [example output of the `n7101` library][n7101-example]
should be available as entities. The entities are generated dynamically, meaning
they can vary from one device to another. They depend on what the device lets us
see.

The integration also creates a **Reboot Device** button per device.

## Default-enabled sensors

The device-specific sensor sets are curated so only the essentials are enabled
by default. For example, on the EX3301-T0 the enabled set is:

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

Additional curated sensors exist (DSL rates, Is Default Route, WiFi telemetry,
etc.) but are disabled by default and can be enabled individually from
**Settings → Devices & Services → Zyxel**.

## Noisy duplicates

On some device types (for example NWA50AX access points) noisy `zyshdata*`
duplicates are skipped, and generic sensors are hidden by default so that only
the useful AP/status sensors are exposed.

[n7101-example]: https://github.com/pkorpine/nr7101?tab=readme-ov-file#example-output