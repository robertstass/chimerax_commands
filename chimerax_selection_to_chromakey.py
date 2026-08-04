#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

import os
import numpy as np
import copy
from pathlib import Path
from chimerax.core.commands import CmdDesc, IntArg, FloatArg, BoolArg, StringArg, ColorArg, SaveFileNameArg, register, run
from chimerax.std_commands import graphics, lighting
from chimerax.core.errors import UserError
from chimerax.core.colors import Color

default_color = "#00FF00"
default_background_color = "#FFFFFF"
default_highlight_color = "black"


def selection_to_chromakey(session, path, width=900, height=700, color=None, background_color=None, transparentBackground=True, highlight=False, highlight_color=None, highlight_thickness=6, overwrite=True):
    ### Color defaults
    if color is None:
        color = Color(default_color)
    if background_color is None:
        background_color = Color(default_background_color)
    if highlight_color is None:
        highlight_color = Color(default_highlight_color)

    r, g, b, a = color.uint8x4()
    color_hex = f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    bgr, bgg, bgb, bga = background_color.uint8x4()
    bg_color_hex = f"#{bgr:02x}{bgg:02x}{bgb:02x}{bga:02x}"
    hr, hg, hb, ha = highlight_color.uint8x4()
    h_color_hex = f"#{hr:02x}{hg:02x}{hb:02x}{ha:02x}"


    path = Path(path)
    if path.exists() and not overwrite:
        raise UserError(f"File already exists: {path}")

    selected_models = session.selection.models()
    if selected_models == None:
        raise UserError(f"Make a selection first.")

    #Get state
    bg = session.main_view.get_background_color()
    l = copy.copy(session.main_view.lighting)
    sil = session.main_view.silhouette.enabled
    hc = Color(session.main_view.highlight_color)
    ht = session.main_view.highlight_thickness


    #Set temporary lighting
    lighting.lighting(session, preset="flat")
    if sil:
        graphics.graphics_silhouettes(session, enable=False)
    session.main_view.set_background_color(background_color.rgba)
    if highlight:
        graphics.graphics_selection(session, color=highlight_color, width=highlight_thickness)
    else:
        graphics.graphics_selection(session, width=0)




    try:

        #color everything white
        bg_color_cmd = f"color all {bg_color_hex}"
        print(bg_color_cmd)
        run(session, bg_color_cmd)

        # a = atoms
        # c = cartoons
        # s = surfaces
        #color selection
        color_cmd = f"color sel {color_hex}" # target acs"
        print(color_cmd)
        run(session, color_cmd)

        #Save image
        trans_str = " transparentBackground true" if transparentBackground else ""
        cmd = f"save {path} format png width {width} height {height}{trans_str}"
        print(cmd)
        run(session, cmd)
        session.logger.info(f"Wrote image to {path}")
    finally:
        # Revert the temporary color command.
        run(session, "undo")
        run(session, "undo")

    # Reset original state
    session.main_view.set_background_color(bg)
    session.main_view.lighting = l
    if sil:
        graphics.graphics_silhouettes(session, enable=True)
    graphics.graphics_selection(session, color=hc, width=ht)




def register_command(logger):
    from chimerax.core.commands import CmdDesc, register
    desc = CmdDesc(
        required=[("path", SaveFileNameArg)],
        keyword=[
            ("width", IntArg), #Image output size
            ("height", IntArg), #Image output size
            ("color", ColorArg), # Fill color
            ("background_color", ColorArg), #Everything else coloured to background color
            ("transparentBackground", BoolArg), #Png transparency
            ("highlight", BoolArg), # Include outline. Default False (as it doesn't look very nice).
            ("highlight_color", ColorArg),
            ("highlight_thickness", FloatArg),
            ("overwrite", BoolArg),
        ],
        synopsis=f"Save the current visible selection surface as a flat single colour image for chromakeying. Default color {default_color} on {default_background_color} background.",
    )
    register("selectiontochromakey", desc, selection_to_chromakey, logger=logger)


register_command(session.logger)
