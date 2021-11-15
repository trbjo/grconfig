#!/usr/bin/env python


import sys
sys.path.append('/home/tb/code/i3ipc-python')

from i3ipc import Connection
import datetime
import subprocess
from typing import Tuple
import re

class Quicknote:
      def __init__(self, content, app=None):
            self.app_id = app[0] if app[0] is not None else ''
            self.content = content if content is not None else ''
            self.timestamp = datetime.datetime.today().replace(microsecond=0)
            title = app[1]
            if '~' in title:
                  numbers = re.compile(r'(~.+?)(?=\s)')
                  title = numbers.sub(r'`\1`', title)
            self.title = title if title is not None else ''

      def __str__(self):
            return f"""
# {self.app_id.replace('_', ' ').title()} – {self.title}
## {self.timestamp}
{self.content}
"""

def get_active_window() -> Tuple[str, str]:
      i3 = Connection()
      focused = i3.get_tree().find_focused()
      return (focused.app_id, focused.name)

def get_clipboard_data() -> str:
    p = subprocess.Popen(['wl-paste','--primary', '-n'], stdout=subprocess.PIPE)
    retcode = p.wait()
    data = p.stdout.read()
    return data.decode()


def main():
      clipboard_content = Quicknote(get_clipboard_data(), get_active_window())
      try:
            notes_file = open('/home/tb/quicknotes.md', 'a')
      except:
            notes_file = open('/home/tb/quicknotes.md', 'x')
      finally:
            notes_file.write(str(clipboard_content))
            notes_file.close()


if __name__ == "__main__":
      main()
