"""
video_timing.py
Functions to measure the time of a test (start and finish on the same line)
from a slow-motion video, by manually selecting the START and END frames.

Author: <your name>
Code written with the help of Claude (Anthropic), then read, tested and adapted.
"""

from pathlib import Path

import cv2
import numpy as np
import pandas as pd


# =====================================================================
# Settings
# =====================================================================

# Arrow key codes (different on each operating system)
#                 Mac     Windows   Linux
KEY_RIGHT = {63235, 2555904, 65363}
KEY_LEFT  = {63234, 2424832, 65361}
KEY_UP    = {63232, 2490368, 65362}
KEY_DOWN  = {63233, 2621440, 65364}
KEY_ENTER = {13, 10}
KEY_BACK  = {8, 127}      # Backspace (Windows/Linux = 8, Mac = 127)
KEY_ESC   = {27}

BAR_HEIGHT = 40           # height of the progress bar area (pixels)
BAR_MARGIN = 10           # space on the left/right of the bar (pixels)

# Columns of the results table
COLUMNS = ["name", "video", "start_frame", "end_frame", "fps", "time_s"]

# Video file extensions accepted (compared in lower case)
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi"}


# =====================================================================
# Video information
# =====================================================================

def get_video_info(video_path):
    """
    Open a video and return its fps and number of frames.

    video_path : path to the video file (Path object)
    returns    : (fps, n_frames)
    """
    video = cv2.VideoCapture(str(video_path))
    if not video.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps = video.get(cv2.CAP_PROP_FPS)
    n_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    video.release()
    return fps, n_frames


def ask_fps(file_fps, default_fps=240):
    """
    Ask the user for the real recording fps of the video.
    (Slow-motion videos are recorded at 240 fps but stored at 30 fps.)

    file_fps    : fps read from the file (shown as information only)
    default_fps : value used if the user just presses Enter
    returns     : the real fps (float)
    """
    print(f"fps stored in the file: {file_fps}")

    while True:
        answer = input(f"Real recording fps (press Enter for {default_fps}): ")

        if answer.strip() == "":
            return float(default_fps)

        try:
            fps = float(answer)
        except ValueError:
            print("Please type a number (e.g. 240).")
            continue

        if fps <= 0:
            print("The fps must be greater than 0.")
            continue

        return fps


def get_name_from_file(video_path):
    """
    Return the child's full name from the file name, in one piece.
    Example: "VICTOR_DJALAL_ROOS.MOV" -> "VICTOR_DJALAL_ROOS"
             "ELIES OSTA.MOV"         -> "ELIES_OSTA"
    """
    return video_path.stem.strip().replace(" ", "_")


# =====================================================================
# Display (window with texts and progress bar)
# =====================================================================

def put_text(img, text, position, color, size=0.8):
    """Write text with a black outline so it is readable on any background."""
    cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, size, (0, 0, 0), 4)
    cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, size, color, 2)


def frame_to_x(index, n_frames, width):
    """Convert a frame number into a horizontal position on the bar."""
    return BAR_MARGIN + int(index / (n_frames - 1) * (width - 2 * BAR_MARGIN))


def draw_display(frame, index, n_frames, fps, start, end):
    """
    Build the image shown in the window: video frame + texts + progress bar.
    Colors are in BGR order (Blue, Green, Red) in OpenCV.
    """
    h, w = frame.shape[:2]

    # Black band under the frame for the progress bar
    band = np.zeros((BAR_HEIGHT, w, 3), dtype=np.uint8)
    img = np.vstack([frame, band])

    # Progress bar: grey background, light part = where we are
    y_top, y_bottom = h + 10, h + BAR_HEIGHT - 10
    cv2.rectangle(img, (BAR_MARGIN, y_top), (w - BAR_MARGIN, y_bottom), (80, 80, 80), -1)
    x_now = frame_to_x(index, n_frames, w)
    cv2.rectangle(img, (BAR_MARGIN, y_top), (x_now, y_bottom), (200, 200, 200), -1)

    # Marks on the bar: green line = START, red line = END
    for mark, color in ((start, (0, 255, 0)), (end, (0, 0, 255))):
        if mark is not None:
            x = frame_to_x(mark, n_frames, w)
            cv2.line(img, (x, h + 2), (x, h + BAR_HEIGHT - 2), color, 3)

    # Line 1: frame number and video time
    put_text(img, f"frame {index}/{n_frames - 1} | video {index / fps:.3f} s",
             (20, 35), (255, 255, 255))

    # Line 2: depends on the step (no start yet / running / finished)
    if start is None:
        put_text(img, "Press ENTER on the START frame", (20, 75), (0, 255, 255))
    elif end is None:
        put_text(img, f"START  |  test time: {(index - start) / fps:.3f} s",
                 (20, 75), (0, 255, 0), 1.0)
    else:
        put_text(img, f"END  |  test time: {(end - start) / fps:.3f} s",
                 (20, 75), (0, 0, 255), 1.0)
        put_text(img, "ENTER = save | BACKSPACE = undo | ESC = cancel",
                 (20, 115), (255, 255, 255), 0.6)

    return img


# =====================================================================
# Measurement of one video
# =====================================================================

def measure_test(video_path, real_fps, scale=0.5):
    """
    Open the video, let the user mark START and END, return the result.

    Keys: right/left arrow = +1/-1 frame (hold to scroll)
          up/down arrow    = +10/-10 frames
          click/drag on the bar = jump in the video
          Enter (1st) = START, Enter (2nd) = END, Enter (3rd) = save
          Backspace = undo last mark, Escape = cancel

    returns : dict with name, frames and time (s), or None if cancelled
    """
    video = cv2.VideoCapture(str(video_path))
    if not video.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    n_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    # "state" is shared with the mouse function below
    state = {"index": 0, "frame_w": 1, "frame_h": 1}

    def on_mouse(event, x, y, flags, param):
        """Click or drag on the bar to jump in the video."""
        if y < state["frame_h"]:
            return
        clicked = event == cv2.EVENT_LBUTTONDOWN
        dragged = event == cv2.EVENT_MOUSEMOVE and (flags & cv2.EVENT_FLAG_LBUTTON)
        if clicked or dragged:
            ratio = (x - BAR_MARGIN) / (state["frame_w"] - 2 * BAR_MARGIN)
            ratio = max(0.0, min(ratio, 1.0))
            state["index"] = int(round(ratio * (n_frames - 1)))

    window = "Measure test"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)

    start, end = None, None
    last_index, frame = None, None
    saved = False

    while True:
        state["index"] = max(0, min(state["index"], n_frames - 1))
        index = state["index"]

        # Read a new frame only if the position changed (faster)
        if index != last_index:
            video.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, raw = video.read()
            if not ok:
                state["index"] = max(index - 1, 0)
                continue
            frame = cv2.resize(raw, None, fx=scale, fy=scale)
            state["frame_h"], state["frame_w"] = frame.shape[:2]
            last_index = index

        cv2.imshow(window, draw_display(frame, index, n_frames, real_fps, start, end))

        # Wait 30 ms for a key (-1 if none), so the mouse bar stays reactive
        key = cv2.waitKeyEx(30)

        if key in KEY_RIGHT:
            state["index"] += 1
        elif key in KEY_LEFT:
            state["index"] -= 1
        elif key in KEY_UP:
            state["index"] += 10
        elif key in KEY_DOWN:
            state["index"] -= 10
        elif key in KEY_ENTER:
            if start is None:
                start = index
            elif end is None:
                if index > start:
                    end = index
                else:
                    print("END must be after START.")
            else:
                saved = True
                break
        elif key in KEY_BACK:
            if end is not None:
                end = None
            elif start is not None:
                start = None
        elif key in KEY_ESC:
            break
        elif key != -1:
            print("Unknown key code:", key)

    # Close the video and the window (extra waitKey calls needed on Mac)
    video.release()
    cv2.destroyAllWindows()
    for _ in range(5):
        cv2.waitKey(1)

    if not saved:
        return None

    return {
        "name": get_name_from_file(video_path),
        "start_frame": start,
        "end_frame": end,
        "fps": real_fps,
        "time_s": round((end - start) / real_fps, 3),
    }


# =====================================================================
# Results file (CSV) and measurement of all videos
# =====================================================================

def list_videos(folder):
    """Return the list of video files in the folder, sorted by name."""
    videos = [f for f in folder.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(videos)


def load_results(csv_path):
    """Read the results file if it exists, otherwise return an empty table."""
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(columns=COLUMNS)


def save_result(result, csv_path):
    """
    Add one result to the CSV file.
    If the video was already measured, its old line is replaced.
    """
    table = load_results(csv_path)
    table = table[table["video"] != result["video"]]
    new_line = pd.DataFrame([result], columns=COLUMNS)
    table = pd.concat([table, new_line], ignore_index=True)
    table = table.sort_values("video")
    table.to_csv(csv_path, index=False)


def measure_all_videos(folder, csv_path, real_fps, redo=False):
    """
    Measure every video of the folder one after the other.

    redo=False : skip videos already in the results file
    redo=True  : measure all videos again
    Escape in the video window stops the session.
    """
    videos = list_videos(folder)
    done = set(load_results(csv_path)["video"])

    for i, video_path in enumerate(videos, start=1):
        if video_path.name in done and not redo:
            print(f"[{i}/{len(videos)}] {video_path.name}: already measured, skipped")
            continue

        print(f"[{i}/{len(videos)}] {video_path.name}: measuring...")
        result = measure_test(video_path, real_fps)

        if result is None:
            print("Session stopped. Results saved so far are kept.")
            break

        result["video"] = video_path.name
        save_result(result, csv_path)
        print(f"   -> {result['name']}: {result['time_s']:.3f} s (saved)")

    print("Done.")


# =====================================================================
# Anonymisation (names are replaced by P01, P02, ...)
# =====================================================================

def make_id_table(names, id_table_path):
    """
    Give an id (P01, P02, ...) to each name and save the table.
    Ids already given are kept, new names get the next numbers,
    so an id never changes when new videos are added.
    """
    if id_table_path.exists():
        table = pd.read_csv(id_table_path)
    else:
        table = pd.DataFrame(columns=["name", "id"])

    known = set(table["name"])
    new_names = sorted(n for n in set(names) if n not in known)

    next_number = len(table) + 1
    new_rows = [{"name": n, "id": f"P{next_number + i:02d}"}
                for i, n in enumerate(new_names)]

    table = pd.concat([table, pd.DataFrame(new_rows, columns=["name", "id"])],
                      ignore_index=True)
    table.to_csv(id_table_path, index=False)
    return table


def anonymize_results(results_csv, id_table_path, info_csv, output_csv):
    """
    Build the anonymous results file used in R:
    id, frames, fps, time measured with the video, age at the test (years), sex.
    The birth dates stay private: only the age is saved.
    """
    measures = load_results(results_csv)
    if measures.empty:
        print("No measures yet: nothing to anonymize.")
        return None

    # Add the id of each child
    id_table = make_id_table(measures["name"], id_table_path)
    data = measures.merge(id_table, on="name")

    # Add the age at the test and the sex, from the private info file
    if info_csv.exists():
        info = pd.read_csv(info_csv, parse_dates=["birth_date", "test_date"])
        data = data.merge(info, on="name", how="left")
        # Age in years = number of days between the two dates / 365.25
        data["age_years"] = ((data["test_date"] - data["birth_date"]).dt.days
                             / 365.25).round(2)
    else:
        print(f"{info_csv} not found: age and sex left empty.")
        data["age_years"] = pd.NA
        data["sex"] = pd.NA

    # Keep only non-identifying columns (no name, no birth date)
    anonymous = data[["id", "start_frame", "end_frame", "fps",
                      "time_s", "age_years", "sex"]]
    anonymous = anonymous.rename(columns={"time_s": "time_video"}).sort_values("id")
    anonymous.to_csv(output_csv, index=False)

    # Warn if some ages are missing
    missing = anonymous.loc[anonymous["age_years"].isna(), "id"].tolist()
    if missing:
        print("Age missing for:", ", ".join(missing))

    print(f"Anonymous file saved: {output_csv}")
    return anonymous