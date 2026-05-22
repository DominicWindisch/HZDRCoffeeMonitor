# HZDR CoffeeMonitor

- Part 1: CoffeePot_ESP -> ESP in the coffee pot to acquire current pot fill level & temperature
- Part 2: CoffeeBroadcaster_ESP -> ESP to broadcast current coffee pot status via BT-LE
- Part 3: CoffeeDisplay_Pico2W -> Pico2W code which listens for coffee broadcaster and displays info

Setup:
- Attach Broadcaster to Raspi running Home Assistant via USB
- Double check that its recognized as '/dev/ttyACM0' (if not, change the HomeAssistant YAML files)
- Add this to HomeAssistant configuration.yaml:
```yaml
shell_command:
  send_coffee_data: 'stty -F /dev/ttyACM0 115200 && echo "{{ payload }}" > /dev/ttyACM0'
```
- Reload YAML or reboot HomeAssistant
- 

