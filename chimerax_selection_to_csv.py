# Commands to add extra functionality to ChimeraX.
# Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

"""
chimerax_selection_to_csv.py

ChimeraX command module that exports the current atomic selection to CSV.

The ``attributes`` keyword controls what each CSV row represents:
- atoms
- residues (default; preserves the original behaviour)
- chains
- models

Chain and model rows are derived from the currently selected residues.  Each
selected residue keeps the original anchor calculation, and the row coordinate
is the arithmetic mean of those residue anchors.  Unselected residues in the
same chain or model are not included.

Automatic labels are:
- residues: the original residue label
- chains:   model filename stem plus chain ID
- models:   model filename stem

The optional ``labels`` keyword accepts a comma-separated CSV list.  Each
non-empty item overrides the label for the corresponding output row.  If the
list is shorter than the exported rows, remaining rows keep their automatic
labels.

This version avoids win_coord() entirely. Instead it:
- chooses a 3D anchor per selected entity
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

from chimerax.atomic import selected_atoms, selected_residues
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

ATTRIBUTE_LEVELS = ("atoms", "residues", "chains", "models")


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


def _normalise_attributes(attributes):
    value = (attributes or "residues").lower()
    if value not in ATTRIBUTE_LEVELS:
        raise UserError("attributes must be one of: atoms, residues, chains, models")
    return value


def _model_id(model):
    if model is None:
        return ""
    if hasattr(model, "id_string"):
        return model.id_string
    return str(getattr(model, "id", ""))


def _model_file_stem(model):
    """Return the source filename without its final extension.

    AtomicStructure.filename is preferred.  Models without a source filename
    fall back to their displayed name and then their model ID.
    """
    if model is None:
        return "model"

    filename = getattr(model, "filename", None)
    if filename:
        stem = Path(str(filename)).stem
        if stem:
            return stem

    name = getattr(model, "name", "") or ""
    if name:
        stem = Path(str(name)).stem
        if stem:
            return stem

    model_id = _model_id(model)
    return f"model_{model_id}" if model_id else "model"


def _parse_label_list(labels):
    """Parse the optional comma-separated CSV label list."""
    if labels is None:
        return []

    text = str(labels).strip()
    if not text:
        return []

    try:
        return [value.strip() for value in next(csv.reader([text], skipinitialspace=True))]
    except csv.Error as error:
        raise UserError(f"Could not parse labels CSV list: {error}") from error


def _chain_id(residue):
    """Return a chain identifier without requiring selected_chains()."""
    chain = getattr(residue, "chain", None)
    if chain is not None:
        return getattr(chain, "id", "") or getattr(chain, "chain_id", "") or ""
    return getattr(residue, "chain_id", "") or ""


def _group_selected_residues(residues, attributes):
    """
    Group selected residues into ordered chain or model records.

    Chains are keyed by structure and chain ID.  This merges residues that
    ChimeraX reports through different Chain wrapper objects but that belong to
    the same named chain in the same model.  Identically named chains in
    different models remain separate rows.
    """
    groups = {}

    for residue in residues:
        structure = getattr(residue, "structure", None)

        if attributes == "chains":
            chain_id = _chain_id(residue)
            # Chain objects may be distinct wrappers even when they represent
            # the same chain.  Group by the displayed chain ID within a model.
            key = (id(structure), chain_id)
            if key not in groups:
                groups[key] = {
                    "structure": structure,
                    "chain": chain_id,
                    "residues": [],
                }
        else:
            # Every selected residue belongs to an atomic structure/model.
            # Object identity keeps models with similar names or IDs separate.
            key = id(structure)
            if key not in groups:
                groups[key] = {
                    "structure": structure,
                    "chain": "",
                    "residues": [],
                }

        groups[key]["residues"].append(residue)

    return list(groups.values())


def _selected_entities(session, attributes):
    if attributes == "atoms":
        entities = list(selected_atoms(session))
        if not entities:
            raise UserError("No atoms are currently selected")
        return entities

    residues = list(selected_residues(session))
    if not residues:
        raise UserError("No residues are currently selected")

    if attributes == "residues":
        return residues

    # Chain and model rows are deliberately derived only from selected
    # residues.  No selected_chains() or direct model-selection API is needed.
    return _group_selected_residues(residues, attributes)


def _entity_anchor_scene_point(entity, attributes, anchor_mode="principal"):
    """Return an anchor while leaving residue-mode behaviour unchanged."""
    if attributes == "atoms":
        return np.asarray(_xyz3(entity.scene_coord), dtype=float)

    if attributes == "residues":
        return residue_anchor_scene_point(entity, anchor_mode=anchor_mode)

    # For a chain or model, calculate the original residue anchor for every
    # selected residue and then take the arithmetic mean of those anchors.
    # This gives every selected residue equal weight and ignores unselected
    # residues elsewhere in the same chain/model.
    residue_anchors = []
    for residue in entity["residues"]:
        if len(residue.atoms) == 0:
            continue
        residue_anchors.append(
            residue_anchor_scene_point(residue, anchor_mode=anchor_mode)
        )

    if not residue_anchors:
        singular = "chain" if attributes == "chains" else "model"
        raise UserError(f"A selected {singular} has no residue coordinates")

    return np.asarray(residue_anchors, dtype=float).mean(axis=0)


def _entity_fields(entity, attributes):
    """Return model, chain, residue fields and label for a CSV row."""
    if attributes == "atoms":
        residue = getattr(entity, "residue", None)
        if residue is not None:
            _, chain, resname, resnum, inscode = residue_label(residue)
        else:
            chain, resname, resnum, inscode = "", "", "", ""
        return (
            _model_id(getattr(entity, "structure", None)),
            chain,
            resname,
            resnum,
            inscode,
            getattr(entity, "name", "") or "",
        )

    if attributes == "residues":
        label, chain, resname, resnum, inscode = residue_label(entity)
        return (
            _model_id(getattr(entity, "structure", None)),
            chain,
            resname,
            resnum,
            inscode,
            label,
        )

    structure = entity["structure"]
    model_id = _model_id(structure)
    model_label = _model_file_stem(structure)

    if attributes == "chains":
        chain = entity["chain"]
        label = f"{model_label}_{chain}" if chain else model_label
        return model_id, chain, "", "", "", label

    return model_id, "", "", "", "", model_label


def _entity_has_coordinates(entity, attributes):
    if attributes == "atoms":
        return True
    if attributes == "residues":
        return len(entity.atoms) > 0
    return any(len(residue.atoms) > 0 for residue in entity["residues"])


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
                     anchor="principal", overwrite=True, debug=False,
                     attributes="residues", labels=None):
    path = Path(path)
    if path.exists() and not overwrite:
        raise UserError(f"File already exists: {path}")

    attributes = _normalise_attributes(attributes)
    entities = _selected_entities(session, attributes)
    custom_labels = _parse_label_list(labels)

    rows = []

    for entity in entities:
        if not _entity_has_coordinates(entity, attributes):
            continue

        model_id, chain, resname, resnum, inscode, label = _entity_fields(entity, attributes)

        # Custom labels correspond to output rows, not raw selected entities.
        # Empty entries and labels beyond the supplied list use the automatic
        # naming for that row.
        row_index = len(rows)
        if row_index < len(custom_labels) and custom_labels[row_index]:
            label = custom_labels[row_index]

        anchor_xyz = _entity_anchor_scene_point(entity, attributes, anchor_mode=anchor)
        image_x, image_y, depth = project_scene_to_saved_image(session, anchor_xyz, width, height)
        camera_xyz = _scene_to_camera(session.main_view, anchor_xyz)

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
            "camera_x": f"{camera_xyz[0]:.6f}",
            "camera_y": f"{camera_xyz[1]:.6f}",
            "camera_z": f"{camera_xyz[2]:.6f}",
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
                f"{str(label):8s} scene={anchor_xyz[0]:8.3f},{anchor_xyz[1]:8.3f},{anchor_xyz[2]:8.3f} "
                f"img={image_x:8.3f},{image_y:8.3f} "
                f"in_bounds={in_bounds}"
            )

    if not rows:
        if attributes == "residues":
            raise UserError("The selected residues contained no atoms to export")
        raise UserError(f"The selected {attributes} contained no coordinates to export")

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

    session.logger.info(f"Wrote {len(rows)} {attributes} to {path}")


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register
    desc = CmdDesc(
        required=[("path", SaveFileNameArg)],
        keyword=[
            ("width", IntArg),
            ("height", IntArg),
            ("anchor", StringArg),
            ("overwrite", BoolArg),
            ("debug", BoolArg),
            ("attributes", StringArg),
            ("labels", StringArg),
        ],
        synopsis="Write selected atoms, residues, chains, or models to CSV with projected image coordinates and optional row labels",
    )
    register("selectiontocsv", desc, selection_to_csv, logger=logger)


register_command(session.logger)
