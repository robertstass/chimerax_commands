#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2024)

import os
import numpy as np


def reload_scripts(session):
    from chimerax.cmd_line.tool import CommandLine
    c = session.tools.find_by_class(CommandLine)[0]
    c._run_startup_commands()
    session.logger.status('Startup commands re-executed.', log=True)

    #Alternative option to hard code the file
    '''
    from chimerax.core.commands import run
    my_functions_cxc_path = '<full_path_to>/chimerax_my_functions.cxc'
    cmd = 'open %s' % my_functions_cxc_path
    print(cmd)
    run(session, cmd)
    '''


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register

    desc = CmdDesc(
        required=[],
        keyword=[],
        required_arguments=[],
        synopsis='Reload chimerax_my_functions.cxc.')
    register('reload scripts', desc, reload_scripts, logger=logger)


register_command(session.logger)