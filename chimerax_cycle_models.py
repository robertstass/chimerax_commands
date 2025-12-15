#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

import os
import numpy as np

always_visible_model_ids = []

def cycle_models(session, cycle_by):
    top_level_model_indices = [i for i,model in enumerate(session.models) if len(model.id) == 1]

    always_visible_model_indices = [model_index for model_index in top_level_model_indices if
                             session.models[model_index].id[0] in always_visible_model_ids]
    always_visible_models = [session.models[model_index] for model_index in always_visible_model_indices]

    top_level_model_indices = [x for x in top_level_model_indices if x not in always_visible_model_indices]

    if len(always_visible_models) > 0:
        print("Always visible models (Remove with 'cycle models fix #0'):")
        print(always_visible_model_ids)


    num_models = len(top_level_model_indices)

    visible_models = [session.models[model_index].visible for model_index in top_level_model_indices]
    visible_indices = [i for i, x in enumerate(visible_models) if x]



    if all(visible_models):
        index = 0
    elif not any(visible_models):
        index = 0
    elif cycle_by < 0:
        start_index = visible_indices[0]
        index = (start_index + cycle_by) % num_models
    elif cycle_by >= 0:
        start_index = visible_indices[-1]
        index = (start_index + cycle_by) % num_models
    else:
        index = 0



    session.logger.status(f"Showing model number {index+1}", log=True)

    [session.models[top_level_model_indices[i]]._set_display(False) for i in visible_indices]

    session.models[top_level_model_indices[index]]._set_display(True)
    [model._set_display(True) for model in session.models[top_level_model_indices[index]].child_models()]


    for always_visible_model in always_visible_models:
        always_visible_model._set_display(True)
        [model._set_display(True) for model in always_visible_model.child_models()]


def next_model(session):
    cycle_models(session, 1)

def previous_model(session):
    cycle_models(session, -1)

def cycle_models_fix(session, models):
    objects = models.models
    global always_visible_model_ids
    always_visible_model_ids = [model.id[0] for model in objects if len(model.id) == 1]
    print("Models set to always show:")
    print(always_visible_model_ids)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg

    desc = CmdDesc(
        required=[],
        keyword=[],
        required_arguments=[],
        synopsis='Show next model.')
    register('next model', desc, next_model, logger=logger)


register_command(session.logger)

def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg


    desc = CmdDesc(
        required=[], #map or atoms
        keyword=[],
        required_arguments=[],
        synopsis='Show previous model.')
    register('previous model', desc, previous_model, logger=logger)


register_command(session.logger)



def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, BoolArg, ObjectsArg

    desc = CmdDesc(
        required=[('models', ObjectsArg)], #map or atoms
        keyword=[],
        required_arguments=[],
        synopsis='Fix model/models to always show.')
    register('cycle models fix ', desc, cycle_models_fix, logger=logger)

register_command(session.logger)




def create_button_panel():
    from chimerax.core.commands import run
    from chimerax.buttonpanel import buttons

    button_panel_title = 'Model shortcuts'

    #Remove button panel if it exists already...
    bp = buttons._button_panel_with_title(session, button_panel_title)
    bp.tool_window.destroy()
    bp.tool_window.cleanup()
    session._button_panels = [bpanel for bpanel in buttons._button_panels(session) if bpanel is not bp]


    cmd = 'buttonpanel "%s" rows 2 columns 1' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Previous model" command "previous model"' % button_panel_title
    run(session, cmd)
    cmd = 'buttonpanel "%s" add "Next model" command "next model"' % button_panel_title
    run(session, cmd)


from chimerax.ui.gui import UI
if type(session.ui) == UI:
    # Comment out the below function to remove button panel
    create_button_panel()
else:
    print('ChimeraX in --nogui mode.')

