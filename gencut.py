#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Generates artwork ready to be processed for cutting'''

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gegl

import math
import os

PROC_GENCUT = 'plug-in-hayharp-mini-maker-gencut'
PLUG_IN_BINARY = 'mini-maker'

def gencut(procedure, run_mode, image, drawables, config, data):
    '''Calls the plugin'''

    if len(drawables) != 1:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                           GLib.Error(f'Procedure "{PROC_GENCUT}" works with one layer.'))
    else:
        if not isinstance(drawables[0], Gimp.Layer):
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                               GLib.Error(f'Procedure "{PROC_GENCUT}" works with layers only.'))

    base_import_layer = image.get_layers()[0] # Get the layer of what the initial image was, since not initially controlled

    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init(PLUG_IN_BINARY)

        config.set_property('mini_name', base_import_layer.get_name().replace('.png', ''))
        dialog = GimpUi.ProcedureDialog.new(procedure, config, 'Mini Maker')
        dialog.fill(['mini_name', 'mini_size', 'border_width', 'scalar_size', 'fold_dir',
                     'border_buffer', 'border_transparency_threshold', 'flat_merge'])
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
        else:
            dialog.destroy()

    mini_name = config.get_property('mini_name')
    fold_dir = config.get_property('fold_dir')
    left_tolerance = config.get_property('border_buffer')
    border_width = config.get_property('border_width')
    mini_size = config.get_property('mini_size')
    scalar_size = config.get_property('scalar_size')
    flat_merge = config.get_property('flat_merge')
    border_transparency_threshold = config.get_property('border_transparency_threshold') / 100

    # Trim blank borders
    width = image.get_width()
    height = image.get_height()
    if (Gegl.Color.get_hsva(drawables[0].get_pixel(0, 0))[3] == 0 or
        Gegl.Color.get_hsva(drawables[0].get_pixel(width - 1, height - 1))[3] == 0):
        image.autocrop()
        width = image.get_width()
        height = image.get_height()

    # Select back of mini and push to layer
    if fold_dir == 'Vertical': # Check if fold line runs vertically
        image.select_rectangle(Gimp.ChannelOps.REPLACE, math.ceil(width / 2), 0, width, height)
    if fold_dir == 'Horizontal':
        image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, width, math.ceil(height / 2))
    Gimp.edit_cut([drawables[0]])
    Gimp.edit_paste(drawables[0], True)
    cut = image.get_selected_layers()[0]
    cut.set_name('Back')

    back_layer = image.get_layer_by_name('Back')
    image.lower_item(back_layer)

    # Select front of mini, shift around, and rename layer
    image.set_selected_layers([base_import_layer])
    base_import_layer.set_name('Front')
    front_layer = base_import_layer
    if fold_dir == 'Vertical':
        back_layer.set_offsets(0, 0)
    if fold_dir == 'Horizontal':
        # front_layer.set_offsets(0, 1 - math.ceil(height / 2))
        front_layer.set_offsets(0, -math.ceil(height / 2))
        # back_layer.set_offsets(0, math.ceil(height / 2))

    # Crop image to size
    if fold_dir == 'Vertical':
        image.crop(math.ceil(width / 2), height, 0, 0)
        # image.crop(math.ceil(width / 2), height, 0, 0)
    if fold_dir == 'Horizontal':
        image.crop(width, math.ceil(height / 2), 0, 0)
    width = image.get_width()
    height = image.get_height()

    # Vertically or horizontally flip back layer and anchor
    image.set_selected_layers([back_layer])
    if fold_dir == 'Vertical':
        back_layer.transform_flip_simple(Gimp.OrientationType.HORIZONTAL, True, 0)
    if fold_dir == 'Horizontal':
        back_layer.transform_flip_simple(Gimp.OrientationType.VERTICAL, True, 0)
        selection = image.get_floating_sel()
        Gimp.floating_sel_anchor(selection)

    # Search image, find lower black border. Realign layers if not matching, then clear that space
    image.set_selected_layers([back_layer])
    Gimp.Selection.all(image)
    contiguous_border_hits = []
    for y_coord in range(math.ceil(height / 2), height - 7):
        color_search = Gegl.Color.get_hsva(back_layer.get_pixel(left_tolerance, y_coord))
        if color_search[3] >= border_transparency_threshold:
            contiguous_border_hits.append(y_coord)
    # if fold_dir == 'Horizontal': # Attempt to realign layers if not matching due to artwork inconsistencies
    image.set_selected_layers([front_layer])
    try:
        for y_coord in range(contiguous_border_hits[0] - 10, contiguous_border_hits[0] + 10):
            color_search = Gegl.Color.get_hsva(front_layer.get_pixel(left_tolerance, y_coord))
            if color_search[3] >= border_transparency_threshold:
                print(y_coord, contiguous_border_hits[0])
                front_layer.set_offsets(0, contiguous_border_hits[0] - y_coord)
                break
    except IndexError:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                           GLib.Error(f'Could not locate lower border bounds.'))
    image.resize_to_layers()
    width = image.get_width()
    height = image.get_height()
    image.set_selected_layers([back_layer])
    contiguous_border_hits = []
    for y_coord in range(math.ceil(height / 2), height - 7):
        color_search = Gegl.Color.get_hsva(back_layer.get_pixel(left_tolerance, y_coord))
        if color_search[3] >= border_transparency_threshold:
            contiguous_border_hits.append(y_coord) # TODO: I have no idea why it sometimes selects 1 coordinate short
    image.set_selected_layers([front_layer, back_layer])
    border_fade = 0
    for layer in [front_layer, back_layer]:
        layer_border_fade = 0
        fade_search = 1
        while Gegl.Color.get_hsva(layer.get_pixel(left_tolerance, contiguous_border_hits[0] - fade_search))[3] > 0:
            layer_border_fade += 1
            fade_search += 1
        if layer_border_fade > border_fade:
            border_fade = layer_border_fade
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, contiguous_border_hits[0] - border_fade, # TODO +1???
                           width + 1, height + 1)
    back_layer.edit_clear()
    front_layer.edit_clear()

    # Do scaling now, if necessary
    if scalar_size < 100:
        scaled_width = math.ceil(width * scalar_size / 100)
        scaled_height = math.ceil(contiguous_border_hits[0] * scalar_size / 100)
        for layer in  [front_layer, back_layer]:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, left_tolerance, left_tolerance, width - left_tolerance * 2,
                                   contiguous_border_hits[0] - left_tolerance)
            layer.transform_scale((width - scaled_width) / 2, contiguous_border_hits[0] - scaled_height,
                                  width - (width - scaled_width) / 2, contiguous_border_hits[0])
            selection = image.get_floating_sel()
            Gimp.floating_sel_anchor(selection)

    # Delete outer border
    Gimp.context_set_sample_merged(True)
    Gimp.context_set_sample_threshold_int(70)
    image.select_contiguous_color(Gimp.ChannelOps.REPLACE, back_layer, 0, contiguous_border_hits[0] - border_fade - 1)
    back_layer.edit_clear()
    front_layer.edit_clear()

    # Add border layer and stroke border
    image.insert_layer(Gimp.Layer.new(image, 'Border', width, height, Gimp.ImageType.RGBA_IMAGE, 100,
                                      Gimp.LayerMode.NORMAL), None, 2)
    border_layer = image.get_layer_by_name('Border')
    Gimp.context_set_sample_transparent(True)
    image.select_color(Gimp.ChannelOps.REPLACE, back_layer, front_layer.get_pixel(left_tolerance * 2, left_tolerance * 2))
    Gimp.Selection.border(image, border_width)
    Gimp.context_set_foreground(Gegl.Color.new('black'))
    border_layer.edit_fill(Gimp.FillType.FOREGROUND)

    #Locate tab top edge location
    bottom_border_y = contiguous_border_hits[0] - border_fade + border_width - 1
    bottom_border_left_x = None
    for x_coord in range(0, int(math.ceil(width / 2))):
        if Gegl.Color.get_hsva(border_layer.get_pixel(x_coord, bottom_border_y))[3] == 1:
            bottom_border_left_x = x_coord
            break
    bottom_border_right_x = None
    for x_coord in range(1, int(math.ceil(width / 2))):
        if Gegl.Color.get_hsva(border_layer.get_pixel(width - x_coord, bottom_border_y))[3] == 1:
            bottom_border_right_x = width - x_coord
            break
    if not bottom_border_left_x or not bottom_border_right_x: # Calling error probably improper here
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR,
                                           GLib.Error(f'Could not locate lower border bounds.'))
    bottom_border_center = math.floor((bottom_border_left_x + bottom_border_right_x) / 2)
    if bottom_border_center < width / 2:
        bottom_border_center += 1
    
    # Add tab. Auto-scales to image dpi
    TAB_RES = 600
    dpi = math.ceil(image.get_resolution()[1])
    tab_filepath = f'{os.path.dirname(os.path.realpath(__file__))}/img/Tab - {mini_size}mm.png'
    tab_file = Gio.File.new_build_filenamev([tab_filepath, None])
    tab_layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, tab_file)
    image.insert_layer(tab_layer, None, 2)
    tab_layer.scale(tab_layer.get_width() * dpi / TAB_RES, tab_layer.get_height() * dpi / TAB_RES, False)
    tab_layer.set_offsets(bottom_border_center - math.floor(tab_layer.get_width() / 2), bottom_border_y - border_width)

    image.autocrop()
    image.set_selected_layers([front_layer])
    Gimp.Selection.none(image)

    # Builds the flattened pngs for cutting
    if flat_merge:
        back_cut_group = Gimp.GroupLayer.new(image, f'{mini_name} Back Cut')
        image.insert_layer(back_cut_group, None, 0)
        front_cut_group = Gimp.GroupLayer.new(image, f'{mini_name} Front Cut')
        image.insert_layer(front_cut_group, None, 0)
        layer_order_add = [back_cut_group, front_cut_group]
        layer_index = 0
        for art_layer in [back_layer, front_layer]:
            for layer in [tab_layer, border_layer, art_layer]:
                layer_copy = layer.copy()
                image.insert_layer(layer_copy, layer_order_add[layer_index], 0)
            layer_index += 1
        back_cut_group.merge()
        front_cut_group.merge()
        border_layer.set_visible(False)
        tab_layer.set_visible(False)
        back_layer.set_visible(False)
        front_layer.set_visible(False)

    # TODO: Memory leak somewhere, possibly? Find and fix
    # TODO: Upscaling

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)
