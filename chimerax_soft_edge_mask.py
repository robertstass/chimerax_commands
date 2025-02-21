#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

import os
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation


def extend_and_soften_mask(img_in, ini_threshold, extend_ini_mask, width_soft_mask_edge):
    # Initialize the mask output array
    img_in = np.asarray(img_in)
    msk_out = np.zeros_like(img_in, dtype=float)

    # Calculate initial binary mask based on density threshold
    msk_out[img_in >= ini_threshold] = 1.0

    # Extend or shrink the initial binary mask
    if extend_ini_mask != 0.0:

        extend_size = int(np.abs(np.ceil(extend_ini_mask)))
        mask_dilated = binary_dilation(msk_out, iterations=extend_size).astype(
            float) if extend_ini_mask > 0 else binary_dilation(~msk_out.astype(bool), iterations=extend_size)

        distances = distance_transform_edt(1 - msk_out if extend_ini_mask > 0 else msk_out)
        within_extend_distance = distances <= extend_ini_mask
        msk_out[within_extend_distance] = 1.0 if extend_ini_mask > 0 else 0.0

    # Add a soft edge to the mask if width_soft_mask_edge is specified
    if width_soft_mask_edge > 0.0:

        # Calculate distances to nearest "1" in the mask for the soft edge
        distances = distance_transform_edt(1 - msk_out)
        mask_edge = distances <= width_soft_mask_edge

        # Calculate the soft edge using a raised cosine function
        mask_soft = np.zeros_like(msk_out)
        mask_soft[mask_edge] = 0.5 + 0.5 * np.cos(np.pi * distances[mask_edge] / width_soft_mask_edge)

        # Apply the soft edge
        msk_out[mask_edge] = mask_soft[mask_edge]

    return msk_out


def soft_edge_mask(session, mask, level=0.5, extend=0, width=12):
    from chimerax.map_data import ArrayGridData
    from chimerax.map import volume_from_grid_data


    ini_threshold = level
    extend_ini_mask = extend
    width_soft_edge = width

    session.logger.status("Binarize map at a threshold level of %.1f..." % (ini_threshold), log=True)

    if extend_ini_mask != 0.0:
        action = "Extending" if extend_ini_mask > 0 else "Shrinking"
        session.logger.status("%s initial binary mask by %.1fpx..." % (action, extend_ini_mask), log=True)

    if width_soft_edge > 0.0:
        session.logger.status("Adding a soft edge (of %.1fpx) to the mask..." % width_soft_edge, log=True)

    if hasattr(mask, '__iter__'): #if list of volumes
        input_mask_data = mask[0].data
    else:
        input_mask_data = mask.data
    m = input_mask_data.matrix()
    softmask = extend_and_soften_mask(m, ini_threshold, extend_ini_mask, width_soft_edge)
    new_mask = ArrayGridData(softmask, origin=input_mask_data.origin, step=input_mask_data.step, cell_angles=input_mask_data.cell_angles, rotation=input_mask_data.rotation, symmetries=input_mask_data.symmetries)
    v = volume_from_grid_data(new_mask, session)
    return v





def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, ModelArg, FloatArg, IntArg, StringArg, BoolArg
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    from chimerax.map import molmap

    desc = molmap.register_molmap_command

    desc = CmdDesc(
        required=[('mask', MapsArg)],
        keyword=[('extend', FloatArg),
                ('level', FloatArg),
                ('width', FloatArg)],
        required_arguments=['mask'],
        synopsis='Binaraize a map, extend it and apply a raised cosine soft edge.')
    register('soft edge mask', desc, soft_edge_mask, logger=logger)


register_command(session.logger)