#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2024)

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


def go_to_residue(session, to, to_ends=False, first=True, NoMove=False):
    from chimerax.core.commands import run
    num_start_res = 0 if first else -1
    sel_string = 'residues'
    rs = session.selection.items(sel_string)
    if len(rs) == 0:
        session.logger.status("First make an atomic selection (ctrl+click/drag or select command)", log=True)
        return False
    sel_string = "atoms"
    selected_atoms_list = session.selection.items(sel_string)
    if len(rs) > 1 or len(selected_atoms_list) > 1:
        multi_model = True
    else:
        multi_model = False
    rs = rs[num_start_res]
    residues_one = rs.filter([num_start_res]) #first residue
    r = residues_one[0]
    atoms = r.atoms
    selection_same = False
    if not len(selected_atoms_list) == 0 and not len(selected_atoms_list) > 1:
        if np.array_equal(selected_atoms_list[0].pointers, atoms.pointers):
            selection_same = True
    ats = session.selection.models()
    from chimerax.atomic.structure import AtomicStructure
    ats = [a for a in ats if type(a) == AtomicStructure]
    a = ats[num_start_res]
    if selection_same and to_ends:
        if first:
            i = 0
        else:
            i = len(a.residues)-1
    else:
        i = a.residues.index(r)
    if selection_same:
        new_i = i+to
    else:
        new_i = i
    if new_i < 0:
        message = ' Start of chain.'
    elif new_i > len(a.residues)-1:
        message = ' End of chain.'
    else:
        message = ""
    new_i = max(0,min(new_i, len(a.residues)-1))
    new_r = a.residues.filter([new_i])

    name = new_r[0].name
    atomspec = new_r[0].atomspec
    model = new_r[0].structure.id_string
    code = new_r[0].one_letter_code
    code = "" if code is None else code
    if atomspec[0] == '#': #doesn't always include model num?
        spec = atomspec
    else:
        model = '#' + model
        spec = model+atomspec
    cmd = 'select %s' % (spec)
    run(session, cmd)
    aa_message = "%s %s %s %s" % (spec, name, code, message)

    if not NoMove:
        #center = new_r[0].center
        center = define_centroid(session, new_r[0].atoms)
        camera = session.main_view.camera
        cofr = session.main_view.center_of_rotation
        s2c = session.main_view.camera.position.inverse()
        residue_center = s2c.transform_points(np.expand_dims(center, 0))
        current_center = s2c.transform_points(np.expand_dims(cofr, 0))
        center_dif = [-1 * (m - a) for m, a in zip(residue_center[0], current_center[0])]
        cmd = 'move %0.2f,%0.2f,%0.2f' % (center_dif[0], center_dif[1], center_dif[2])
        run(session, cmd)
        cmd = 'cofr sel'
        run(session, cmd)

    session.logger.status(aa_message, log=True)



def next_residue(session, NoMove=False):
    go_to_residue(session, 1, NoMove=NoMove)
def previous_residue(session, NoMove=False):
    go_to_residue(session, -1, NoMove=NoMove)

def first_residue(session, NoMove=False):
    go_to_residue(session, 0, to_ends=True, NoMove=NoMove)

def last_residue(session, NoMove=False):
    go_to_residue(session, 0, to_ends=True, first=False, NoMove=NoMove)

def to_residue(session, NoMove=False):
    go_to_residue(session, 0, NoMove=NoMove)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[],
        keyword=[('NoMove', BoolArg)],
        required_arguments=[],
        synopsis='Go to next residue.')
    register('next residue', desc, next_residue, logger=logger)


register_command(session.logger)

def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[], #map or atoms
        keyword=[('NoMove', BoolArg)],
        required_arguments=[],
        synopsis='Go to previous residue.')
    register('previous residue', desc, previous_residue, logger=logger)


register_command(session.logger)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[], #map or atoms
        keyword=[('NoMove', BoolArg)],
        required_arguments=[],
        synopsis='Go to first residue of selection.')
    register('first residue', desc, first_residue, logger=logger)


register_command(session.logger)

def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[], #map or atoms
        keyword=[('NoMove', BoolArg)],
        required_arguments=[],
        synopsis='Go to last residue of selection.')
    register('last residue', desc, last_residue, logger=logger)


register_command(session.logger)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[], #map or atoms
        keyword=[('NoMove', BoolArg)],
        required_arguments=[],
        synopsis='Identify current residue of selection.')
    register('to residue', desc, to_residue, logger=logger)


register_command(session.logger)



def create_button_panel():
    from chimerax.core.commands import run
    from chimerax.buttonpanel import buttons

    button_panel_title = 'Residue shortcuts'

    #Remove button panel if it exists already...
    bp = buttons._button_panel_with_title(session, button_panel_title)
    bp.tool_window.destroy()
    bp.tool_window.cleanup()
    session._button_panels = [bpanel for bpanel in buttons._button_panels(session) if bpanel is not bp]


    cmd = 'buttonpanel "%s" rows 2 columns 3' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "To residue" command "to residue"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Previous residue" command "previous residue"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Next residue" command "next residue"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Reset cofr" command "cofr all"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "First residue" command "first residue"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Last residue" command "last residue"' % button_panel_title
    run(session, cmd)


#Comment out the below function to remove button panel
create_button_panel()