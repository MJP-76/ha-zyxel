# ha-zyxel

<img src="https://raw.githubusercontent.com/zulufoxtrot/ha-zyxel/refs/heads/main/resources/logo.png" alt="Zyxel Logo" width="128"/>

> 📢 🤓 **This project is looking for maintainers** 📢 🤓
> 
> If you are interested, get in touch!

__Home Assistant integration for the Zyxel NWA50AX access point__

<img src="https://raw.githubusercontent.com/zulufoxtrot/ha-zyxel/refs/heads/main/resources/screenshot.png" alt="Zyxel Logo" />

[![Open ha-zyxel on Home Assistant Community Store (HACS)](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zulufoxtrot&repository=ha-zyxel&category=integration)

## Supported device

Confirmed working on:

- NWA50AX

This fork is focused on the NWA50AX access point only.

## Installation

Prerequisites:

1. The device must be reachable from your home assistant instance (they need to be on the same local network)
2. HTTP access must be enabled in the device's settings (it is the case by default)

### Install via HACS (recommended)

1. Install HACS
2. Click the big blue button above
3. Click Download and confirm
4. Restart HA

### Install manually

1. SSH into your HA instance
3. `git clone https://github.com/zulufoxtrot/ha-zyxel`
2. Navigate to `ha-zyxel/custom_components`
4. Copy `ha_zyxel` to your HA instance's `custom_components` directory
4. Restart your HA instance

## Adding a device

1. Go to HA Settings > Devices & Services.
2. Click Add Integration.
3. Search for Zyxel.
4. Select the Zyxel integration.
5. In Host, type your hostname IP, usually something like `https://192.168.1.1` (⚠️ enter the full URL scheme with `https://`)
6. Type your admin username and password
7. Click Submit.

If connection fails, try with `http://` instead of `https://`.

## Adding cards to your dashboard

Add [this code](resources/card_example.yml) to your dashboard to add the cards pictured above. Follow the instructions from the animation below.

Note: the Mushroom card extension is required for the above code to work.

![](resources/import_demo.gif)

## Available entities

Entities are generated dynamically from the NWA50AX response data and may vary with firmware and configuration.

## Support

Please submit an [issue](https://github.com/zulufoxtrot/ha-zyxel/issues).

## Credits

This integration uses the [n7101 library](https://github.com/pkorpine/nr7101) by pkorpine.
