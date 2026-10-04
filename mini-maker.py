#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Project for automatically modifying PrintableHeroes and PaperForge PNGs for VoMT cutouts'''

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import GObject

import gencut
import gensheet

import sys

proc_gensheet = 'plug-in-hayharp-mini-maker-gensheet'
PLUG_IN_BINARY = 'mini-maker'

class MiniMaker(Gimp.PlugIn):
    '''Main class'''

    def do_query_procedures(self):
        return [gencut.PROC_GENCUT, gensheet.PROC_GENSHEET]

    def do_create_procedure(self, name):
        '''Where all the procedures live'''

        procedure = None

        if name == gencut.PROC_GENCUT:
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, gencut.gencut, None)
            procedure.set_attribution('Nathan Hay', 'HayHarp', '2026')
            procedure.set_documentation('''Automatically modifies PrintableHeroes and PaperForge minis
                                        for Vault of Many Things cutout tabs''', None)

            procedure.set_menu_label('Mini Ma_ker')
            procedure.add_menu_path('<Image>/Image') # Tricky! <Image>, I believe, must always be root
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE) # Only allow procedure when single image is opened

            procedure.add_string_argument('mini_name', 'Name', '', 'Mini', GObject.ParamFlags.READWRITE)
            mini_fold_choices = Gimp.Choice.new()
            mini_fold_choices.add('Horizontal', 0, 'Horizontal', 'Select if center fold line runs horizontally')
            mini_fold_choices.add('Vertical', 1, 'Vertical', 'Select if center fold line runs vertically')
            procedure.add_choice_argument('fold_dir', '_Fold Line Direction', 'Which direction the center fold line run',
                                          mini_fold_choices, 'Horizontal', GObject.ParamFlags.READWRITE)
            mini_size_choices = Gimp.Choice.new()
            mini_size_choices.add('25', 25, '25 mm', '')
            mini_size_choices.add('50', 50, '50 mm', '')
            mini_size_choices.add('75', 75, '75 mm', '')
            procedure.add_choice_argument('mini_size', 'Mini _Size', "The size of the mini's VoMT base", mini_size_choices,
                                          '25', GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('scalar_size', 'Scale Artwork?', "The size (in percentage) to scale the mini to",
                                       1, 100, 100, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('border_width', 'Border _Width', '', 1, 20, 8, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument('advanced_options', '_Advanced', '', False, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('border_buffer', 'Left Border _Buffer',
                                       'The distance from the left wall of the image to search for the horizontal black fold lines',
                                       4, 12, 4, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('border_transparency_threshold', 'Border _Threshold',
                                       'Minimum opacity required to detect a border; change only if detection fails',
                                       80, 100, 90, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument('flat_merge', '_Flatten to Layers?',
                                           'Whether or not to copy the expected layers and flatten into a new layer. Set false if modifications expected',
                                           True, GObject.ParamFlags.READWRITE)

        if name == gensheet.PROC_GENSHEET:
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, gensheet.gensheet, None)
            procedure.set_attribution('Nathan Hay', 'HayHarp', '2026')
            procedure.set_documentation('''Automatically modifies PrintableHeroes and PaperForge minis
                                        for Vault of Many Things cutout tabs''', None)

            procedure.set_menu_label('Mini S_heet Maker')
            procedure.add_menu_path('<Image>/Image')
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE) # Only allow procedure when single image is opened

            for letter in range(1, 27):
                letter = chr(letter + 96)
                procedure.add_int_argument(f'image_{letter}_quantity', f'Image {letter.upper()} Quantity', 'How many of said image to include',
                                           1, 50, 1, GObject.ParamFlags.READWRITE)

            procedure.add_int_argument('dpi', '_DPI', 'Art resolution in DPI', 100, 8000, 300, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('buffer', '_Art Buffer', 'Space in px between art', 0, 30, 4, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('alignment_guide_buffer', 'Ali_gnment Buffer', 'Distance from page edge to alignment marks',
                                         0, 100, 12.5, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('page_width', 'Page _Width', 'Width of page in mm', 100, 3000, 215.9, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument('page_height', 'Page _Height', 'Height of page in mm', 100, 3000, 279.4, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument('flat_merge', '_Flatten to Layers?',
                                           'Whether or not to copy the expected layers and flatten into a new layer. Set false if modifications expected',
                                           True, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument('blackout', '_Fill Art Whitespace', '', True, GObject.ParamFlags.READWRITE)
            procedure.add_string_argument('naming_front', 'Front Art Naming Convention', '', ' Front Cut.png', GObject.ParamFlags.READWRITE)
            procedure.add_string_argument('naming_back', 'Back Art Naming Convention', '', ' Back Cut.png', GObject.ParamFlags.READWRITE)
            procedure.add_file_argument('filepath', 'Filepath', '', Gimp.FileChooserAction.SELECT_FOLDER, False, None,
                                        GObject.ParamFlags.READWRITE)

        return procedure

Gimp.main(MiniMaker.__gtype__, sys.argv)
