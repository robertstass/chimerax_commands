# Commands to add movie keyframe timestamp tracking to ChimeraX.
# Written in the same single-file command style as selectiontocsv.

"""
chimerax_movie_keyframes_v3.py

Write named keyframe timestamps from a ChimeraX movie recording.

`moviekey mark` asks ChimeraX's own movie recorder how many frames
have been recorded so far via `session.movie.getFrameCount()`.

Typical CXC use:

    movie record supersample 3
    moviekey start ~/Desktop/keyframes.csv framerate 25 overwrite true

    moviekey mark start

    view close frames 90
    wait 90
    moviekey mark close_view

    movie crossfade frames 30
    wait 30
    moviekey mark after_crossfade

    moviekey write
    moviekey stop
    movie encode ~/Desktop/movie.mp4 framerate 25 quality high

CSV columns are exactly:

    Name,frame,time

where time is frame/framerate in seconds.

"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from chimerax.core.commands import (
    BoolArg,
    CmdDesc,
    FloatArg,
    IntArg,
    SaveFileNameArg,
    StringArg,
    register,
)
from chimerax.core.errors import UserError


STATE_ATTR = "_moviekey_state"


@dataclass
class MovieKeyState:
    path: Path
    framerate: float
    overwrite: bool = True
    active: bool = True
    debug: bool = False
    fallback_frame: int = 0
    marks: List[Dict[str, object]] = field(default_factory=list)

    def time_for_frame(self, frame: int) -> float:
        return float(frame) / float(self.framerate)

    def add_mark(self, name: str, frame: int):
        self.marks.append(
            {
                "Name": str(name),
                "frame": int(frame),
                "time": self.time_for_frame(int(frame)),
            }
        )


def _state(session) -> MovieKeyState:
    st = getattr(session, STATE_ATTR, None)
    if st is None:
        raise UserError("moviekey has not been started; use: moviekey start <csv-path> framerate <fps>")
    return st


def _movie_object(session):
    return getattr(session, "movie", None)


def _movie_frame_count(session, require_recording=True) -> int:
    """Return ChimeraX movie recorder's current frame count.

    This intentionally uses the recorder state rather than drawing triggers or
    command parsing. It should therefore include recorder-managed postprocessing
    such as movie crossfade once the relevant wait has completed.
    """
    movie = _movie_object(session)
    if movie is None:
        raise UserError("No ChimeraX movie recorder found. Run 'movie record' before using moviekey mark.")

    if require_recording:
        try:
            recording = bool(movie.is_recording())
        except Exception:
            recording = False
        if not recording:
            raise UserError("ChimeraX movie recorder is not recording. Run 'movie record' before using moviekey mark.")

    if not hasattr(movie, "getFrameCount"):
        raise UserError("ChimeraX movie recorder does not expose getFrameCount().")

    return int(movie.getFrameCount())


def moviekey_start(session, path, framerate=25.0, overwrite=True, debug=False):
    """Start collecting named keyframes for the active movie recording."""
    if framerate <= 0:
        raise UserError("framerate must be greater than zero")

    path = Path(path).expanduser()
    if path.exists() and not overwrite:
        raise UserError(f"File already exists: {path}")

    st = MovieKeyState(
        path=path,
        framerate=float(framerate),
        overwrite=bool(overwrite),
        active=True,
        debug=bool(debug),
    )
    setattr(session, STATE_ATTR, st)

    # Do not require movie recording at start, because a user may choose to put
    # moviekey start immediately before movie record. But tell them what we see.
    movie = _movie_object(session)
    if movie is not None and hasattr(movie, "getFrameCount"):
        try:
            fc = int(movie.getFrameCount())
            session.logger.info(
                f"moviekey started: {path} at {framerate:g} fps; current movie frame count is {fc}"
            )
            return
        except Exception:
            pass

    session.logger.info(
        f"moviekey started: {path} at {framerate:g} fps; no active movie recorder frame count yet"
    )


def moviekey_mark(session, name, frame=None, time=None):
    """Mark the current recorded movie frame with a name."""
    st = _state(session)
    if not st.active:
        raise UserError("moviekey is stopped or paused")

    if time is not None and frame is not None:
        raise UserError("Specify either frame or time, not both")

    if time is not None:
        mark_frame = int(round(float(time) * float(st.framerate)))
    elif frame is not None:
        mark_frame = int(frame)
    else:
        mark_frame = _movie_frame_count(session, require_recording=True)

    if mark_frame < 0:
        raise UserError("frame must be non-negative")

    st.add_mark(name, mark_frame)
    row = st.marks[-1]
    session.logger.info(
        f"moviekey mark {row['Name']}: frame {row['frame']}, time {row['time']:.6f} s"
    )


def moviekey_write(session, path=None):
    """Write movie keyframes to CSV."""
    st = _state(session)
    out = Path(path).expanduser() if path is not None else st.path
    if out.exists() and not st.overwrite:
        raise UserError(f"File already exists: {out}")
    if out.parent and not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Name", "frame", "time"])
        writer.writeheader()
        for row in st.marks:
            writer.writerow(
                {
                    "Name": row["Name"],
                    "frame": int(row["frame"]),
                    "time": f"{float(row['time']):.6f}",
                }
            )

    session.logger.info(f"moviekey wrote {len(st.marks)} keyframes to {out}")


def moviekey_status(session):
    """Report current movie keyframe status."""
    st = _state(session)
    try:
        current_frame = _movie_frame_count(session, require_recording=False)
        movie_status = f"movie_frame={current_frame}, movie_time={st.time_for_frame(current_frame):.6f} s"
    except Exception as e:
        movie_status = f"movie_frame unavailable ({e})"

    session.logger.info(
        f"moviekey status: active={st.active}, {movie_status}, marks={len(st.marks)}, "
        f"framerate={st.framerate:g} fps, path={st.path}"
    )


def moviekey_stop(session, write=False):
    """Stop collecting keyframes. Optionally write the CSV first."""
    st = _state(session)
    if write:
        moviekey_write(session)
    st.active = False
    session.logger.info("moviekey stopped")


def moviekey_pause(session):
    """Pause keyframe marking without deleting marks."""
    st = _state(session)
    st.active = False
    session.logger.info("moviekey paused")


def moviekey_resume(session):
    """Resume keyframe marking."""
    st = _state(session)
    st.active = True
    session.logger.info("moviekey resumed")


def moviekey_reset(session):
    """Clear all stored marks."""
    st = _state(session)
    st.marks.clear()
    session.logger.info("moviekey cleared all marks")


def register_command(logger):
    register(
        "moviekey start",
        CmdDesc(
            required=[("path", SaveFileNameArg)],
            keyword=[
                ("framerate", FloatArg),
                ("overwrite", BoolArg),
                ("debug", BoolArg),
            ],
            synopsis="Start collecting movie keyframe timestamps from ChimeraX's movie recorder frame count",
        ),
        moviekey_start,
        logger=logger,
    )

    register(
        "moviekey mark",
        CmdDesc(
            required=[("name", StringArg)],
            keyword=[("frame", IntArg), ("time", FloatArg)],
            synopsis="Mark the current recorded movie frame with a name",
        ),
        moviekey_mark,
        logger=logger,
    )

    register(
        "moviekey write",
        CmdDesc(
            keyword=[("path", SaveFileNameArg)],
            synopsis="Write movie keyframes to CSV",
        ),
        moviekey_write,
        logger=logger,
    )

    register(
        "moviekey status",
        CmdDesc(synopsis="Report current movie keyframe status"),
        moviekey_status,
        logger=logger,
    )

    register(
        "moviekey stop",
        CmdDesc(
            keyword=[("write", BoolArg)],
            synopsis="Stop collecting movie keyframe timestamps",
        ),
        moviekey_stop,
        logger=logger,
    )

    register(
        "moviekey pause",
        CmdDesc(synopsis="Pause movie keyframe marking"),
        moviekey_pause,
        logger=logger,
    )

    register(
        "moviekey resume",
        CmdDesc(synopsis="Resume movie keyframe marking"),
        moviekey_resume,
        logger=logger,
    )

    register(
        "moviekey reset",
        CmdDesc(synopsis="Clear all moviekey marks"),
        moviekey_reset,
        logger=logger,
    )


register_command(session.logger)
