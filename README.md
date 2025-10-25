# Apple Version Tracker for Home Assistant

A custom Home Assistant integration that tracks the latest iOS, iPadOS, watchOS, and tvOS versions for specific Apple device models.

## Features

- Track latest OS versions for any Apple device model
- Automatic updates every 10 minutes
- Easy configuration through the UI
- Provides version number, build number, and posting date as attributes

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add this repository URL
6. Install "Apple Version Tracker"
7. Restart Home Assistant

### Manual Installation

1. Copy the `apple_version_tracker` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Apple Version Tracker"
4. Enter:
   - **Device Model**: The Apple device identifier (e.g., `iPhone14,4`, `iPad12,1`, `Watch7,1`, `AppleTV6,2`)
   - **Friendly Name**: A name for the sensor (e.g., `iPhone`, `iPad`, `Watch`, `AppleTV`)
5. Click **Submit**

## Finding Device Models

To find your device model:

### iPhone/iPad
- Go to **Settings** → **General** → **About** → **Model Number**
- Tap the model number to see the identifier (e.g., iPhone14,4)

### Apple Watch
- On iPhone: **Watch app** → **General** → **About** → **Model**
- Look up the model number online to find the identifier

### Apple TV
- **Settings** → **General** → **About** → **Model**
- Look up the model number online to find the identifier

### Common Device Models

| Device | Model Identifier |
|--------|------------------|
| iPhone 13 Mini | iPhone14,4 |
| iPhone 13 | iPhone14,5 |
| iPhone 13 Pro | iPhone14,2 |
| iPhone 13 Pro Max | iPhone14,3 |
| iPad Pro 12.9" (5th gen) | iPad13,8 |
| iPad Pro 11" (3rd gen) | iPad13,4 |
| iPad 9th Gen | iPad12,1 |
| Apple Watch Series 7 | Watch7,1 |
| Apple TV 4K (2nd gen) | AppleTV11,1 |
| Apple TV HD | AppleTV6,2 |

## Sensor Attributes

Each sensor provides the following attributes:

- `product_version`: The version number (e.g., "18.0.1")
- `build`: The build number (e.g., "22A400")
- `posting_date`: When Apple released this version
- `device_model`: The device model identifier
- `supported_devices`: List of all devices that support this version

## Example Automation

```yaml
automation:
  - alias: "Notify on New iOS Version"
    trigger:
      - platform: state
        entity_id: sensor.latest_version_iphone
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New iOS Version Available"
          message: >
            iOS {{ states('sensor.latest_version_iphone') }} is now available!
            Build: {{ state_attr('sensor.latest_version_iphone', 'build') }}
```

## Multiple Devices

You can add the integration multiple times to track different devices. Each device will create a separate sensor entity.

## Troubleshooting

### Sensor shows "unknown"
- Check that the device model identifier is correct
- Verify your internet connection
- Check Home Assistant logs for errors

### Updates not showing
- The integration checks for updates every 10 minutes
- You can force an update by reloading the integration

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## License

MIT License
