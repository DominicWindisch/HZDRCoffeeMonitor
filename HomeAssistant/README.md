In configuration.yaml, add:
```yaml
homeassistant:
  packages: !include_dir_named packages
```

Then, create a folder 'packages' right next to configuration.yaml and place hzdr_coffee_monitor.yaml in there.

Restart homeassistant (reloading YAML is not enough).