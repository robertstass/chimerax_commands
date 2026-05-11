#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

import os
import numpy as np

def in_contour(atoms, volume, stats):
    points = atoms.scene_coords
    if len(points) == 0:
        raise ValueError("No atoms in selection.")
    from chimerax.geometry import identity
    from chimerax.map_fit import fitmap as FM
    poc, clevel = FM.points_outside_contour(points, identity(), volume)
    stats['atoms outside contour'] = poc
    stats['total atoms'] = len(points)
    stats['atoms inside contour'] = len(points) - poc
    stats['contour level'] = clevel
    pic = float(len(points) - poc) / len(points)
    stats['percent inside contour'] = pic
    return pic

def atom_inclusion(session, atoms, inmap):
    stats = {}
    inclusion = in_contour(atoms, inmap[0], stats)
    session.logger.status('Atom inclusion:', log=True)
    session.logger.status('%.1f%% of atoms (%d out of %d) are inside contour at level %.3f.' % (stats['percent inside contour']*100, stats['atoms inside contour'], stats['total atoms'], stats['contour level']), log=True)
    return inclusion


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    desc = CmdDesc(
        required=[('atoms', AtomsArg)],
        keyword=[('inmap', MapsArg)],
        required_arguments=['inmap'],
        synopsis='Print the number and percentage of atoms inside the map at current level.')
    register('atom inclusion', desc, atom_inclusion, logger=logger)


register_command(session.logger)
