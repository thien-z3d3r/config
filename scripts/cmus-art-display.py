#!/usr/bin/env python3

import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "cmus-art"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

FALLBACK_ASCII_VINYL = """
            .▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄.
        .▄█▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓█▄.
      ▄▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▄
    ▄▓▓▓▓▓▓▓▓▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▓▓▓▓▓▓▓▓▄
   █▓▓▓▓▓▓▀    .▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄.    ▀▓▓▓▓▓▓█
  █▓▓▓▓▓▀   .▄▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▄.   ▀▓▓▓▓▓█
 ▐▓▓▓▓▓   ▄▓▓▓▓▓▓▀▀▀▀▀▀▀▀▀▀▀▀▀▓▓▓▓▓▓▄   ▓▓▓▓▓▌
 █▓▓▓▓   ▓▓▓▓▓▀   .▄▄▄▄▄▄▄.   ▀▓▓▓▓▓   ▓▓▓▓█
 █▓▓▓▌  ▐▓▓▓▓   ▄█▓▓▓▓▓▓▓▓▓█▄   ▓▓▓▓▌  ▐▓▓▓█
 █▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓▓█▀ ▀█▓▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓█
 █▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓▓   ●   ▓▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓█
 █▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓▓█▄ ▄█▓▓▓▓▌  ▐▓▓▓▌  ▐▓▓▓█
 █▓▓▓▌  ▐▓▓▓▓   ▀█▓▓▓▓▓▓▓▓▓█▀   ▓▓▓▓▌  ▐▓▓▓█
 █▓▓▓▓   ▓▓▓▓▓▄   '▀▀▀▀▀▀▀'   ▄▓▓▓▓▓   ▓▓▓▓█
 ▐▓▓▓▓▓   ▀▓▓▓▓▓▓▄▄▄▄▄▄▄▄▄▄▄▄▓▓▓▓▓▓▀   ▓▓▓▓▓▌
  █▓▓▓▓▓▄   '▀▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▀'   ▄▓▓▓▓▓█
   █▓▓▓▓▓▓▄    '▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀'    ▄▓▓▓▓▓▓█
    ▀▓▓▓▓▓▓▓▓▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▓▓▓▓▓▓▓▓▀
      ▀▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▀
        '▀█▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓█▀'
            '▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀'
"""

FALLBACK_ASCII_STOPPED = """
  ██████╗███╗   ███╗██╗   ██╗███████╗
 ██╔════╝████╗ ████║██║   ██║██╔════╝
 ██║     ██╔████╔██║██║   ██║███████╗
 ██║     ██║╚██╔╝██║██║   ██║╚════██║
 ╚██████╗██║ ╚═╝ ██║╚██████╔╝███████║
  ╚═════╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝

        C* Music Player (cmus)
      Select and play a track
"""


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def visible_length(text: str) -> int:
    return len(strip_ansi(text))


def center_line(line: str, width: int) -> str:
    vis_len = visible_length(line)
    pad = max(0, (width - vis_len) // 2)
    return (" " * pad) + line


def extract_flac_picture(flac_path: str, out_path: str) -> bool:
    try:
        with open(flac_path, "rb") as f:
            header = f.read(4)
            if header != b"fLaC":
                return False
            while True:
                bh = f.read(4)
                if len(bh) < 4:
                    break
                is_last = (bh[0] & 0x80) != 0
                btype = bh[0] & 0x7F
                blen = int.from_bytes(bh[1:4], "big")
                data = f.read(blen)
                if btype == 6:  # picture block
                    mime_len = int.from_bytes(data[4:8], "big")
                    idx = 8 + mime_len
                    desc_len = int.from_bytes(data[idx : idx + 4], "big")
                    idx += 4 + desc_len + 16  # skip description, dimensions, depth
                    img_len = int.from_bytes(data[idx : idx + 4], "big")
                    idx += 4
                    img_data = data[idx : idx + img_len]
                    if img_data:
                        with open(out_path, "wb") as out_f:
                            out_f.write(img_data)
                        return True
                if is_last:
                    break
    except Exception:
        pass
    return False


def extract_cover_art(audio_file: str) -> str | None:
    if not audio_file or not os.path.exists(audio_file):
        return None

    try:
        mtime = os.path.getmtime(audio_file)
    except OSError:
        mtime = 0

    key = hashlib.md5(f"{audio_file}:{mtime}".encode("utf-8")).hexdigest()
    cached_img = CACHE_DIR / f"{key}.img"

    if cached_img.exists() and cached_img.stat().st_size > 0:
        return str(cached_img)

    if audio_file.lower().endswith(".flac"):
        if extract_flac_picture(audio_file, str(cached_img)):
            return str(cached_img)

    try:
        res = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                audio_file,
                "-an",
                "-update",
                "1",
                "-frames:v",
                "1",
                str(cached_img),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if res.returncode == 0 and cached_img.exists() and cached_img.stat().st_size > 0:
            return str(cached_img)
    except Exception:
        pass

    song_dir = Path(audio_file).parent
    candidates = [
        "cover.jpg",
        "cover.png",
        "folder.jpg",
        "folder.png",
        "album.jpg",
        "album.png",
        "front.jpg",
        "front.png",
        "art.jpg",
        "art.png",
    ]
    for c in candidates:
        img_path = song_dir / c
        if img_path.exists() and img_path.stat().st_size > 0:
            return str(img_path)

    return None


def get_audio_properties(audio_file: str, duration: int = 0) -> dict:
    props = {
        "codec": "",
        "sample_rate": "",
        "bit_depth": "",
        "bit_rate": "",
    }
    if not audio_file or not os.path.exists(audio_file):
        return props

    try:
        res = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,bits_per_raw_sample,bit_rate:format=bit_rate",
                "-of",
                "default=noprint_wrappers=1",
                audio_file,
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            br_candidates = []
            for line in res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "codec_name" and v:
                        props["codec"] = v.upper()
                    elif k == "sample_rate" and v and v != "N/A":
                        try:
                            sr = int(v)
                            if sr >= 1000:
                                props["sample_rate"] = f"{sr / 1000:.1f} kHz"
                            else:
                                props["sample_rate"] = f"{sr} Hz"
                        except ValueError:
                            props["sample_rate"] = v
                    elif k == "bits_per_raw_sample" and v and v != "N/A":
                        props["bit_depth"] = f"{v}-bit"
                    elif k == "bit_rate" and v != "N/A":
                        br_candidates.append(v)

            if br_candidates:
                try:
                    chosen = br_candidates[0] if len(br_candidates) == 1 else br_candidates[-1]
                    kbps = int(chosen) // 1000
                    props["bit_rate"] = f"{kbps} kbps"
                except ValueError:
                    pass
    except Exception:
        pass

    if not props["bit_rate"] and duration > 0:
        try:
            fsize = os.path.getsize(audio_file)
            kbps = (fsize * 8) // (duration * 1000)
            props["bit_rate"] = f"{kbps} kbps"
        except Exception:
            pass

    return props


def get_cmus_status() -> dict:
    try:
        res = subprocess.run(
            ["cmus-remote", "-Q"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode != 0:
            return {"status": "not_running"}
    except Exception:
        return {"status": "not_running"}

    data = {
        "status": "stopped",
        "file": "",
        "artist": "",
        "album": "",
        "title": "",
        "date": "",
        "duration": 0,
        "position": 0,
    }

    for line in res.stdout.splitlines():
        if line.startswith("status "):
            data["status"] = line.split(" ", 1)[1].strip()
        elif line.startswith("file "):
            data["file"] = line.split(" ", 1)[1].strip()
        elif line.startswith("duration "):
            try:
                data["duration"] = int(line.split(" ", 1)[1].strip())
            except ValueError:
                data["duration"] = 0
        elif line.startswith("position "):
            try:
                data["position"] = int(line.split(" ", 1)[1].strip())
            except ValueError:
                data["position"] = 0
        elif line.startswith("tag "):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                tag_name = parts[1].lower()
                tag_val = parts[2].strip()
                if tag_name in data and not data[tag_name]:
                    data[tag_name] = tag_val
                elif tag_name == "title":
                    data["title"] = tag_val
                elif tag_name == "artist":
                    data["artist"] = tag_val
                elif tag_name == "album":
                    data["album"] = tag_val
                elif tag_name == "date":
                    data["date"] = tag_val

    if not data["title"] and data["file"]:
        data["title"] = Path(data["file"]).stem

    return data


def format_time(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


SYMBOL_PRESETS = {
    "detailed": "block+half+quad+sextant+braille+stipple+wedge+dot+diagonal",
    "hybrid": "block+half+quad+sextant+braille+stipple+wedge+dot+diagonal",
    "all": "all-wide-ascii-alpha-digit-alnum-bad",
    "braille": "braille",
    "sextant": "half+quad+sextant+block",
    "blocks": "block+border+half+quad+sextant",
}


def load_art_config() -> dict:
    cfg = {
        "symbols": SYMBOL_PRESETS["detailed"],
        "work": "9",
        "color_extractor": "median",
    }

    config_file = Path.home() / ".config" / "cmus" / "art.conf"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip().lower(), v.strip()
                    if k == "symbols" and v:
                        cfg["symbols"] = SYMBOL_PRESETS.get(v.lower(), v)
                    elif k == "work" and v:
                        cfg["work"] = v
                    elif k in ("color_extractor", "extractor") and v:
                        cfg["color_extractor"] = v
        except Exception:
            pass

    env_sym = os.environ.get("CMUS_ART_SYMBOLS", "").strip()
    if env_sym:
        cfg["symbols"] = SYMBOL_PRESETS.get(env_sym.lower(), env_sym)

    env_work = os.environ.get("CMUS_ART_WORK", "").strip()
    if env_work:
        cfg["work"] = env_work

    env_extr = os.environ.get("CMUS_ART_COLOR_EXTRACTOR", "").strip()
    if env_extr:
        cfg["color_extractor"] = env_extr

    return cfg


def render_art(img_path: str | None, width: int, height: int) -> list[str]:
    if not img_path:
        lines = []
        for line in FALLBACK_ASCII_VINYL.strip("\n").split("\n"):
            lines.append(f"\033[38;2;203;166;247m{line}\033[0m")
        return lines

    target_w = max(10, width)
    target_h = max(5, height)

    cfg = load_art_config()

    cmd = [
        "chafa",
        "-f",
        "symbols",
        f"--symbols={cfg['symbols']}",
        "--color-space=din99d",
        f"--color-extractor={cfg['color_extractor']}",
        "-c",
        "full",
        "-w",
        str(cfg["work"]),
        "--scale=max",
        f"--size={target_w}x{target_h}",
        img_path,
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            clean = (
                res.stdout.replace("\x1b[?25h", "")
                .replace("\x1b[?25l", "")
                .strip("\n")
            )
            return clean.split("\n")
    except Exception:
        pass

    return [line for line in FALLBACK_ASCII_VINYL.strip("\n").split("\n")]


class DisplayManager:
    def __init__(self):
        self.running = True
        self.last_file = ""
        self.last_img_path = None
        self.last_art_lines = []
        self.last_audio_props = {}
        self.last_size = (0, 0)
        self.last_printed_lines = 0
        self.last_frame_key = None

        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        signal.signal(signal.SIGWINCH, self.on_resize)
        signal.signal(signal.SIGUSR1, self.on_signal)

    def cleanup(self, *args):
        self.running = False
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()
        sys.exit(0)

    def on_resize(self, *args):
        self.last_size = (0, 0)

    def on_signal(self, *args):
        self.last_frame_key = None
        self.last_art_lines = []

    def run(self):
        sys.stdout.write("\033[?25l\033[2J\033[H")
        sys.stdout.flush()

        while self.running:
            try:
                self.draw_frame()
            except Exception:
                pass
            time.sleep(0.4)

    def draw_frame(self):
        cols, rows = shutil.get_terminal_size((80, 24))

        if (cols, rows) != self.last_size:
            self.last_size = (cols, rows)
            self.last_art_lines = []
            self.last_frame_key = None
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

        status_info = get_cmus_status()

        frame_key = (
            status_info.get("status"),
            status_info.get("file"),
            status_info.get("position"),
            cols,
            rows,
        )
        if frame_key == self.last_frame_key:
            return
        self.last_frame_key = frame_key

        out_lines = []

        if status_info["status"] == "not_running":
            banner_lines = FALLBACK_ASCII_STOPPED.strip("\n").split("\n")
            top_pad = max(0, (rows - len(banner_lines) - 4) // 2)
            for _ in range(top_pad):
                out_lines.append("")
            for l in banner_lines:
                out_lines.append(center_line(f"\033[1;38;2;137;220;235m{l}\033[0m", cols))
            out_lines.append("")
            out_lines.append(center_line("\033[38;2;249;226;175mWaiting for cmus to start...\033[0m", cols))
        elif status_info["status"] == "stopped" or not status_info["file"]:
            banner_lines = FALLBACK_ASCII_STOPPED.strip("\n").split("\n")
            top_pad = max(0, (rows - len(banner_lines) - 4) // 2)
            for _ in range(top_pad):
                out_lines.append("")
            for l in banner_lines:
                out_lines.append(center_line(f"\033[1;38;2;137;220;235m{l}\033[0m", cols))
            out_lines.append("")
            out_lines.append(center_line("\033[38;2;108;112;134m[ ⏹ STOPPED ]\033[0m", cols))
        else:
            curr_file = status_info["file"]
            reserved_meta_lines = 7
            avail_art_h = max(5, rows - reserved_meta_lines)
            avail_art_w = max(10, cols - 4)

            if curr_file != self.last_file or not self.last_art_lines:
                self.last_file = curr_file
                self.last_img_path = extract_cover_art(curr_file)
                self.last_art_lines = render_art(
                    self.last_img_path, avail_art_w, avail_art_h
                )
                self.last_audio_props = get_audio_properties(
                    curr_file, status_info["duration"]
                )

            art_h = len(self.last_art_lines)
            total_content_lines = art_h + 6
            top_pad = max(0, (rows - total_content_lines) // 2)

            for _ in range(top_pad):
                out_lines.append("")

            for art_line in self.last_art_lines:
                out_lines.append(center_line(art_line, cols))

            out_lines.append("")

            title = status_info["title"] or "Unknown Title"
            artist = status_info["artist"] or "Unknown Artist"
            album = status_info["album"] or ""
            date = status_info["date"] or ""

            max_text_w = max(10, cols - 6)
            if len(title) > max_text_w:
                title = title[: max_text_w - 3] + "..."
            if len(artist) > max_text_w:
                artist = artist[: max_text_w - 3] + "..."

            out_lines.append(center_line(f"\033[1;38;2;205;214;244m{title}\033[0m", cols))

            album_str = f" - {album}" if album else ""
            if date:
                album_str += f" ({date.split('/')[0]})"
            artist_line = f"{artist}{album_str}"
            if len(artist_line) > max_text_w:
                artist_line = artist_line[: max_text_w - 3] + "..."
            out_lines.append(center_line(f"\033[38;2;180;190;254m{artist_line}\033[0m", cols))

            spec_parts = []
            codec = self.last_audio_props.get("codec")
            if codec:
                spec_parts.append(f"\033[1;38;2;137;220;235m{codec}\033[0m")
            depth = self.last_audio_props.get("bit_depth")
            if depth:
                spec_parts.append(f"\033[38;2;249;226;175m{depth}\033[0m")
            sr = self.last_audio_props.get("sample_rate")
            if sr:
                spec_parts.append(f"\033[38;2;166;227;161m{sr}\033[0m")
            br = self.last_audio_props.get("bit_rate")
            if br:
                spec_parts.append(f"\033[38;2;203;166;247m{br}\033[0m")

            if spec_parts:
                dot = "\033[38;2;88;91;112m • \033[0m"
                specs_line = dot.join(spec_parts)
                out_lines.append(center_line(specs_line, cols))
            else:
                out_lines.append("")

            pos = status_info["position"]
            dur = status_info["duration"]
            pos_str = format_time(pos)
            dur_str = format_time(dur) if dur > 0 else "--:--"

            state_badge = (
                "\033[1;38;2;166;227;161m▶\033[0m"
                if status_info["status"] == "playing"
                else "\033[1;38;2;249;226;175m⏸\033[0m"
            )

            time_labels_w = len(pos_str) + len(dur_str) + 6
            bar_w = max(6, min(cols - time_labels_w, 32))
            if dur > 0:
                filled_w = int((pos / dur) * bar_w)
                filled_w = max(0, min(bar_w, filled_w))
            else:
                filled_w = 0

            empty_w = bar_w - filled_w
            bar_str = f"\033[1;38;2;137;180;250m{'━' * filled_w}\033[0m\033[38;2;69;71;90m{'─' * max(0, empty_w)}\033[0m"
            time_styled = f"\033[38;2;186;194;222m{pos_str}\033[0m"
            dur_styled = f"\033[38;2;166;173;200m{dur_str}\033[0m"
            prog_line = f"{state_badge}  {time_styled} [{bar_str}] {dur_styled}"
            out_lines.append(center_line(prog_line, cols))

        out_lines = out_lines[: rows - 1]

        buf = ["\033[H"]
        for line in out_lines:
            buf.append(line + "\033[K\n")

        if self.last_printed_lines > len(out_lines):
            for _ in range(self.last_printed_lines - len(out_lines)):
                buf.append("\033[K\n")
        self.last_printed_lines = len(out_lines)

        sys.stdout.write("".join(buf))
        sys.stdout.flush()


def main():
    display = DisplayManager()
    display.run()


if __name__ == "__main__":
    main()
