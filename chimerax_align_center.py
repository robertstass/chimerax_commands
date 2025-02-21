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

def parse_map_or_atoms(session , atomspec):
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    m = MapsArg()
    map = m.parse(str(atomspec), session)
    if map[0] == []:
        a = AtomsArg()
        atoms = a.parse(str(atomspec), session)
        return atoms[0]
    else:
        return map[0][0]


def align_center(session, model, to=None, MoveAtomSubset=False):
    from chimerax.core.commands import run
    from chimerax.atomic.molarray import Atoms
    from chimerax.map.volume import Volume
    from chimerax.std_commands.measure_center import volume_center_of_mass
    from chimerax.core.commands import atomspec

    if type(model) == atomspec.AtomSpec:
        model = parse_map_or_atoms(session, model)
    if to is not None:
        if type(to) == atomspec.AtomSpec:
            to = parse_map_or_atoms(session, to)

    if type(model) == Atoms:
        model_id = model.spec
        model_center = define_centroid(session, model)
        move_string = 'atoms'
    elif type(model) == Volume:
        model_id = '#'+model.id_string
        model_center = volume_center_of_mass(model)
        if np.isnan(model_center[0]):
            raise ValueError("Map has no volume. Set threshold level to display density.")
        model_xyz = model.data.ijk_to_xyz(model_center)
        model_center = model.scene_position * model_xyz
        move_string = 'models'
    else:
        raise ValueError("Model type not recognised: %s" % str(type(model)))

    if to is not None:
        if type(to) == Atoms:
            to_id = to.spec
            to_center = define_centroid(session, to)
        elif type(to) == Volume:
            to_id = '#'+to.id_string
            to_center = volume_center_of_mass(to)
            if np.isnan(to_center[0]):
                raise ValueError("Map has no volume. Set threshold level to display density.")
            to_xyz = to.data.ijk_to_xyz(to_center)
            to_center = to.scene_position * to_xyz
        else:
            raise ValueError("'Model to' type not recognised: %s" % str(type(to)))
    else:
        to_center = session.main_view.center_of_rotation

    move_atom_subset = MoveAtomSubset
    if not move_atom_subset:
        move_string = 'model'

    s2c = session.main_view.camera.position.inverse()
    screen_map_center = s2c.transform_points(np.expand_dims(model_center, 0))
    screen_atoms_center = s2c.transform_points(np.expand_dims(to_center, 0))
    center_dif = [-1*(m-a) for m,a in zip(screen_map_center[0],screen_atoms_center[0])]
    cmd = 'move %0.2f,%0.2f,%0.2f %s %s' % (center_dif[0], center_dif[1], center_dif[2], move_string, model_id)
    print(cmd)
    run(session, cmd)




def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, ModelArg, StringArg, BoolArg, AtomSpecArg
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg

    desc = CmdDesc(
        required=[('model', AtomSpecArg)], #map or atoms
        keyword=[('to', AtomSpecArg), #map or atoms
                 ('MoveAtomSubset', BoolArg)],
        required_arguments=[],
        synopsis='Move a map to the center of some atoms (no rotation).')
    register('align center', desc, align_center, logger=logger)


register_command(session.logger)