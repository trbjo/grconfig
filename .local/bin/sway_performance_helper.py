#!/usr/bin/python

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

def signal_app(pid: int, app_id: str, signal: int):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=False if app_id == 'Alacritty' else True):
            child.send_signal(signal)
        parent.send_signal(signal)
    except psutil.AccessDenied:
        pass
    except psutil.NoSuchProcess:
        pass

def check_app_close(ipc, event):
    signal_app(event.container.pid, event.container.app_id, signal.SIGCONT)
    global prev_app
    prev_app = None

def on_window_focus(ipc, event):
    signal_app(event.container.pid, event.container.app_id, signal.SIGCONT)
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
    global workspace_changed
    # workspace not changed, meaning we only need to check the previous container
    if not workspace_changed:
        global prev_app
        if prev_app is not None:
            if prev_app == event.container.pid:
                return
            con = ipc.get_tree().find_by_pid(prev_app)[0]
            if not con.visible:
                signal_app(prev_app, con.app_id, signal.SIGSTOP)
        prev_app = event.container.pid
        return

    workspace_changed = False
    for window in focused:
        if window.app_id and window.visible:
            signal_app(window.pid, window.app_id, signal.SIGCONT)

    for window in prev_ws:
        if window.app_id:
            signal_app(window.pid, window.app_id, signal.SIGSTOP)

def on_window_move(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    descendants = current_ws.descendants()
    if len(descendants) > 1:
        for d in descendants:
            if d.app_id and d.visible:
                signal_app(d.pid, d.app_id, signal.SIGCONT)


def on_workspace_focus(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    global workspace_changed
    workspace_changed = True
    global current_ws
    current_ws = event.current
    global prev_ws
    prev_ws = event.old

def on_workspace_init(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    global current_ws
    for window in current_ws:
        if window.app_id:
            signal_app(window.pid, window.app_id, signal.SIGSTOP)
    global prev_ws
    prev_ws = current_ws
    current_ws = event.current


def exit_handler(ipc):
    for window in ipc.get_tree():
        if window.app_id is not None:
            signal_app(window.pid, window.app_id, signal.SIGCONT)
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
        if window.app_id is None or window.visible:
            continue
        signal_app(window.pid, window.app_id, power_status)


if __name__ == "__main__":
    ipc = i3ipc.Connection()

    current_ws = ipc.get_tree().find_focused().workspace()
    prev_ws = ipc.get_tree().find_focused().workspace()
    prev_app = None
    power_status = PowerStatus.ON_BATTERY
    set_power_status(ipc)
    workspace_changed = False

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
