import sublime
from sublime_plugin import ViewEventListener

class SetStatus(ViewEventListener):
    def helper_path(self):
        if self.view.file_name():
            return sublime.active_window().extract_variables()['file_name']
        elif self.view.name():
            return self.view.name()
        else:
            return "New File"


    def on_load_async(self):
        self.view.set_status('currentPath', self.helper_path())

    def on_activated_async(self):
        if self.view.is_dirty():
            self.view.set_status('currentPath', ' ' + self.helper_path())
        else:
            self.view.set_status('currentPath', self.helper_path())

    def on_modified_async(self):
        if self.view.is_dirty():
            self.view.set_status('currentPath', ' ' + self.helper_path())
        else:
             self.view.set_status('currentPath', self.helper_path())

    def on_pre_save_async(self):
        sublime.set_timeout(lambda: sublime.status_message('\0'), 2)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 4)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 6)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 8)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 10)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 50)

    def on_post_save_async(self):
        self.view.set_status('currentPath', self.helper_path())
        sublime.set_timeout(lambda: sublime.status_message('\0'), 2)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 4)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 6)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 8)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 10)
        sublime.set_timeout(lambda: sublime.status_message('\0'), 50)
