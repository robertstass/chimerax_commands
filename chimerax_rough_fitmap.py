#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2024)

import os
import numpy as np


def is_map_or_atoms(session, atomspec):
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomicStructureArg
    a = AtomicStructureArg()
    atoms = a.parse(atomspec.spec, session)
    if len(atoms[0].atoms) == 0:
        m = MapsArg()
        map = m.parse(atomspec.spec, session)
        return True
        #return map[0][0]
    else:
        return False #atoms[0]

def is_map_or_atoms(session, atomspec):
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    m = MapsArg()
    map = m.parse(str(atomspec), session)
    if map[0] == []:
        return False
    else:
        return True

def parse_map_or_atoms(session, atomspec):
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

def rough_fitmap(session, atoms_or_map, inmap, search=50, radius=50, sym=False, refine=False):
    from chimerax.core.commands import run, AtomSpecArg
    from chimerax.std_commands import wait
    from chimerax.atomic.cmd import combine_cmd
    from chimerax.atomic import AtomicStructuresArg
    from chimerax.core.commands.cli import command_function
    align_center = command_function("align center")

    ismap = is_map_or_atoms(session, atoms_or_map.spec)
    atoms_or_map_id = atoms_or_map.spec
    map_id = '#' + inmap[0].id_string


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


    a = AtomSpecArg()
    A = a.parse(atoms_or_map_id, session)
    parsed_atoms_or_map = parse_map_or_atoms(session, A[0])

    cmd = 'align center %s to %s' % (atoms_or_map_id, map_id)
    print(cmd)
    align_center(session, parsed_atoms_or_map, inmap[0])

    wait.wait(session,1) #update view

    if sym and not ismap:
        # combine to make fitmap work following symmetry command.
        cmd = 'combine %s' % (atoms_or_map_id)
        print(cmd)
        a = AtomicStructuresArg()
        A = a.parse(atoms_or_map_id, session)
        atoms_or_map = combine_cmd(session, A[0])
        cmd = 'hide %s models' % atoms_or_map_id
        print(cmd)
        run(session, cmd)
        atoms_or_map_id = '#'+atoms_or_map.id_string

    cmd = 'fitmap %s inmap %s search %d radius %d' % (atoms_or_map_id, map_id, search, radius)
    print(cmd)
    run(session, cmd)

    wait.wait(session, 30)  # update view

    if refine: #repeat fitmap command without search
        cmd = 'fitmap %s inmap %s' % (atoms_or_map_id, map_id)
        print(cmd)
        run(session, cmd)

    return atoms_or_map_id, map_id



def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, IntArg, ModelArg, StringArg, BoolArg, ObjectsArg
    from chimerax.map import MapsArg
    from chimerax.atomic import AtomsArg
    desc = CmdDesc(
        required=[('atoms_or_map', ObjectsArg)],
        keyword=[('inmap', MapsArg),
                 ('search', IntArg), #default 50
                 ('radius', IntArg), #default 50
                 ('sym', BoolArg), #symmetrize first (by biomt info in file header)
                 ('refine', BoolArg)], #Run a standard, non-search fitmap command after rough fit.
        required_arguments=['atoms_or_map', 'inmap'],
        synopsis='Initial approximate fitmap command.')
    register('rough fitmap', desc, rough_fitmap, logger=logger)


register_command(session.logger)