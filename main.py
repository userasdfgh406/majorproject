from vex import *
import sys


brain = Brain()
motor_thumb = Motor(Ports.PORT1, GearSetting.RATIO_18_1, False)
motor_index = Motor(Ports.PORT2, GearSetting.RATIO_18_1, False)
motor_middle = Motor(Ports.PORT3, GearSetting.RATIO_18_1, False)
motor_ring = Motor(Ports.PORT4, GearSetting.RATIO_18_1, False)
motor_pinky = Motor(Ports.PORT5, GearSetting.RATIO_18_1, False)

motors = [motor_thumb, motor_index, motor_middle, motor_ring, motor_pinky]

MOTOR_SPEED = 25
MOTOR_POSITION_UP = 0
MOTOR_POSITION_DOWN = 2250
MOTOR_HOLD_MS = 250
last_command = "NONE"
is_unlocked = False


def show_screen(line1, line2=""):
    brain.screen.clear_screen()
    brain.screen.set_cursor(1, 1)
    brain.screen.print(line1)
    if line2:
        brain.screen.set_cursor(2, 1)
        brain.screen.print(line2)


def is_valid_pattern(text):
    if len(text) != 5:
        return False

    for char in text:
        if char not in ("0", "1"):
            return False

    return True


def move_finger(finger_motor, finger_state):
    if finger_state == "1":
        finger_motor.spin_to_position(MOTOR_POSITION_UP, DEGREES, False)
    elif finger_state == "0":
        finger_motor.spin_to_position(MOTOR_POSITION_DOWN, DEGREES, False)


def apply_pattern(pattern):
    global last_command

    for index in range(5):
        move_finger(motors[index], pattern[index])

    wait(MOTOR_HOLD_MS, MSEC)
    last_command = pattern


def unlock_receiver():
    global is_unlocked
    is_unlocked = True
    print("Receiver unlocked")
    show_screen("Hand tracking", "UNLOCKED")


def lock_receiver():
    global is_unlocked
    is_unlocked = False
    print("Receiver locked")
    show_screen("Security lock", last_command)


def read_line_from_stdin():
    try:
        line = sys.stdin.readline()
    except Exception as error:
        print("stdin read error:", error)
        return None

    if not line:
        return None

    return line.strip()


def main():
    for motor in motors:
        motor.set_stopping(HOLD)
        motor.set_velocity(MOTOR_SPEED, PERCENT)
        motor.set_position(0, DEGREES)

    show_screen("Security lock", "Do gesture code")
    print("Receiver ready. Send commands like 01000")
    print("Send UNLOCK after the hand-tracking security sequence")
    print("Send LOCK to disable motor commands")
    print("Reading from sys.stdin")

    while True:
        text = read_line_from_stdin()

        if text is None:
            wait(20, MSEC)
            continue

        if text == "UNLOCK":
            unlock_receiver()
        elif text == "LOCK":
            lock_receiver()
        elif is_valid_pattern(text) and is_unlocked:
            apply_pattern(text)
            print("Received:", last_command)
            show_screen("Received:", last_command)
        elif is_valid_pattern(text):
            print("Ignored while locked:", text)
            show_screen("Security lock", "Gesture code needed")
        else:
            print("Ignored input:", text)
            show_screen("Waiting for PC", last_command)


main()
