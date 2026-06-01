import argparse
import time

try:
    import cv2
    from cvzone.HandTrackingModule import HandDetector
    import serial
except ImportError as error:
    missing_package = str(error).split("'")[1] if "'" in str(error) else str(error)
    print("Missing Python package:", missing_package)
    print("Install the project dependencies with:")
    print("  pip install -r requirements.txt")
    raise SystemExit(1)


PORT = "COM3"
BAUD_RATE = 115200
CAMERA_INDEX = 0
STABLE_FRAMES_REQUIRED = 4
UNLOCK_STABLE_FRAMES_REQUIRED = 8
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720

GESTURE_MAP = {
    "00000": "FIST",
    "11111": "OPEN",
    "01000": "INDEX",
    "01100": "PEACE",
    "10000": "THUMB",
    "00001": "PINKY",
    "11000": "L_SHAPE",
}

UNLOCK_SEQUENCE = [
    ("OPEN", "11111"),
    ("FIST", "00000"),
    ("PEACE", "01100"),
    ("THUMB", "10000"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Hand tracking controller for the robot hand.")
    parser.add_argument("--port", default=PORT, help="Serial port for the VEX Brain")
    parser.add_argument("--baud", type=int, default=BAUD_RATE, help="Serial baud rate")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX, help="Webcam index")
    parser.add_argument("--width", type=int, default=DEFAULT_WINDOW_WIDTH, help="Window width")
    parser.add_argument("--height", type=int, default=DEFAULT_WINDOW_HEIGHT, help="Window height")
    parser.add_argument("--fullscreen", action="store_true", help="Open the window fullscreen")
    return parser.parse_args()


def connect_serial(port, baud_rate):
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(2)
        print(f"Connected to VEX Brain on {port}")
        return ser
    except Exception as error:
        print(f"WARNING: Could not connect to VEX Brain on {port}. Error: {error}")
        return None


def classify_gesture(fingers):
    pattern = "".join(map(str, fingers))
    gesture_name = GESTURE_MAP.get(pattern, "UNKNOWN")
    return pattern, gesture_name


def send_command(ser, command):
    if command is None:
        return

    if ser is None:
        return

    ser.write((command + "\n").encode("utf-8"))
    print(f"Sent command: {command}")


def reset_unlock():
    return 0, None, 0


def update_unlock(pattern, sequence_index, candidate_unlock_pattern, unlock_frames):
    expected_pattern = UNLOCK_SEQUENCE[sequence_index][1]

    if pattern == expected_pattern:
        if pattern == candidate_unlock_pattern:
            unlock_frames += 1
        else:
            candidate_unlock_pattern = pattern
            unlock_frames = 1
    else:
        candidate_unlock_pattern = None
        unlock_frames = 0

    if unlock_frames >= UNLOCK_STABLE_FRAMES_REQUIRED:
        sequence_index += 1
        candidate_unlock_pattern = None
        unlock_frames = 0

    return sequence_index, candidate_unlock_pattern, unlock_frames


def draw_status_panel(img, unlocked, pattern, gesture_name, last_sent_label, last_sent_command,
                      sequence_index, unlock_frames):
    height, width = img.shape[:2]
    panel_left = max(0, width - 360)
    cv2.rectangle(img, (panel_left, 0), (width, height), (20, 25, 32), cv2.FILLED)
    cv2.line(img, (panel_left, 0), (panel_left, height), (90, 100, 115), 1)

    status = "UNLOCKED" if unlocked else "LOCKED"
    status_color = (80, 220, 120) if unlocked else (80, 170, 255)
    cv2.putText(img, "Robot Hand", (panel_left + 24, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
    cv2.putText(img, status, (panel_left + 24, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2)
    cv2.putText(img, "mode: serial", (panel_left + 24, 112),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (190, 205, 215), 1)
    cv2.putText(img, f"pattern: {pattern or '-----'}", (panel_left + 24, 145),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
    cv2.putText(img, f"gesture: {gesture_name}", (panel_left + 24, 174),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
    cv2.putText(img, f"sent: {last_sent_label} ({last_sent_command or '--'})",
                (panel_left + 24, 203), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 230, 190), 1)

    y = 255
    cv2.putText(img, "Unlock sequence", (panel_left + 24, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
    y += 30
    for index, (name, unlock_pattern) in enumerate(UNLOCK_SEQUENCE):
        if unlocked or index < sequence_index:
            marker = "[x]"
            color = (80, 220, 120)
        elif index == sequence_index:
            marker = "[>]"
            color = (80, 170, 255)
        else:
            marker = "[ ]"
            color = (150, 160, 170)
        cv2.putText(img, f"{marker} {name}", (panel_left + 24, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        cv2.putText(img, unlock_pattern, (panel_left + 240, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 28

    if not unlocked:
        progress = min(1.0, unlock_frames / UNLOCK_STABLE_FRAMES_REQUIRED)
        cv2.rectangle(img, (panel_left + 24, y + 8), (width - 24, y + 20), (60, 70, 80), -1)
        cv2.rectangle(img, (panel_left + 24, y + 8),
                      (panel_left + 24 + int(312 * progress), y + 20), (80, 170, 255), -1)

    cv2.putText(img, "L: lock   R: reset   Q: quit", (panel_left + 24, height - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (190, 205, 215), 1)


def main():
    args = parse_args()
    ser = connect_serial(args.port, args.baud)
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print(f"Could not open camera {args.camera}.")
        print("Try a different camera index, for example:")
        print("  python fingers.py --camera 1")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    detector = HandDetector(detectionCon=0.8, maxHands=1)
    window_name = "Major Project - Gesture Prototype"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, args.width, args.height)
    if args.fullscreen:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    print("--- Gesture Tracking Started ---")
    print("Unlock sequence: OPEN, FIST, PEACE, THUMB")
    print("A camera window should open now.")
    print("Click the camera window, then press 'q' to quit.")

    candidate_command = None
    candidate_frames = 0
    last_sent_command = None
    last_sent_label = "NONE"
    unlocked = False
    sequence_index = 0
    candidate_unlock_pattern = None
    unlock_frames = 0

    send_command(ser, "LOCK")

    while True:
        success, img = cap.read()
        if not success:
            print("Camera read failed.")
            break

        hands, img = detector.findHands(img, draw=True)

        if hands:
            hand = hands[0]
            fingers = detector.fingersUp(hand)
            pattern, gesture_name = classify_gesture(fingers)

            if not unlocked:
                sequence_index, candidate_unlock_pattern, unlock_frames = update_unlock(
                    pattern, sequence_index, candidate_unlock_pattern, unlock_frames
                )
                if sequence_index >= len(UNLOCK_SEQUENCE):
                    unlocked = True
                    send_command(ser, "UNLOCK")
                    last_sent_command = "UNLOCK"
                    last_sent_label = "UNLOCKED"

            if gesture_name == "UNKNOWN" or not unlocked:
                candidate_command = None
                candidate_frames = 0
            else:
                if pattern == candidate_command:
                    candidate_frames += 1
                else:
                    candidate_command = pattern
                    candidate_frames = 1

                if candidate_frames >= STABLE_FRAMES_REQUIRED and pattern != last_sent_command:
                    send_command(ser, pattern)
                    last_sent_command = pattern
                    last_sent_label = gesture_name

            draw_status_panel(img, unlocked, pattern, gesture_name, last_sent_label, last_sent_command,
                              sequence_index, unlock_frames)
        else:
            candidate_command = None
            candidate_frames = 0
            candidate_unlock_pattern = None
            unlock_frames = 0
            draw_status_panel(img, unlocked, None, "NO HAND", last_sent_label, last_sent_command,
                              sequence_index, unlock_frames)

        cv2.imshow(window_name, img)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        if key == ord("l"):
            unlocked = False
            sequence_index, candidate_unlock_pattern, unlock_frames = reset_unlock()
            send_command(ser, "LOCK")
            last_sent_command = "LOCK"
            last_sent_label = "LOCKED"
        if key == ord("r"):
            sequence_index, candidate_unlock_pattern, unlock_frames = reset_unlock()

    cap.release()
    cv2.destroyAllWindows()
    if ser is not None:
        send_command(ser, "LOCK")
        ser.close()


if __name__ == "__main__":
    main()
