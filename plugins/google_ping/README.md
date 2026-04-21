# Google Ping Plugin

The `google_ping` plugin starts a background task that sends an HTTP GET request to a configured URL on a fixed interval. By default, it pings `https://google.com` every 30 seconds and logs the HTTP status code or any request error.

## What it does

- Starts a background task during plugin initialization
- Waits for the configured interval between requests
- Sends an HTTP GET request to the configured URL
- Logs successful responses and failures
- Shuts down cleanly when the plugin is stopped

## Configuration

The plugin accepts these configuration values in `plugins/config.yaml`:

- `interval`: Number of seconds between ping attempts. Default: `30`
- `url`: Target URL to ping. Default: `https://google.com`

Example:

```yaml
- name: "GooglePingPlugin"
  kind: "plugins.google_ping.google_ping.GooglePingPlugin"
  description: "Background plugin that pings a configured URL on an interval"
  version: "0.1.0"
  author: "ContextForge"
  hooks: []
  tags: ["background", "http", "monitoring", "healthcheck"]
  mode: "disabled"
  priority: 500
  conditions: []
  config:
    interval: 30
    url: "https://google.com"
```

## How to enable

1. Ensure plugins are enabled in your environment:
   - `PLUGINS_ENABLED=true`
   - `PLUGINS_CONFIG_FILE=plugins/config.yaml`

2. In `plugins/config.yaml`, change the plugin mode from:
   - `mode: "disabled"`
   to either:
   - `mode: "permissive"` or
   - `mode: "enforce"`

3. Restart the gateway so the plugin is loaded.

## Logging

The plugin logs:
- Startup configuration
- Successful ping status codes
- Timeout failures
- HTTP/network errors
- Shutdown and cancellation events