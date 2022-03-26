import sublime_plugin
from sublime import active_window

class SetDanishDictCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        buf: View | None = active_window().active_view()
        if buf is None:
            return False
        return True

    def run(self) -> None:
        buf: View | None = active_window().active_view()
        if buf is None:
            return
        buf.settings().set(key="dictionary", value="Dictionaries/da_DK.dic")

class SetEnglishDictCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        buf: View | None = active_window().active_view()
        if buf is None:
            return False
        return True

    def run(self) -> None:
        buf: View | None = active_window().active_view()
        if buf is None:
            return
        buf.settings().set(key="dictionary", value="Packages/Language - English/en_US.dic")

