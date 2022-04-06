#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys
sys.path.append('/home/tb/code/i3ipc-python')

import i3ipc
import signal
from typing import Dict
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
    PARENT= 1
    CHILDREN= 2
    ALL= 3


policy = {
    "Alacritty": KillStatus.PARENT,
    "firefox": KillStatus.CHILDREN,
    "sublime_text": KillStatus.ALL,
    "PopUp": KillStatus.KEEPALIVE,
}

def signal_app(app: Dict, signal: MySignal):
    global app_dict

    app_pid: int = app['pid']
    app_id: str = app['app_id']
    if app_pid == -1:
        print('this should not happen')
        return

    this_policy = policy[app_id]
    if this_policy == KillStatus.KEEPALIVE:
        return

    app_paused: bool = app['paused']

    if not app_paused and signal == MySignal.SIGCONT:
        return
    if app_paused and signal == MySignal.SIGSTOP:
        return
    app_paused = not app_paused
    app_dict[app_pid]['paused'] = app_paused

    parent = psutil.Process(app_pid)
    if this_policy == KillStatus.CHILDREN or this_policy == KillStatus.ALL:
        for child in parent.children(recursive=True):
            child.send_signal(signal)
    if this_policy == KillStatus.PARENT or this_policy == KillStatus.ALL:
        parent.send_signal(signal)


def check_app_close(ipc, event):
    global app_dict
    app_dict.pop(event.container.pid)

def check_app_open(ipc, event):
    global app_dict
    window = event.container
    app = {}
    app['paused'] = False
    app['app_id'] = window.app_id
    app['pid'] = window.pid
    app_dict[window.pid] = app

def on_window_focus(ipc, event):
    # race condition workaround:
    focused = ipc.get_tree().find_focused()
    if focused is None:
        return
    descendants = focused.workspace().descendants()
    if len(descendants) == 1 and descendants[0].type != 'floating_con':
        descendants[0].command("fullscreen enable")
        # if len([output for output in ipc.get_outputs() if output.active]) == 1:


def on_workspace_focus(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    for window in ipc.get_tree():
        if window.app_id is None:
            continue
        app = app_dict[window.pid]
        if window.visible:
            signal_app(app, MySignal.SIGCONT)
        else:
            signal_app(app, MySignal.SIGSTOP)

def on_workspace_init(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    for app in app_dict:
        signal_app(app_dict[app], MySignal.SIGSTOP)


def exit_handler(ipc):
    for app in app_dict:
        signal_app(app_dict[app], MySignal.SIGCONT)
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

    if power_status == power_status.ON_BATTERY:
        for window in ipc.get_tree():
            if window.app_id is None:
                continue
            app = app_dict[window.pid]
            if window.visible:
                signal_app(app, MySignal.SIGCONT)
            else:
                signal_app(app, MySignal.SIGSTOP)
    else:
        for app in app_dict:
            signal_app(app_dict[app], MySignal.SIGCONT)


def set_init_pids(ipc, event=None) -> None:
    global app_dict
    for window in ipc.get_tree():
        if window.app_id is None:
            continue
        app = {}
        app['paused'] = False
        app['app_id'] = window.app_id
        app['pid'] = window.pid
        app_dict[window.pid] = app


if __name__ == "__main__":
    ipc = i3ipc.Connection()
    app_dict = {}

    set_init_pids(ipc)
    power_status = None
    set_power_status(ipc)

    ipc.on("window::focus", on_window_focus)
    if power_status != PowerStatus.NOT_A_LAPTOP:
        ipc.on("window::new", check_app_open)
        ipc.on("window::close", check_app_close)
        ipc.on("workspace::init", on_workspace_init)
        ipc.on('workspace::focus', on_workspace_focus)
        signal.signal(signal.SIGUSR1, lambda signal, frame: set_power_status(ipc))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
