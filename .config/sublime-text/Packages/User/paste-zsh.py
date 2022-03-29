import sublime_plugin
import subprocess
import time

class PasteZshCommand(sublime_plugin.WindowCommand):
    def run(self):
        subprocess.Popen(['/usr/bin/pkill', 'zsh', '--signal=USR2']).wait()
        # time.sleep(0.07)
        subprocess.Popen(['swaymsg', '[app_id="^PopUp$"]', 'scratchpad', 'show,', 'fullscreen', 'disable,', 'move', 'position', 'center,', 'resize', 'set', 'width', '100ppt', 'height', '100ppt,', 'resize', 'shrink', 'up', '1100px,', 'resize', 'grow', 'up', '150px']).wait()

