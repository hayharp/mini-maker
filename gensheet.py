#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Generates sheets. Uses Volodymyr Agafonkin's simple rectangle packing algo'''

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gegl

PROC_GENSHEET = 'plug-in-hayharp-mini-maker-gensheet'
PLUG_IN_BINARY = 'mini-maker'

def gensheet(procedure, run_mode, image, drawables, config, data):
    '''Calls the plugin'''

    if len(drawables) < 1:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                           GLib.Error(f'Procedure "{PROC_GENSHEET}" requires at least one image.'))
    else:
        if not isinstance(drawables[0], Gimp.Layer):
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                               GLib.Error(f'Procedure "{PROC_GENSHEET}" works with layers only.'))

    # Variables to turn into arguments

    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init(PLUG_IN_BINARY)

        dialog = GimpUi.ProcedureDialog.new(procedure, config, 'Mini Sheet Maker')
        dialog.fill(['filepath', 'dpi', 'buffer', 'alignment_guide_buffer', 'page_width', 'page_height',
                     'flat_merge', 'blackout', 'naming_front', 'naming_back'])
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
        else:
            dialog.destroy()
    
    NAMING_CONVENTION_FRONT = config.get_property('naming_front')
    NAMING_CONVENTION_BACK = config.get_property('naming_back')
    FILEPATH = config.get_property('filepath').get_path()
    DPI = config.get_property('dpi')
    ART_BUFFER = config.get_property('buffer')
    CUT_TARGET_BUFFER = config.get_property('alignment_guide_buffer')
    PAGE_WIDTH = Gimp.units_to_pixels(config.get_property('page_width') - CUT_TARGET_BUFFER * 2, Gimp.Unit.mm(), DPI)
    PAGE_HEIGHT = Gimp.units_to_pixels(config.get_property('page_height') - (CUT_TARGET_BUFFER + 5) * 2, Gimp.Unit.mm(), DPI)
    FLAT_MERGE = config.get_property('flat_merge')
    BLACKOUT = config.get_property('blackout')

    # Sort layers by height
    image.resize_to_layers()
    art_info = {}
    art_layers = image.get_layers()
    art_count = 1
    layer_sort = []
    for layer in art_layers:
        added = False
        for item in layer_sort:
            if item.get_height() < layer.get_height():
                layer_sort.insert(layer_sort.index(item), layer)
                added = True
                break
        if not added:
            layer_sort.append(layer)
    order_index = 0
    for layer in layer_sort:
        print(layer.get_name())
        image.reorder_item(layer, None, order_index)
        order_index += 1
    art_layers = image.get_layers()

    # Get original art names, load back art files, then rename for convenience
    for layer in art_layers:
        new_name = f'image_{chr(art_count + 96)}'
        art_info[new_name] = {
            'art_name': layer.get_name().replace(NAMING_CONVENTION_FRONT, ''),
            'width': layer.get_width(),
            'height': layer.get_height(),
        }
        art_info[new_name]['area'] = art_info[new_name]['width'] * art_info[new_name]['height']
        layer.set_name(f'{new_name}')
        back_cut_name = f'{art_info[new_name]['art_name']}{NAMING_CONVENTION_BACK}'
        art_info[new_name]['back_file'] = Gio.File.new_for_path(f'{FILEPATH}/{back_cut_name}')
        art_count += 1
    art_layers = image.get_layers()
        
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init(PLUG_IN_BINARY)

        dialog = GimpUi.ProcedureDialog.new(procedure, config, 'Mini Sheet Maker')
        art_properties = []
        for art in range(0, len(art_info.keys())):
            prop_name = f'image_{chr(art + 97)}'
            art_properties.append(f'{prop_name}_quantity')
        dialog.fill(art_properties)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
        else:
            dialog.destroy()

    # Check for basic possibility that everything can fit
    space_sum = 0
    for layer in art_layers:
        space_sum += art_info[layer.get_name()]['area'] * config.get_property(f'{layer.get_name()}_quantity')
    if space_sum > PAGE_WIDTH * PAGE_HEIGHT:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                           GLib.Error(f'Not enough space.'))

    # Make layer copies
    rectangle_sizes = []
    depth = 1
    for layer in art_layers:
        layer_name = layer.get_name()
        layer_copies = config.get_property(f'{layer_name}_quantity')
        rectangle_sizes.append({'w': art_info[layer_name]['width'], 'h': art_info[layer_name]['height'],
                                'x': 0, 'y': 0})
        for x in range(layer_copies - 1):
            rectangle_sizes.append({'w': art_info[layer_name]['width'], 'h': art_info[layer_name]['height'],
                                    'x': 0, 'y': 0})
            new_copy = layer.copy()
            new_copy.set_name(f'{layer_name} {x+1} front')
            image.insert_layer(new_copy, None, depth)
            depth += 1
        layer.set_name(f'{layer_name} 0 front')
        depth += 1

    # Agafonin's rectangle packing algorithm
    def get_space_area(space):
        return space['w'] * space['h']
    pack_spaces = [{'x': 0, 'y': 0, 'w': PAGE_WIDTH, 'h': PAGE_HEIGHT}]
    packed_rectangles = []
    pr_index = 0
    for rectangle in rectangle_sizes:
        fit = False
        ps_index = 0
        pack_spaces = sorted(pack_spaces, key=get_space_area)
        for space in pack_spaces:
            if rectangle['w'] <= space['w'] and rectangle['h'] <= space['h']: # Can space fix rect?
                packed_rectangles.append([space['x'], space['y'], False])
                fit = ['w', 'h']
            elif rectangle['h'] <= space['w'] and rectangle['w'] <= space['h']: # Would it fit if rotated?
                packed_rectangles.append([space['x'], space['y'], True])
                fit = ['h', 'w']
            if fit:
                # print(f'>>>Box #{pr_index}')
                if rectangle[fit[0]] == space['w'] and rectangle[fit[1]] == space['h']: # Does it precisely fill the space?
                    if ps_index < len(pack_spaces): # TODO: Not sure if this chunk is necessary
                        pack_spaces[ps_index] = pack_spaces[len(pack_spaces)]
                    pack_spaces.pop()
                elif rectangle[fit[1]] == space['h']: # For height match
                    space['x'] += rectangle[fit[0]] + ART_BUFFER
                    space['w'] -= (rectangle[fit[0]] + ART_BUFFER)
                elif rectangle[fit[0]] == space['w']: # For width match
                    space['y'] += rectangle[fit[1]] + ART_BUFFER
                    space['h'] -= (rectangle[fit[1]] + ART_BUFFER)
                else: # Split the space into two
                    pack_spaces.append({
                        'x': space['x'] + rectangle[fit[0]] + ART_BUFFER,
                        'y': space['y'],
                        'w': space['w'] - rectangle[fit[0]] - ART_BUFFER,
                        'h': rectangle[fit[1]]
                    })
                    space['y'] += rectangle[fit[1]] + ART_BUFFER
                    space['h'] -= (rectangle[fit[1]] + ART_BUFFER)
                break
            ps_index += 1
        rect_layer = image.get_layers()[pr_index]
        if packed_rectangles[pr_index][2]: # Check if rotation should be done
            rect_layer.transform_rotate_simple(Gimp.RotationType.DEGREES90, True, 0, 0)
        rect_layer.set_offsets(packed_rectangles[pr_index][0], packed_rectangles[pr_index][1])
        pr_index += 1

    # Add back layers
    front_layers = image.get_layers()
    front_layer_group = Gimp.GroupLayer.new(image, 'fronts')
    image.insert_layer(front_layer_group, None, 0)
    back_layer_group = Gimp.GroupLayer.new(image, 'backs')
    image.insert_layer(back_layer_group, None, 1)
    fl_index = 0
    for layer in front_layers:
        layer_name = layer.get_name()
        base_name = layer_name[:7]
        back_layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, art_info[base_name]['back_file']) # TODO: Inefficient, as it could copy duplicate layers
        back_layer.set_name(f'{layer_name[:-6]} back')
        image.insert_layer(back_layer, back_layer_group, fl_index)
        if packed_rectangles[fl_index][2]:
            back_layer.transform_rotate_simple(Gimp.RotationType.DEGREES90, True, 0, 0)
        back_layer.set_offsets(packed_rectangles[fl_index][0], packed_rectangles[fl_index][1])
        image.reorder_item(layer, front_layer_group, fl_index)
        fl_index += 1

    # Flatten layers
    if FLAT_MERGE:
        front_layer_group = front_layer_group.merge()
        back_layer_group = back_layer_group.merge()

    if BLACKOUT:
        # Generate background layer
        background_layer = Gimp.Layer.new(image, 'background', front_layer_group.get_width(), front_layer_group.get_height(),
                                          Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
        image.insert_layer(background_layer, None, len(image.get_layers()))
        image.resize_to_layers()
        image.set_selected_layers([front_layer_group])
        Gimp.context_set_sample_merged(True)
        Gimp.context_set_sample_transparent(True)
        Gimp.Selection.all(image)
        image.select_contiguous_color(Gimp.ChannelOps.SUBTRACT, front_layer_group, 1, 1)
        image.select_contiguous_color(Gimp.ChannelOps.SUBTRACT, front_layer_group, background_layer.get_width() - 1, 1)
        image.select_contiguous_color(Gimp.ChannelOps.SUBTRACT, front_layer_group, 1, background_layer.get_height() - 1)
        image.select_contiguous_color(Gimp.ChannelOps.SUBTRACT, front_layer_group, background_layer.get_width() - 1,
                                      background_layer.get_height() - 1)
        Gimp.context_set_background(Gegl.Color.new('black'))
        background_layer.edit_fill(Gimp.FillType.BACKGROUND)

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)