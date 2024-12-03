#Commands to add extra functionality to ChimeraX.
#Written by Robert Stass, Bowden group, STRUBI/OPIC (2024)

import os

def next_lowest_model_id(session):
    lowest_unused_model_id = max([m.id_string for m in session.models])
    return int(float(lowest_unused_model_id))+1

def map_eraser_mask_create(session, mask, sphere, save_masks=True, file_root=None, sphere_append='_sphere', full_append='_plus_sphere', extend=0.0, width=12):
    center = sphere.scene_position.origin()

    radius = sphere.radius
    mask_id = mask[0].id_string
    sphere_model_id = next_lowest_model_id(session)
    from chimerax.core.commands import run, CenterArg
    from chimerax.map_filter.vopcommand import volume_threshold, volume_add
    from chimerax.map_eraser.eraser import volume_erase
    from chimerax.core.commands.cli import command_function
    soft_edge_mask = command_function("soft edge mask")

    # Make a filled volume
    cmd = 'volume threshold #%s minimum 2 set 1 maximum 2 setMaximum 0' % (mask_id)
    print(cmd)
    filled_v = volume_threshold(session, mask, minimum=2, set=1, maximum=2, set_maximum=0)
    filled_model_id = filled_v.id_string
    cmd = 'volume threshold #%s minimum 2 set 1 maximum 2 setMaximum 0 modelId #%s' % (mask_id, sphere_model_id)
    print(cmd)
    #run(session, cmd)

    # Erase everything but the map eraser sphere
    c = '%.5g,%.5g,%.5g' % tuple(center)
    ca = CenterArg()
    C = ca.parse(c, session)
    cmd = 'volume erase #%s center %s radius %.5g outside true' % (filled_model_id, c, radius)
    print(cmd)
    sphere_v = volume_erase(session, [filled_v], center=C[0], radius=radius, outside=True)
    sphere_model_id = sphere_v.id_string

    # Binarize the mask
    cmd = 'volume threshold #%s minimum 0.5 set 0 maximum 0.5 setMaximum 1' % (mask_id)
    print(cmd)
    binary_v = volume_threshold(session, mask, minimum=0.5, set=0, maximum=0.5, set_maximum=1)
    binary_mask_id = binary_v.id_string

    # Add together sphere and mask
    cmd = 'volume add #%s,%s' % (sphere_model_id, binary_mask_id)
    print(cmd)
    combined_v = volume_add(session, (sphere_v, binary_v))
    combined_model_id = combined_v.id_string

    #Re-binarize
    cmd = 'volume threshold #%s minimum 0 set 0 maximum 1 setMaximum 1' % (combined_model_id)
    print(cmd)
    combined_v = volume_threshold(session, [combined_v], minimum=0.5, set=0, maximum=0.5, set_maximum=1)
    combined_model_id = combined_v.id_string

    # Soften sphere mask
    cmd = 'soft_edge_mask %s level 0.5 extend %.2f width %.2f' % (sphere_model_id, extend, width)
    print(cmd)
    soft_sphere = soft_edge_mask(session, sphere_v, level=0.5, extend=extend, width=width)
    soft_sphere_id = soft_sphere.id_string

    # Soften combined mask
    cmd = 'soft_edge_mask %s level 0.5 extend %.2f width %.2f' % (combined_model_id, extend, width)
    print(cmd)
    soft_combined = soft_edge_mask(session, combined_v, level=0.5, extend=extend, width=width)
    soft_combined_id = soft_combined.id_string



    if save_masks:
        if file_root == None:
            split_path = os.path.splitext(mask[0].path)
        else:
            split_path = [file_root, '.mrc']
        sphere_path = split_path[0]+sphere_append+split_path[1]
        full_path = split_path[0]+full_append+split_path[1]
        cmd = 'save %s format mrc models #%s' % (sphere_path, soft_sphere_id)
        print(cmd)
        run(session, cmd)
        cmd = 'save %s format mrc models #%s' % (full_path, soft_combined_id)
        print(cmd)
        run(session, cmd)
        print('Files output: %s %s' % (sphere_path, full_path))


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, ModelArg, StringArg, BoolArg, FloatArg
    from chimerax.map import MapsArg
    desc = CmdDesc(
        required=[],
        keyword=[('mask', MapsArg),
                 ('sphere', ModelArg),
                 ('save_masks', BoolArg), #Default to True
                 ('file_root', StringArg), #Defaults to the mask file path
                 ('sphere_append', StringArg), #Alternative file endings
                 ('full_append', StringArg), #Alternative file endings
                 ('extend', FloatArg), #Extend initial mask (px)
                 ('width', FloatArg)], #Width soft edge of mask (px)
        required_arguments=['mask', 'sphere'],
        synopsis='Create a mask from the map eraser sphere.'
    )
    register('map eraser mask create', desc, map_eraser_mask_create, logger=logger)


register_command(session.logger)