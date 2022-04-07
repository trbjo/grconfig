#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys
sys.path.append('/home/tb/code/i3ipc-python')

import i3ipc
import signal
from enum import IntEnum
import glob
import psutil

class PowerStatus(IntEnum):
    NOT_A_LAPTOP = 1
    ON_AC = 18
    ON_BATTERY = 19

class MySignal(IntEnum):
    SIGCONT = 18
    SIGSTOP = 19

class KillStatus(IntEnum):
    KEEPALIVE= 0
    CHILDREN= 1
    ALL= 2

def signal_app(pid: int, app_id: str, signal: MySignal):
    if app_id == 'Alacritty':
        kill = KillStatus.ALL
        rec = False
    elif app_id == 'firefox':
        kill = KillStatus.CHILDREN
        rec = True
    else:
        kill = KillStatus.ALL
        rec = True
    parent = psutil.Process(pid)
    try:
        if kill == KillStatus.CHILDREN or kill == KillStatus.ALL:
            for child in parent.children(recursive=rec):
                child.send_signal(signal)
        if kill == KillStatus.ALL:
            parent.send_signal(signal)
    except:
        pass


def check_app_close(ipc, event):
    signal_app(event.container.pid, event.container.app_id, MySignal.SIGCONT)
    global current_focus
    current_focus = None

def on_window_focus(ipc, event):
    signal_app(event.container.pid, event.container.app_id, MySignal.SIGCONT)
    # race condition workaround:
    focused = ipc.get_tree().find_focused()
    if focused is None:
        return
    descendants = focused.workspace().descendants()
    if len(descendants) == 1 and descendants[0].type != 'floating_con':
        descendants[0].command("fullscreen enable")
        # if len([output for output in ipc.get_outputs() if output.active]) == 1:

    if power_status != PowerStatus.ON_BATTERY:
        return

    global current_focus
    if current_focus is not None:
        con = ipc.get_tree().find_by_pid(current_focus)[0]
        if not con.visible:
            signal_app(current_focus, con.app_id, MySignal.SIGSTOP)
    current_focus = event.container.pid


def on_window_move(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    focused = ipc.get_tree().find_focused()
    if focused is None:
        return
    descendants = focused.workspace().descendants()
    if len(descendants) <= 1:
        return
    for d in descendants:
        if d.app_id is None:
            continue
        if d.visible:
            signal_app(d.pid, d.app_id, MySignal.SIGCONT)


def on_workspace_focus(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    if event.current is not None:
        global current_ws
        current_ws = event.current
        for window in event.current:
            if window.app_id is None:
                continue
            if window.visible:
                signal_app(window.pid, window.app_id, MySignal.SIGCONT)
            else:
                signal_app(window.pid, window.app_id, MySignal.SIGSTOP)
    if event.old is not None:
        for window in event.old:
            if window.app_id is None:
                continue
            if window.visible:
                signal_app(window.pid, window.app_id, MySignal.SIGCONT)
            else:
                signal_app(window.pid, window.app_id, MySignal.SIGSTOP)

def on_workspace_init(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    global current_ws
    if current_ws is not None:
        for window in event.current:
            if window.app_id is None:
                continue
            signal_app(window.pid, window.app_id, MySignal.SIGSTOP)
    current_ws = None


def exit_handler(ipc):
    for window in ipc.get_tree():
        if window.app_id is not None:
            signal_app(window.pid, window.app_id, MySignal.SIGCONT)
    ipc.main_quit()
    sys.exit(0)


def set_power_status(ipc):
    ac_adapter = None
    for f in glob.glob('/sys/class/power_supply/AC*', recursive=False):
        ac_adapter = f
        break
    global power_status
    if ac_adapter is None:
        power_status = PowerStatus.NOT_A_LAPTOP
        return
    with open(f'{ac_adapter}/online', mode='rb') as fd:
        res = fd.read().decode().split('\x0A')[0]
        if res == '0':
            power_status = PowerStatus.ON_BATTERY
        else:
            power_status = PowerStatus.ON_AC

    for window in ipc.get_tree():
        if window.app_id is None:
            continue
        if not window.visible and power_status == power_status.ON_BATTERY:
            signal_app(window.pid, window.app_id, MySignal.SIGSTOP)
        else:
            signal_app(window.pid, window.app_id, MySignal.SIGCONT)


if __name__ == "__main__":
    ipc = i3ipc.Connection()

    current_ws = None
    current_focus = None
    power_status = None
    set_power_status(ipc)

    ipc.on("window::focus", on_window_focus)
    if power_status != PowerStatus.NOT_A_LAPTOP:
        ipc.on("window::move", on_window_move)
        ipc.on("window::close", check_app_close)
        ipc.on("workspace::init", on_workspace_init)
        ipc.on('workspace::focus', on_workspace_focus)
        signal.signal(signal.SIGUSR1, lambda signal, frame: set_power_status(ipc))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
