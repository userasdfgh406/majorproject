from vex import *
import sys


brain = Brain()
motor_thumb = Motor(Ports.PORT1, GearSetting.RATIO_18_1, False)
motor_index = Motor(Ports.PORT2, GearSetting.RATIO_18_1, False)
# Ports 4 and 5 use the same direction so they bend the same way.
motor_middle = Motor(Ports.PORT3, GearSetting.RATIO_18_1, False )
motor_ring = Motor(Ports.PORT4, GearSetting.RATIO_18_1, True)
motor_pinky = Motor(Ports.PORT5, GearSetting.RATIO_18_1, True)

motors = [motor_thumb, motor_index, motor_middle, motor_ring, motor_pinky]

# Shared motor settings keep every finger moving at the same speed.
MOTOR_SPEED = 25
MOTOR_POSITION_UP_ROTATIONS_BY_FINGER = [
    -0.50,    # Port 1 thumb
    0,    # Port 2 index
    0,    # Port 3 middle
    0,    # Port 4 ring
    -0.50,    # Port 5 pinky
]
MOTOR_POSITION_DOWN_ROTATIONS_BY_FINGER = [
    6.50, # Port 1 thumb
    9.0, # Port 2 index
    7.30, # Port 3 middle
    6.80,  # Port 4 ring
    7.80,  # Port 5 pinky
]
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
    if len(text) != 5: # Valid commands are five binary digits, one for each finger.
        return False

    for char in text:
        if char not in ("0", "1"):
            return False

    return True


def move_finger(finger_motor, finger_state, up_rotations, down_rotations):    # "1" opens a finger and "0" closes it to match the camera pattern.
    if finger_state == "1":
        finger_motor.spin_to_position(up_rotations, TURNS, False)
    elif finger_state == "0":
        finger_motor.spin_to_position(down_rotations, TURNS, False)


def wait_for_motors(timeout_ms=3000):
    """
    Blocks execution until all motors have finished moving, or until
    the safety timeout is reached.
    """
    elapsed = 0
    while elapsed < timeout_ms:
        all_done = True
        for motor in motors:
            if not motor.is_done():
                all_done = False
                break
        if all_done:
            break
        wait(20, MSEC)
        elapsed += 20


def apply_pattern(pattern):
    global last_command

    # Start every finger first so the hand changes shape as one motion.
    for index in range(5):
        move_finger(
            motors[index],
            pattern[index],
            MOTOR_POSITION_UP_ROTATIONS_BY_FINGER[index],
            MOTOR_POSITION_DOWN_ROTATIONS_BY_FINGER[index],
        )

    # Hold the next command until the current gesture has finished moving.
    wait_for_motors()

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
    # The PC sends one command per line over the serial stdin connection.
    try:
        line = sys.stdin.readline()
    except Exception as error:
        print("stdin read error:", error)
        return None

    if not line:
        return None

    return line.strip()


def main():
    # Put every motor into a known starting state before accepting commands.
    for motor in motors:
        motor.set_stopping(HOLD)
        motor.set_velocity(MOTOR_SPEED, PERCENT)
        motor.set_position(0, TURNS)

    show_screen("Security lock", "Do gesture code")
    print("Receiver ready. Send commands like 01000")
    print("Send UNLOCK after the hand-tracking security sequence")
    print("Send LOCK to disable motor commands")
    print("Reading from sys.stdin")

    while True:
        # Keep polling stdin so the robot can react as soon as the PC sends data.
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
