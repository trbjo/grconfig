import sublime
import sublime_plugin

# sometimes the lsp is too slow to update, so we wait until it has had time to syncronize
# with changes in the buffer
class SaveNicelyCommand(sublime_plugin.WindowCommand):
    def run(self):
        lsp_active = self.window.active_view().settings().get("lsp_active")
        current_view = self.window.active_view()
        if lsp_active:
            panelView = self.window.find_output_panel("diagnostics")
            if panelView.size() == 28:
                sublime.active_window().run_command('hide_panel', {'panel': 'output.diagnostics'})
            sublime.set_timeout(lambda: current_view.run_command('lsp_save'), 100)
        else:
            current_view.run_command('save')
