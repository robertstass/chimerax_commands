#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2024)

import os
import numpy as np

def is_map_or_atoms(session, atomspec):
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    m = MapsArg()
    map = m.parse(str(atomspec), session)
    if map[0] == []:
        return False
    else:
        return True

def fit_opposite_hand(session, atoms_or_map, inmap, search=50, radius=50, sym=False, refine=True, SkipRoughFit=False):
    from chimerax.core.commands import run, ObjectsArg
    from chimerax.map_filter.vopcommand import volume_flip
    from chimerax.atomic import AtomicStructuresArg
    from chimerax.atomic.cmd import combine_cmd
    from chimerax.core.commands.cli import command_function
    rough_fitmap = command_function("rough fitmap")

    map_id = '#'+inmap[0].id_string
    atoms_or_map_id = atoms_or_map.spec
    ismap = is_map_or_atoms(session, atoms_or_map.spec)

    if inmap[0]._surfaces[0]._colors[0][3] == 255: #if not transparent already
        transparency = 70
        cmd = 'trans %s %d' % (map_id, transparency)
        print(cmd)
        run(session, cmd)


    if sym and not ismap:
        orig_models = session.models._models.copy()
        cmd = 'sym %s biomt' % atoms_or_map_id
        print(cmd)
        run(session, cmd)
        dif = session.models._models.keys()-orig_models #find new id
        new_ids = [key for key in dif if len(key) == 1]
        if len(new_ids) > 0:
            atoms_or_map_id = '#'+str(new_ids[0][0])


    #flip map
    cmd = 'volume flip %s' % (map_id)
    print(cmd)
    flipped_volume = volume_flip(session, inmap)
    flipped_volume_id = '#'+flipped_volume.id_string

    #copy model
    cmd = 'combine %s' % (atoms_or_map_id)
    print(cmd)
    a = AtomicStructuresArg()
    A = a.parse(atoms_or_map_id, session)
    atoms_or_map = combine_cmd(session, A[0])

    #hide old map
    cmd = 'hide %s models' % atoms_or_map_id
    print(cmd)
    run(session, cmd)
    old_atoms_or_map_id = atoms_or_map_id
    atoms_or_map_id = '#' + atoms_or_map.id_string

    #turn model 180 degrees
    map_size = np.array(inmap[0].data.size)
    map_step = inmap[0].data.step
    map_center = (map_size/2.0)*map_step
    c = '%.5g,%.5g,%.5g' % tuple(map_center)
    cmd = 'turn x 180 coordinateSystem %s center %s models %s' % (flipped_volume_id, c, atoms_or_map_id)
    print(cmd)
    run(session,cmd)

    if not SkipRoughFit:
        #fit in map
        cmd = 'rough fitmap %s inmap %s search %d radius %d refine %s' % (atoms_or_map_id, flipped_volume_id, search, radius, "False")
        print(cmd)
        run(session, cmd)

    if refine: #repeat fitmap command without search
        cmd = 'fitmap %s inmap %s' % (atoms_or_map_id, flipped_volume_id)
        print(cmd)
        run(session, cmd)

    if SkipRoughFit == True and refine == False:
        session.logger.status('No fitting done. Set refine True or SkipRoughFit False.', log=True)


    cmd1 = 'hide %s models; hide %s models; show %s models; show %s models' % (atoms_or_map_id, flipped_volume_id, old_atoms_or_map_id, map_id)
    #run(session, cmd1)

    cmd2 = 'hide %s models; hide %s models; show %s models; show %s models' % (old_atoms_or_map_id, map_id, atoms_or_map_id, flipped_volume_id)
    #run(session, cmd2)

    session.logger.status('To view original hand fit, run command:', log=True)
    session.logger.status(cmd1, log=True)
    session.logger.status('To view opposite hand fit, run command:', log=True)
    session.logger.status(cmd2, log=True)

    return atoms_or_map_id, flipped_volume_id


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, IntArg, ModelArg, StringArg, BoolArg, ObjectsArg
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    desc = CmdDesc(
        required=[('atoms_or_map', ObjectsArg)],
        keyword=[('inmap', MapsArg),
                 ('search', IntArg), #default 50
                 ('radius', IntArg), #default 50
                 ('sym', BoolArg), #default False uses biomt in file header
                 ('refine', BoolArg), #default True
                 ('SkipRoughFit', BoolArg)], #default False
        required_arguments=['atoms_or_map', 'inmap'],
        synopsis='Fitmap in a opposite hand map.')
    register('fit opposite hand', desc, fit_opposite_hand, logger=logger)


register_command(session.logger)