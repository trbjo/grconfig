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
from enum import Enum
import glob

class PowerStatus(Enum):
    NOT_A_LAPTOP = 1
    ON_BATTERY = 2
    ON_AC = 3


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


def on_workspace_init(ipc, event):
    if firefox_con_id != -1 and power_status == PowerStatus.ON_BATTERY:
        stop_firefox(signal.SIGSTOP)

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


def on_window_focus(inactive_opacity, ipc, event):
    focused_workspace = ipc.get_tree().find_focused()
    focused = event.container

    global power_status
    if power_status == PowerStatus.ON_BATTERY:
        global firefox_con_id
        if firefox_con_id != -1:
            if focused.app_id == 'firefox':
                stop_firefox(signal.SIGCONT)
            elif ipc.get_tree().find_by_id(firefox_con_id).visible:
                stop_firefox(signal.SIGCONT)
            else:
                stop_firefox(signal.SIGSTOP)

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
                if old.visible and prev_focused.type != 'floating_con':
                    prev_focused.command("opacity " + inactive_opacity)
        else:
            if prev_focused.type != 'floating_con':
                prev_focused.command("opacity " + inactive_opacity)

        prev_focused = focused
        prev_workspace = workspace

    if len(focused_workspace.workspace().descendants()) == 1:
        focused.command("fullscreen enable")


def running_on_battery(ipc):
    global power_status
    power_status = PowerStatus.ON_BATTERY
    if firefox_con_id != -1:
        firefox = ipc.get_tree().find_by_id(firefox_con_id)
        if not firefox.visible:
            stop_firefox(signal.SIGSTOP)

def running_on_ac(ipc):
    global power_status
    power_status = PowerStatus.ON_AC
    if firefox_con_id != -1:
        firefox = ipc.get_tree().find_by_id(firefox_con_id)
        stop_firefox(signal.SIGCONT)


def exit_handler(ipc):
    global power_status
    if power_status != PowerStatus.NOT_A_LAPTOP and firefox_con_id != -1:
        stop_firefox(signal.SIGCONT)
    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            w.command("opacity 1")
    ipc.main_quit()
    sys.exit(0)

def find_power_status() -> PowerStatus:
    AC_ADAPTER = None
    for f in glob.glob('/sys/class/power_supply/AC*', recursive=False):
        AC_ADAPTER = f
        break

    if AC_ADAPTER is not None:
        with open(f'{AC_ADAPTER}/online', mode='rb') as fd:
            res = fd.read().decode().split('\x0A')[0]
            if res == '0':
                return PowerStatus.ON_BATTERY
            else:
                return PowerStatus.ON_AC
    else:
        return PowerStatus.NOT_A_LAPTOP


def check_firefox_exists(ipc, event) -> None:
    global firefox_con_id
    cont = event.container
    if cont.app_id == 'firefox':
        if event.change == 'new':
            firefox_con_id = cont.id
        elif event.change == 'close':
            firefox_con_id = -1
        else:
            raise Exception(f'Unknown event: {event.change}')


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
    power_status: PowerStatus = find_power_status()

    for window in ipc.get_tree():
        if window.focused:
            prev_focused = window

        elif window.visible:
            window.command("opacity " + args.opacity)

    # If we are not on a laptop, we do not care about Firefox power saving:
    if power_status != PowerStatus.NOT_A_LAPTOP:
        firefox_con_id = -1
        for window in ipc.get_tree():
            if window.app_id == 'firefox':
                firefox_con_id = window.id
                if window.visible:
                    stop_firefox(signal.SIGSTOP)
                break

        signal.signal(signal.SIGUSR1, lambda signal, frame: running_on_battery(ipc))
        signal.signal(signal.SIGUSR2, lambda signal, frame: running_on_ac(ipc))

        ipc.on("window::new", partial(check_firefox_exists))
        ipc.on("window::close", partial(check_firefox_exists))
        ipc.on("workspace::init", partial(on_workspace_init))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.on("window::focus", partial(on_window_focus, args.opacity))
    ipc.on("window::move", partial(on_window_move, args.opacity))


    ipc.main()
