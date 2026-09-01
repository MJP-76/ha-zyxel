# Installation

## Pre-requisites

1. The device must be reachable from your Home Assistant instance (they need to
   be on the same local network).
2. HTTP access must be enabled in the device's settings (it is the case by
   default).

## Install via HACS (recommended)

1. Install HACS
2. Click the HACS button on the [home page](index.md)
3. Click Download and confirm
4. Restart HA

## Install manually

1. SSH into your HA instance
2. `git clone https://github.com/MJP-76/ha-zyxel`
3. Navigate to `ha-zyxel/custom_components`
4. Copy `ha_zyxel` to your HA instance's `custom_components` directory
5. Restart your HA instance

## What's next

Once installed, see [Adding a device](setup.md) to connect your Zyxel device.