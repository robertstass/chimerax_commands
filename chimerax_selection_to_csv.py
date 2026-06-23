#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

"""
chimerax_selection_to_csv.py

ChimeraX command module that exports the current residue selection to CSV.

This version avoids win_coord() entirely. Instead it:
- chooses a 3D anchor per residue
- converts the anchor into camera coordinates
- uses the scene width at that depth from view.view_width()
- scales into the requested saved image width/height

That matches the saved framebuffer geometry much better than trying to
interpret raw window coordinates.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Tuple

import numpy as np

from chimerax.atomic import selected_residues
from chimerax.core.commands import CmdDesc, IntArg, BoolArg, StringArg, SaveFileNameArg, register
from chimerax.core.errors import UserError


AA1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "SEC": "U", "PYL": "O",
}

NA1 = {
    "A": "A", "G": "G", "C": "C", "U": "U", "T": "T",
    "DA": "A", "DG": "G", "DC": "C", "DT": "T",
}


def _xyz3(v) -> Tuple[float, float, float]:
    if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
        return float(v.x), float(v.y), float(v.z)
    try:
        return float(v[0]), float(v[1]), float(v[2])
    except Exception as e:
        raise UserError(f"Could not interpret coordinate value: {v!r}") from e


def residue_label(r):
    """Return (label, chain_id, resname, resnum, inscode)."""
    resname = (getattr(r, "name", "") or "").upper()

    if resname in AA1:
        code = AA1[resname]
    elif resname in NA1:
        code = NA1[resname]
    else:
        code = resname

    chain = ""
    if getattr(r, "chain", None) is not None:
        chain = getattr(r.chain, "id", "") or getattr(r.chain, "chain_id", "") or ""

    resnum = getattr(r, "number", None)
    if resnum is None:
        resnum = getattr(r, "id", "")

    inscode = getattr(r, "insertion_code", "") or ""
    label = f"{code}{resnum}{inscode}"
    return label, chain, resname, resnum, inscode


def residue_anchor_scene_point(r, anchor_mode="principal"):
    """
    Pick a scene-space anchor point for a residue.

    anchor_mode:
      - principal: use principal_atom if available, else mean atom position
      - mean:      use mean of all atom scene coordinates
      - com:       same as mean here
    """
    atoms = r.atoms
    if len(atoms) == 0:
        raise UserError("A selected residue has no atoms")

    anchor_mode = (anchor_mode or "principal").lower()

    if anchor_mode == "principal":
        pa = getattr(r, "principal_atom", None)
        if pa is not None:
            return np.asarray(_xyz3(pa.scene_coord), dtype=float)

        coords = np.asarray([_xyz3(a.scene_coord) for a in atoms], dtype=float)
        return coords.mean(axis=0)

    if anchor_mode in ("mean", "com"):
        coords = np.asarray([_xyz3(a.scene_coord) for a in atoms], dtype=float)
        return coords.mean(axis=0)

    raise UserError("anchor must be one of: principal, mean, com")


def _scene_to_camera(view, scene_xyz):
    """Convert a scene point to camera coordinates."""
    camera = view.camera
    cam_place = camera.position
    inv = cam_place.inverse()

    p = np.asarray(scene_xyz, dtype=float)

    if hasattr(inv, "transform_points"):
        cam_p = inv.transform_points(p[None, :])[0]
    else:
        cam_p = np.asarray(inv * p, dtype=float)

    return np.asarray(cam_p, dtype=float)


def project_scene_to_saved_image(session, scene_xyz, image_width, image_height):
    """
    Project a scene-space point to pixel coordinates in the saved image.

    Returns (image_x, image_y, depth).
    """
    view = session.main_view
    cam_p = _scene_to_camera(view, scene_xyz)

    # Width of the visible region at the depth of this point.
    # ChimeraX documents view_width(point) as the full width of the view
    # at the distance of the point in scene coordinates.
    if hasattr(view, "view_width"):
        view_width = float(view.view_width(scene_xyz))
    else:
        view_width = float(view.camera.view_width(scene_xyz))

    if view_width == 0.0:
        raise UserError("view_width() returned zero")

    view_height = view_width * (float(image_height) / float(image_width))

    # Camera coordinates: +x right, +y up, -z forward.
    # Normalise against the view rectangle at this depth.
    image_x = (cam_p[0] / view_width + 0.5) * float(image_width)
    image_y = (0.5 - cam_p[1] / view_height) * float(image_height)

    return float(image_x), float(image_y), float(cam_p[2])


def selection_to_csv(session, path, width=900, height=700,
                     anchor="principal", overwrite=True, debug=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise UserError(f"File already exists: {path}")

    residues = list(selected_residues(session))
    if not residues:
        raise UserError("No residues are currently selected")

    rows = []

    for r in residues:
        if len(r.atoms) == 0:
            continue

        label, chain, resname, resnum, inscode = residue_label(r)
        anchor_xyz = residue_anchor_scene_point(r, anchor_mode=anchor)
        image_x, image_y, depth = project_scene_to_saved_image(session, anchor_xyz, width, height)

        model_id = ""
        if getattr(r, "structure", None) is not None:
            if hasattr(r.structure, "id_string"):
                model_id = r.structure.id_string
            else:
                model_id = str(getattr(r.structure, "id", ""))

        in_bounds = (0.0 <= image_x <= width) and (0.0 <= image_y <= height)

        row = {
            "model": model_id,
            "chain": chain,
            "resname": resname,
            "resnum": resnum,
            "inscode": inscode,
            "label": label,
            "anchor_mode": anchor,
            "scene_x": f"{anchor_xyz[0]:.6f}",
            "scene_y": f"{anchor_xyz[1]:.6f}",
            "scene_z": f"{anchor_xyz[2]:.6f}",
            "camera_x": f"{_scene_to_camera(session.main_view, anchor_xyz)[0]:.6f}",
            "camera_y": f"{_scene_to_camera(session.main_view, anchor_xyz)[1]:.6f}",
            "camera_z": f"{_scene_to_camera(session.main_view, anchor_xyz)[2]:.6f}",
            "image_x": f"{image_x:.3f}",
            "image_y": f"{image_y:.3f}",
            "image_width": int(width),
            "image_height": int(height),
            "depth": f"{depth:.6f}",
            "in_bounds": str(in_bounds),
        }
        rows.append(row)

        if debug:
            session.logger.info(
                f"{label:8s} scene={anchor_xyz[0]:8.3f},{anchor_xyz[1]:8.3f},{anchor_xyz[2]:8.3f} "
                f"img={image_x:8.3f},{image_y:8.3f} "
                f"in_bounds={in_bounds}"
            )

    if not rows:
        raise UserError("The selected residues contained no atoms to export")

    fieldnames = [
        "model",
        "chain",
        "resname",
        "resnum",
        "inscode",
        "label",
        "anchor_mode",
        "scene_x",
        "scene_y",
        "scene_z",
        "camera_x",
        "camera_y",
        "camera_z",
        "image_x",
        "image_y",
        "image_width",
        "image_height",
        "depth",
        "in_bounds",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    session.logger.info(f"Wrote {len(rows)} residues to {path}")


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register
    desc = CmdDesc(
        required=[("path", SaveFileNameArg)],
        keyword=[
            ("width", IntArg),
            ("height", IntArg),
            ("anchor", StringArg),
            ("overwrite", BoolArg),
            ("debug", BoolArg)
        ],
        synopsis="Write current selected residues to a CSV file with projected image coordinates",
    )
    register("selectiontocsv", desc, selection_to_csv, logger=logger)



register_command(session.logger)
