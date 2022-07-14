# loads the notes file if it is not open, otherwise closes it

import sublime
import sublime_plugin
import os
from functools import partial

NOTES_PATH = os.getenv('HOME') + '/.local/notes.md'

class ToggleNotesCommand(sublime_plugin.WindowCommand):
    def run(self):
        current_view = self.window.active_view()
        current_fname = current_view.file_name()
        if current_fname == NOTES_PATH:

            if current_view.is_dirty():
                current_view.run_command('save')

            rowcol = current_view.rowcol(current_view.sel()[0].end())
            self.window.settings().set('notes_cursor', rowcol)
            self.window.run_command('next_view_in_stack')
            current_view.close()
        else:
            row, col = sublime.active_window().settings().get('notes_cursor', (1, 1))
            file_loc = "%s:%s:%s" % (NOTES_PATH, row + 1, col + 1)
            self.window.open_file(file_loc, sublime.ENCODED_POSITION)

