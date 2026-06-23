#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2026)

"""
chimerax_clip_list_relative.py

ChimeraX command module that reports the current clip planes in the coordinate
system of a chosen model and relative to a chosen reference position.

The built-in ``clip list`` output is useful, but it is often harder to interpret
when you want the values relative to a particular model frame and reference
point. This module reads ChimeraX clip planes, converts their geometry into the
chosen model's coordinate system, and computes the signed distance of each plane
from an explicit reference position.

That lets you recover values in the same spirit as:

    clip near -32 far -10 coordinateSystem #1 position 0,0,0

"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from chimerax.core.commands import CmdDesc, BoolArg, Float3Arg, ModelArg, register
from chimerax.core.errors import UserError


def _xyz3(v) -> Tuple[float, float, float]:
    if v is None:
        raise UserError("Missing coordinate value")
    if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
        return float(v.x), float(v.y), float(v.z)
    try:
        return float(v[0]), float(v[1]), float(v[2])
    except Exception as e:
        raise UserError(f"Could not interpret coordinate value: {v!r}") from e


def _as_array3(v) -> np.ndarray:
    return np.asarray(_xyz3(v), dtype=float)


def _transform_point(place, point) -> np.ndarray:
    p = _as_array3(point)
    if place is None:
        return p
    if hasattr(place, "transform_points"):
        return np.asarray(place.transform_points(p[None, :])[0], dtype=float)
    return np.asarray(place * p, dtype=float)


def _transform_normal(place, normal) -> np.ndarray:
    n = _as_array3(normal)
    if place is None:
        return n
    if hasattr(place, "transform_normals"):
        return np.asarray(place.transform_normals(n[None, :])[0], dtype=float)
    if hasattr(place, "transform_vector"):
        return np.asarray(place.transform_vector(n), dtype=float)
    return np.asarray(place * n, dtype=float)


def _inverse_place(place):
    if place is None:
        return None
    if hasattr(place, "inverse"):
        return place.inverse()
    raise UserError("Could not invert model coordinate system")


def _model_scene_place(model):
    for attr in ("scene_position", "position"):
        if hasattr(model, attr):
            place = getattr(model, attr)
            if place is not None:
                return place
    if hasattr(model, "get_scene_position"):
        return model.get_scene_position()
    raise UserError(f"Could not get a scene position for model {model!r}")


def _model_spec(model) -> str:
    if hasattr(model, "id_string"):
        return f"#{model.id_string}"
    if hasattr(model, "id"):
        return f"#{model.id}"
    return "<model>"


def _clip_container(view):
    candidates = (
        view,
        getattr(view, "clip_planes", None),
        getattr(view, "clipping", None),
        getattr(view, "clips", None),
        getattr(view, "scene", None),
    )
    for c in candidates:
        if c is None:
            continue
        if hasattr(c, "planes") and (
            hasattr(c, "add_plane") or hasattr(c, "remove_plane") or hasattr(c, "set_clip_position")
        ):
            return c
        if hasattr(c, "__iter__") and not hasattr(c, "__dict__"):
            return c
        for attr in ("clip_planes", "planes", "items"):
            if hasattr(c, attr):
                return getattr(c, attr)
    raise UserError("Could not locate the active clipping planes in this ChimeraX build")


def _iter_planes(clip_container) -> Iterable[object]:
    if clip_container is None:
        return []
    if callable(clip_container):
        clip_container = clip_container()
    if hasattr(clip_container, "planes"):
        planes = getattr(clip_container, "planes")
        return planes() if callable(planes) else planes
    if hasattr(clip_container, "_clip_planes"):
        planes = getattr(clip_container, "_clip_planes")
        return planes() if callable(planes) else planes
    if isinstance(clip_container, dict):
        return clip_container.values()
    if isinstance(clip_container, (list, tuple, set)):
        return clip_container
    for attr in ("all_planes", "items", "values", "plane_list"):
        if hasattr(clip_container, attr):
            obj = getattr(clip_container, attr)
            try:
                return obj() if callable(obj) else obj
            except TypeError:
                pass
    if hasattr(clip_container, "__len__") and hasattr(clip_container, "__getitem__"):
        try:
            return [clip_container[i] for i in range(len(clip_container))]
        except Exception:
            pass
    try:
        return iter(clip_container)
    except TypeError as e:
        raise UserError(
            f"Could not iterate over clip planes container of type {type(clip_container).__name__}. "
            "If this persists, inspect dir(session.main_view.clip_planes) in ChimeraX and add the relevant accessor."
        ) from e


def _plane_name(plane, index: int) -> str:
    for attr in ("name", "id", "plane_name", "label"):
        if hasattr(plane, attr):
            value = getattr(plane, attr)
            if value:
                return str(value)
    return f"plane_{index}"


def _plane_point_normal(plane) -> Tuple[np.ndarray, np.ndarray]:
    for point_attr, normal_attr in (
        ("plane_point", "normal"),
        ("point", "normal"),
        ("origin", "normal"),
        ("center", "normal"),
        ("position", "normal"),
    ):
        if hasattr(plane, point_attr) and hasattr(plane, normal_attr):
            return _as_array3(getattr(plane, point_attr)), _as_array3(getattr(plane, normal_attr))
    for point_attr, normal_attr in (
        ("get_plane_point", "get_normal"),
        ("plane_point", "get_normal"),
        ("get_point", "get_normal"),
    ):
        if hasattr(plane, point_attr) and hasattr(plane, normal_attr):
            p = getattr(plane, point_attr)
            n = getattr(plane, normal_attr)
            p = p() if callable(p) else p
            n = n() if callable(n) else n
            return _as_array3(p), _as_array3(n)
    if isinstance(plane, (tuple, list)) and len(plane) >= 2:
        try:
            return _as_array3(plane[0]), _as_array3(plane[1])
        except Exception:
            pass
    attrs = [a for a in ("plane_point", "normal", "offset", "name") if hasattr(plane, a)]
    raise UserError(
        f"Could not extract a point/normal from plane object of type {type(plane).__name__}. "
        f"Available attributes include: {', '.join(attrs) if attrs else 'none of plane_point/normal/offset/name'}"
    )


def _plane_metadata(plane) -> dict:
    meta = {}
    for attr in ("near", "far", "offset", "distance", "side", "coordinate_system", "coordinateSystem", "position"):
        if hasattr(plane, attr):
            value = getattr(plane, attr)
            if value is not None:
                meta[attr] = value
    return meta


def _format_xyz(v: Sequence[float], digits: int = 3) -> str:
    return f"{v[0]:.{digits}f},{v[1]:.{digits}f},{v[2]:.{digits}f}"


def _signed_distance(plane, reference_scene: np.ndarray) -> float:
    if hasattr(plane, "offset"):
        try:
            return float(plane.offset(reference_scene))
        except Exception:
            pass
    plane_point, plane_normal = _plane_point_normal(plane)
    n = np.asarray(plane_normal, dtype=float)
    norm = float(np.linalg.norm(n))
    if norm == 0.0:
        raise UserError("Encountered a clip plane with zero-length normal")
    n = n / norm
    return float(np.dot(plane_point - reference_scene, n))


def _format_plane_report(name: str, plane, scene_p: np.ndarray, scene_n: np.ndarray,
                         model_p: np.ndarray, model_n: np.ndarray,
                         reference_model: np.ndarray, model_place,
                         meta: Optional[dict] = None,
                         model_spec: str = "#1") -> str:
    meta = meta or {}
    reference_scene = _transform_point(model_place, reference_model)
    signed = _signed_distance(plane, reference_scene)

    extras = []
    for key in ("near", "far", "offset", "distance", "side"):
        if key in meta:
            extras.append(f"{key}={meta[key]}")
    head = ""

    cmd_bits = []
    if "near" in meta or name.lower().startswith("near"):
        cmd_bits += ["near", f"{signed:.2f}"]
    elif "far" in meta or name.lower().startswith("far"):
        cmd_bits += ["far", f"{-signed:.2f}"]
    else:
        cmd_bits += [f"{name}", f"{signed:.2f}"]


    return cmd_bits


def clip_list_relative(session, coordinateSystem=None, position=(0.0, 0.0, 0.0)):
    model = coordinateSystem
    if model is None:
        models = session.models.list(model_id=(1,))
        if not models:
            raise UserError("No model #1 is open")
        model = models[0]

    view = session.main_view
    clip_container = _clip_container(view)
    planes = list(_iter_planes(clip_container))
    if not planes:
        raise UserError("No clipping planes were found")

    model_place = _model_scene_place(model)
    scene_to_model = _inverse_place(model_place)
    model_spec = _model_spec(model)
    reference_model = np.asarray(position, dtype=float)

    session.logger.info(f"Clipping planes relative to {model_spec} at position {_format_xyz(reference_model, 0)}")
    head = ""
    cmd_bits = ["clip"]
    for i, plane in enumerate(planes, start=1):
        name = _plane_name(plane, i)
        scene_p, scene_n = _plane_point_normal(plane)
        model_p = _transform_point(scene_to_model, scene_p)
        model_n = _transform_normal(scene_to_model, scene_n)
        norm = float(np.linalg.norm(model_n))
        if norm > 0.0:
            model_n = model_n / norm
        meta = _plane_metadata(plane)
        cmd_bit = _format_plane_report(
                name=name,
                plane=plane,
                scene_p=scene_p,
                scene_n=scene_n,
                model_p=model_p,
                model_n=model_n,
                reference_model=reference_model,
                model_place=model_place,
                meta=meta,
                model_spec=model_spec,
        )
        cmd_bits += cmd_bit

    cmd_bits += [
        f"coordinateSystem {model_spec}",
        f"position {_format_xyz(reference_model, 0)}",
    ]
    head += "\n    " + " ".join(cmd_bits)
    session.logger.info(head)



def register_command(logger):
    desc = CmdDesc(
        required=[],
        keyword=[("coordinateSystem", ModelArg), ("position", Float3Arg)],
        synopsis="List current clip planes in the coordinate system of a chosen model and reference position",
    )
    register("cliplistrelative", desc, clip_list_relative, logger=logger)


register_command(session.logger)
