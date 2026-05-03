from evdev import InputDevice, categorize, ecodes, list_devices

def get_controller():
    devices = [InputDevice(path) for path in list_devices()]
    for device in devices:
        if "Xbox" in device.name or "Wireless Controller" in device.name:
            return device
    return None

gamepad = get_controller()

if not gamepad:
    print("No controller found. Make sure it is paired and turned on!")
    exit()

print(f"Connected to {gamepad.name}.")
print("Leave the sticks untouched for a moment, then move them around.")
print("Press Ctrl+C to stop.")
print("-" * 40)

try:
    for event in gamepad.read_loop():
        # Only listen for analog stick/trigger movements (EV_ABS)
        if event.type == ecodes.EV_ABS:
            axis_name = ecodes.ABS[event.code]
            print(f"Input: {axis_name} | Raw Value: {event.value}")
except KeyboardInterrupt:
    print("\nTest stopped.")