# Zyxel Home Assistant Integration

[![HACS][badge-hacs]][hacs]
[![HACS Validation][badge-hacs-validation]][workflow-hacs-validation]
[![Hassfest][badge-hassfest]][workflow-hassfest]
[![Docs][badge-docs]][docs]

<img src="https://raw.githubusercontent.com/MJP-76/ha-zyxel/main/resources/logo.png" alt="Zyxel Logo" width="128"/>

> 📢 🤓 **This project is looking for maintainers** 📢 🤓
>
> If you are interested, get in touch!

__Home Assistant integration for Zyxel devices__

[![Open ha-zyxel on Home Assistant Community Store (HACS)](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zulufoxtrot&repository=ha-zyxel&category=integration)

## What this integration does

- Monitors Zyxel devices (read-only by default — telemetry/monitoring)
- Works with Zyxel access points, routers, and cellular gateways
- Entities are generated dynamically based on what each device exposes

## Supported devices

Confirmed working on:

- AX7501-B0
- FWA505
- FWA510
- FWA710 5G V2
- LTE3202-M437
- LTE7490-M904
- LTE5398-M904
- NR5103E
- NR5103v2
- NR5307
- NR7101
- NR7102
- NR7302
- VMG3625-T50B
- VMG4005-B50A
- VMG8825-T50

Potentially compatible with a lot more devices.
If you do test and find out your device is working, please submit an issue or a
pull request and we'll add it to the list.

## Where to go next

| Topic | Page |
|---|---|
| Install the integration | [Installation](installation.md) |
| Add a device | [Adding a device](setup.md) |
| What entities are available | [Entities](entities.md) |
| Planned feature direction | [Roadmap](roadmap.md) |
| Report a problem or get help | [Support](support.md) |
| Maintainer handover and development notes | [Handover notes](development/handover.md) |

[badge-hacs]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs]: https://github.com/hacs/integration
[badge-hacs-validation]: https://img.shields.io/badge/HACS%20Validation-passing-brightgreen
[workflow-hacs-validation]: https://github.com/MJP-76/ha-zyxel/actions/workflows/hacs.yml
[badge-hassfest]: https://img.shields.io/github/actions/workflow/status/MJP-76/ha-zyxel/hassfest.yml?branch=main&label=Hassfest
[workflow-hassfest]: https://github.com/MJP-76/ha-zyxel/actions/workflows/hassfest.yml
[badge-docs]: https://img.shields.io/badge/Docs-MkDocs-41BDF5?style=flat&logo=materialdesignicons&logoColor=white
[docs]: https://MJP-76.github.io/ha-zyxel/