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
        crds = atoms.coords
    if mass_weighting:
        masses = atoms.elements.masses
        avg_mass = masses.sum() / len(masses)
        import numpy
        weights = masses[:, numpy.newaxis] / avg_mass
    else:
        weights = None
    xyz = centroid(crds, weights=weights)
    return xyz

def molmap_cube(session, atoms, resolution, size, spacing):
    from chimerax.core.commands import run
    from chimerax.map import molmap
    from chimerax.map_filter.vopcommand import volume_new





    box = volume_new(session, name='box', size=(size, size, size), grid_spacing=(spacing, spacing, spacing))
    box_id = box.id_string



    cmd = 'volume #%s level 0' % (box_id)
    print(cmd)
    run(session, cmd)

    cmd = 'trans #%s 70' % (box_id)
    print(cmd)
    run(session, cmd)


    atoms_id = atoms.spec
    atoms_center = define_centroid(session, atoms)

    half_map = (size/2.0)*spacing
    map_center = (half_map, half_map, half_map)


    s2c = session.main_view.camera.position.inverse()
    screen_map_center = s2c.transform_points(np.expand_dims(map_center, 0))
    screen_atoms_center = s2c.transform_points(np.expand_dims(atoms_center, 0))
    center_dif = [-1*(m-a) for m,a in zip(screen_map_center[0],screen_atoms_center[0])]
    cmd = 'move %0.2f,%0.2f,%0.2f models #%s' % (center_dif[0], center_dif[1], center_dif[2], box_id)
    print(cmd)
    run(session, cmd)

    session.logger.status('Running molmap with onGrid option...', log=True)
    molmap.molmap(session, atoms, resolution, on_grid=box)
    session.logger.status('Done.', log=True)
    session.logger.status('Box displayed is %d pixels with a spacing of %.2f angstrom/pixel' % (size, spacing), log=True)



def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, ModelArg, FloatArg, IntArg, StringArg, BoolArg
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    from chimerax.map import molmap

    desc = molmap.register_molmap_command

    desc = CmdDesc(
        required=[('atoms', AtomsArg),
                  ('resolution', FloatArg), #Angstrom
                  ('size', IntArg), #Size of box in pixels
                  ('spacing', FloatArg)], #Angstrom per pixel
        keyword=[],
        required_arguments=['atoms', 'resolution', 'size', 'spacing'],
        synopsis='Molmap with a cubic outer shape of a given size and spacing.')
    register('molmap cube', desc, molmap_cube, logger=logger)


register_command(session.logger)