Apple Device Latest Version integration for Home Assistant

Tracks the latest iOS/iPadOS/watchOS/tvOS/macOS version available for a given Apple device.

## Adding a device

1. Choose the device type — iPhone, iPad, Apple Watch, Apple TV, HomePod, Apple Vision Pro or a Mac family.
2. Choose the model by name — "iPhone 13 mini (iPhone14,4)" — then name the sensor.

Which models exist comes from Apple's own version feed, so the list stays current on its own. The model can also be typed by hand (for example `iPhone14,4`) if it is not in the list.

Apple's feed publishes only identifiers, never marketing names, so the names come from a bundled table generated from [AppleDB](https://github.com/littlebyteorg/appledb) (MIT licensed). A device newer than that table is still listed and selectable, just shown as its bare identifier. Refresh the table with:

```
git clone --depth 1 https://github.com/littlebyteorg/appledb /tmp/appledb
python3 scripts/generate_device_names.py /tmp/appledb
```

## Install

- Use `apple_device_latest_version.zip` for HACS installs.
- Use `apple_device_latest_version_manual.zip` for manual Home Assistant custom component upload.

The manual ZIP contains the integration directory at the archive root, which is required when uploading the integration directly through the Home Assistant UI.

<img width="431" height="560" alt="image" src="https://github.com/user-attachments/assets/c41a01a5-bfb6-4186-9cf4-a6e64e384439" />
