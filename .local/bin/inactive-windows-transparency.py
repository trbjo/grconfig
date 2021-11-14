#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys
sys.path.append('/home/tb/code/i3ipc-python')

import argparse
import i3ipc
import signal
from functools import partial
import os

def stop_firefox(sig: signal.Signals):
    for dirname in os.listdir('/proc'):
        if dirname == 'curproc':
            continue

        try:
            with open('/proc/{}/cmdline'.format(dirname), mode='rb') as fd:
                content = fd.read().decode().split('\x00')
        except Exception:
            continue

        if "firefox" in content[0]:
            os.kill(int(dirname), sig)



def on_window_move(inactive_opacity, ipc, event):
    focused_workspace = ipc.get_tree().find_focused()
    if focused_workspace == None:
        return

    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            if w.visible:
                if not w.focused:
                    w.command("opacity " + inactive_opacity)
                else:
                    w.command("opacity 1")
            else:
                if not w.focused:
                    w.command("opacity 1")

    return


def on_window_focus(inactive_opacity, ipc, event):
    focused_workspace = ipc.get_tree().find_focused()

    if focused_workspace == None:
        return

    global prev_focused
    global prev_workspace

    focused = event.container
    workspace = focused_workspace.workspace().num

    if focused.id != prev_focused.id:  # https://github.com/swaywm/sway/issues/2859
        global firefox_con_id

        if firefox_con_id != -1:
            if focused.app_id == 'firefox':
                stop_firefox(signal.SIGCONT)
            elif ipc.get_tree().find_by_id(firefox_con_id).visible:
                stop_firefox(signal.SIGCONT)
            else:
                stop_firefox(signal.SIGSTOP)

        focused.command("opacity 1")
        if workspace == prev_workspace:
            old = ipc.get_tree().find_by_id(prev_focused.id)
            if old is not None:
                if old.visible and prev_focused.type != 'floating_con':
                    prev_focused.command("opacity " + inactive_opacity)
        else:
            if prev_focused.type != 'floating_con':
                prev_focused.command("opacity " + inactive_opacity)

        prev_focused = focused
        prev_workspace = workspace

    if len(focused_workspace.workspace().descendants()) == 1:
        focused.command("fullscreen enable")


def exit_handler(ipc):
    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            if w.app_id == 'firefox':
                stop_firefox(signal.SIGCONT)
            w.command("opacity 1")

    ipc.main_quit()
    sys.exit(0)


def check_firefox_exists(ipc, event = None) -> None:
    global firefox_con_id
    for window in ipc.get_tree():
        if window.app_id == 'firefox':
            firefox_con_id = window.id
            return

    firefox_con_id = -1
    return


if __name__ == "__main__":
    transparency_val = "0.80"

    parser = argparse.ArgumentParser(
        description="This script allows you to set the transparency of unfocused windows in sway."
    )
    parser.add_argument(
        "--opacity",
        "-o",
        type=str,
        default=transparency_val,
        help="set opacity value in range 0...1",
    )
    args = parser.parse_args()

    ipc = i3ipc.Connection()
    prev_focused = None
    prev_workspace = ipc.get_tree().find_focused().workspace().num
    check_firefox_exists(ipc)

    firefox_visible_or_focused = False
    for window in ipc.get_tree():
        if window.focused:
            prev_focused = window
            if window.app_id == 'firefox':
                firefox_visible_or_focused = True

        elif window.visible:
            window.command("opacity " + args.opacity)
            if window.app_id == 'firefox':
                firefox_visible_or_focused = True

    if firefox_visible_or_focused == False:
        stop_firefox(signal.SIGSTOP)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.on("window::focus", partial(on_window_focus, args.opacity))
    ipc.on("window::move", partial(on_window_move, args.opacity))
    ipc.on("window::new", partial(check_firefox_exists))
    ipc.on("window::close", partial(check_firefox_exists))

    ipc.main()
