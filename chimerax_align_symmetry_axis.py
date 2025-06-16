#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

import os
import numpy as np

def define_centroid(session, atoms, mass_weighting=False): # from cmd_centroid
    from chimerax.core.errors import UserError
    from chimerax.centroids import centroid
    from chimerax.atomic import AtomicStructure, concatenate
    if atoms is None:
        structures_atoms = [m.atoms for m in session.models if isinstance(m, AtomicStructure)]
        if structures_atoms:
            atoms = concatenate(structures_atoms)
    if not atoms:
        raise UserError("Atom specifier selects no atoms")
    structures = atoms.unique_structures
    if len(structures) > 1:
        crds = atoms.scene_coords
    else:
        crds = atoms.scene_coords #was atoms.coords ?
    if mass_weighting:
        masses = atoms.elements.masses
        avg_mass = masses.sum() / len(masses)
        import numpy
        weights = masses[:, numpy.newaxis] / avg_mass
    else:
        weights = None
    xyz = centroid(crds, weights=weights)
    return xyz

def is_planar(points, tolerance=1):
    points = np.asarray(points)
    if len(points) < 4:
        return True  # 3 or fewer points are always planar

    p0, p1, p2 = points[:3]
    normal = np.cross(p1 - p0, p2 - p0)
    norm = np.linalg.norm(normal)
    if norm < 1e-12:
        return False  # Degenerate triangle
    normal /= norm

    for pi in points[3:]:
        distance = np.dot(pi - p0, normal)
        if abs(distance) > tolerance:
            return False
    return True

def align_sym_axis(session, atoms, sym, MoveToOrigin=True):
    from chimerax.core.commands import run
    from chimerax.core.errors import UserError
    from chimerax.geometry import rotation


    if sym[0] != "c" and sym[0] != "C":
        raise UserError(f"Cyclic symmetry only accepted. Not {sym}.")

    if len(sym) > 1:
        try:
            cyclic_sym = int(sym[1:])
        except:
            raise UserError(f"Cannot parse symmetry from {sym}. Should be C2 or C3 ect.")
    else:
        raise UserError(f"Cannot parse symmetry from {sym}. Should be C2 or C3 ect.")

    if cyclic_sym < 3:
        raise UserError(f"Symmetries less than C3 currently not supported.")

    num_atoms = len(atoms)
    print(f"Number of atoms: {num_atoms}")


    if num_atoms != cyclic_sym:
        raise UserError(f"Number of atoms ({num_atoms}) must match symmetry order (C{cyclic_sym}).")

    scene_coords = atoms.scene_coords

    if not is_planar(scene_coords):
        raise UserError("For symmetries greater than C3, supplied points must be co-planar.")

    centroid = define_centroid(session, atoms)

    p0, p1, p2 = scene_coords[:3]
    v0 = p1 - p0
    v1 = p2 - p0
    normal = np.cross(v0, v1)
    normal /= np.linalg.norm(normal)
    target = np.array([0, 0, 1]) # xy plane

    axis = np.cross(normal, target)
    angle = np.degrees(np.arccos(np.clip(np.dot(normal, target), -1.0, 1.0)))
    transform = rotation(axis, angle, centroid)
    #new_coords = transform.transform_points(scene_coords)

    cmd = 'view orient'
    run(session, cmd)
    atoms[0].structure.atoms.transform(transform)

    if MoveToOrigin:
        model_id = atoms[0].structure.atomspec
        s2c = session.main_view.camera.position.inverse()
        screen_atoms_center = s2c.transform_points(np.expand_dims(centroid, 0))
        screen_origin_center = s2c.transform_points(np.expand_dims([0.0,0.0,0.0], 0))
        center_dif = [-1 * (m - a) for m, a in zip(screen_atoms_center[0], screen_origin_center[0])]
        cmd = 'move %0.2f,%0.2f,%0.2f model %s' % (center_dif[0], center_dif[1], center_dif[2], model_id)
        print(cmd)
        run(session, cmd)
        cmd = 'view orient'
        run(session, cmd)

    msg_str = f"Symmetry axis of model {model_id} aligned to Z axis"
    if MoveToOrigin:
        msg_str = msg_str+" and centroid also moved to origin."
    else:
        msg_str = msg_str+"."
    print(msg_str)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, StringArg, BoolArg

    from chimerax.atomic import AtomsArg

    desc = CmdDesc(
        required=[('atoms', AtomsArg), #For C3 symmetry, supply exactly 3 atoms. 4 atoms for C4 ect.
                  ('sym', StringArg)],
        keyword=[('MoveToOrigin', BoolArg)], # default True. Moves center of the supplied atoms to the origin.
        required_arguments=[],
        synopsis='Align a symmetric model to the z axis. Cyclic symmetry only. You must supply a specific number of atoms that define the symmetric plane.')
    register('align symmetry axis', desc, align_sym_axis, logger=logger)


register_command(session.logger)