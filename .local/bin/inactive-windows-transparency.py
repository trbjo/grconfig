#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys
sys.path.append('/home/tb/code/i3ipc-python')


from gi.repository import Gio

import argparse
import i3ipc
import signal
from functools import partial
from enum import Enum, IntEnum
import glob
import psutil

class PowerStatus(Enum):
    NOT_A_LAPTOP = 1
    ON_BATTERY = 2
    ON_AC = 3

class MySignal(IntEnum):
    SIGCONT = 18
    SIGSTOP = 19


def signal_firefox(firefox_pid, signal: MySignal):
    parent = psutil.Process(firefox_pid)
    for child in parent.children(recursive=True):  # or parent.children() for recursive=False
        child.send_signal(signal)
    # we leave the parent as it handles the clipboard
    # parent.kill()

def on_workspace_init(ipc, event):
    if FIREFOX_PID != -1 and POWER_STATUS == PowerStatus.ON_BATTERY:
        signal_firefox(FIREFOX_PID, MySignal.SIGCONT)

def on_window_move(ipc, event):
    focused_workspace = ipc.get_tree().find_focused()
    if focused_workspace == None:
        return

    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            if w.visible:
                if not w.focused and not w.app_id == 'mpv':
                    w.command("opacity " + OPACITY)
                else:
                    w.command("opacity 1")
            else:
                if not w.focused:
                    w.command("opacity 1")


def on_window_focus(ipc, event):
    global OPACITY
    focused_workspace = ipc.get_tree().find_focused()
    focused = event.container

    global POWER_STATUS
    if POWER_STATUS == PowerStatus.ON_BATTERY:
        global FIREFOX_PID
        if FIREFOX_PID != -1:
            if focused.app_id == 'firefox':
                signal_firefox(FIREFOX_PID, MySignal.SIGCONT)
            elif ipc.get_tree().find_by_pid(FIREFOX_PID)[0].visible:
                signal_firefox(FIREFOX_PID, MySignal.SIGCONT)
            else:
                signal_firefox(FIREFOX_PID, MySignal.SIGSTOP)

    if focused_workspace == None:
        return

    global prev_focused
    global prev_workspace

    workspace = focused_workspace.workspace().num

    if focused.id != prev_focused.id:  # https://github.com/swaywm/sway/issues/2859
        focused.command("opacity 1")
        if workspace == prev_workspace:
            old = ipc.get_tree().find_by_id(prev_focused.id)
            if old is not None:
                if old.visible and prev_focused.type != 'floating_con' and old.app_id != 'mpv':
                    prev_focused.command("opacity " + OPACITY)
        else:
            if prev_focused.type != 'floating_con' and prev_focused.app_id != 'mpv':
                prev_focused.command("opacity " + OPACITY)

        prev_focused = focused
        prev_workspace = workspace

    if len(focused_workspace.workspace().descendants()) == 1:
        if len([output for output in ipc.get_outputs() if output.active]) == 1:
            focused.command("fullscreen enable")


def exit_handler(ipc):
    global POWER_STATUS
    if POWER_STATUS != PowerStatus.NOT_A_LAPTOP and FIREFOX_PID != -1:
        signal_firefox(FIREFOX_PID, MySignal.SIGCONT)
    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            w.command("opacity 1")
    ipc.main_quit()
    sys.exit(0)


def find_power_status(ipc):
    global POWER_STATUS
    AC_ADAPTER = None
    for f in glob.glob('/sys/class/power_supply/AC*', recursive=False):
        AC_ADAPTER = f
        break

    if AC_ADAPTER is not None:
        with open(f'{AC_ADAPTER}/online', mode='rb') as fd:
            res = fd.read().decode().split('\x0A')[0]
            if res == '0':
                POWER_STATUS = PowerStatus.ON_BATTERY
            else:
                POWER_STATUS = PowerStatus.ON_AC
    else:
        POWER_STATUS = PowerStatus.NOT_A_LAPTOP

    if FIREFOX_PID != -1:
        if POWER_STATUS == POWER_STATUS.ON_BATTERY and not ipc.get_tree().find_by_pid(FIREFOX_PID)[0].visible:
            signal_firefox(FIREFOX_PID, MySignal.SIGSTOP)
        else:
            signal_firefox(FIREFOX_PID, MySignal.SIGCONT)


def check_firefox_exists(ipc, event=None) -> None:
    global FIREFOX_PID
    try:
        cont = event.container
        if cont.app_id == 'firefox':
            if event.change == 'new':
                FIREFOX_PID = cont.pid
            elif event.change == 'close':
                FIREFOX_PID = -1
            else:
                raise Exception(f'Unknown event: {event.change}')
    except AttributeError:
        for window in ipc.get_tree():
            if window.app_id == 'firefox':
                FIREFOX_PID = window.pid
                if window.visible:
                    signal_firefox(FIREFOX_PID, MySignal.SIGSTOP)
                break


def signal_handler(ipc, inactive_opacities):
    global prev_focused
    global OPACITY
    theme = str(gso.get_value("gtk-theme"))
    # light theme, lower higher opacity
    if theme == "'Adwaita'":
        OPACITY = inactive_opacities[0]
    else:
        OPACITY = inactive_opacities[1]

    for window in ipc.get_tree():
        if window.focused:
            prev_focused = window

        elif window.visible:
            window.command("opacity " + OPACITY)

    ipc.on("window::focus", partial(on_window_focus))
    ipc.on("window::move", partial(on_window_move))


prev_focused = None

if __name__ == "__main__":
    transparency_val = [ "0.94", "0.7" ]

    parser = argparse.ArgumentParser(
        description="This script allows you to set the transparency of unfocused windows in sway."
    )
    parser.add_argument(
        "--opacity",
        "-o",
        type=lambda s: [item for item in s.split(',')],
        default=transparency_val,
        help="set opacity value in range 0...1",
    )
    args = parser.parse_args()

    ipc = i3ipc.Connection()
    prev_workspace = ipc.get_tree().find_focused().workspace().num

    FIREFOX_PID = None
    check_firefox_exists(ipc)

    POWER_STATUS = None
    find_power_status(ipc)

    if POWER_STATUS != PowerStatus.NOT_A_LAPTOP:
        signal.signal(signal.SIGUSR1, lambda signal, frame: find_power_status(ipc))
        ipc.on("window::new", check_firefox_exists)
        ipc.on("window::close", check_firefox_exists)
        ipc.on("workspace::init", on_workspace_init)

    OPACITY = None
    gso=Gio.Settings.new("org.gnome.desktop.interface")
    signal_handler(ipc, args.opacity)

    signal.signal(signal.SIGUSR2, lambda signal, frame: signal_handler(ipc, args.opacity))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
