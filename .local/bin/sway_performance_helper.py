#!/usr/bin/python

import os
import sys
from typing import Dict

HOME=os.getenv('HOME')
sys.path.append(f'{HOME}/code/i3ipc-python')

import i3ipc
import signal
from enum import IntEnum
import glob
import psutil
import threading
import time

PAUSE_SECS = 90
RUN_SECS = 3
STOPPED_APPS: Dict[int,str] = {}

def periodically_pause(pause=True):
    time.sleep(PAUSE_SECS if pause else RUN_SECS)
    if power_status == PowerStatus.ON_BATTERY:
        if pause:
            apps = STOPPED_APPS.copy()
            sign = signal.SIGCONT
        else:
            apps = STOPPED_APPS
            sign = signal.SIGSTOP
        for pid,app_id in apps.items():
            send_signal(pid, app_id, sign)
    periodically_pause(not pause)

class PowerStatus(IntEnum):
    NOT_A_LAPTOP = 1
    ON_AC = 18
    ON_BATTERY = 19

def send_signal(pid: int, app_id: str, sign: signal):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=False if app_id == 'Alacritty' else True):
            child.send_signal(sign)
        parent.send_signal(sign)
    except psutil.AccessDenied:
        pass
    except psutil.NoSuchProcess:
        pass

def stop_app(pid: int, app_id: str):
    send_signal(pid, app_id, signal.SIGSTOP)
    global STOPPED_APPS
    STOPPED_APPS[pid] = app_id

def start_app(pid: int, app_id: str):
    global STOPPED_APPS
    try:
        del STOPPED_APPS[pid]
    except KeyError:
        pass
    send_signal(pid, app_id, signal.SIGCONT)

def check_app_close(ipc, event):
    start_app(event.container.pid, event.container.app_id)
    global prev_app
    prev_app = None

def on_window_focus(ipc, event):
    start_app(event.container.pid, event.container.app_id)
    # race condition workaround:
    focused = ipc.get_tree().find_focused()
    if focused is None:
        print('Focused is none :-(')
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
                stop_app(con.pid, con.app_id)
        prev_app = event.container.pid
        return

    workspace_changed = False
    for window in descendants:
        if window.app_id and window.visible:
            start_app(window.pid, window.app_id)

    for window in prev_ws:
        if window.app_id:
            stop_app(window.pid, window.app_id)

def on_window_move(ipc, event):
    if power_status != PowerStatus.ON_BATTERY:
        return
    descendants = current_ws.descendants()
    if len(descendants) > 1:
        for d in descendants:
            if d.app_id and d.visible:
                start_app(d.pid, d.app_id)


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
            stop_app(window.pid, window.app_id)
    global prev_ws
    prev_ws = current_ws
    current_ws = event.current


def exit_handler(ipc):
    print('got signal')
    for window in ipc.get_tree():
        if window.app_id is not None:
            start_app(window.pid, window.app_id)
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
            for window in ipc.get_tree():
                if window.app_id is None or window.visible:
                    continue
                stop_app(window.pid, window.app_id)
        else:
            power_status = PowerStatus.ON_AC
            for window in ipc.get_tree():
                if window.app_id is None or window.visible:
                    continue
                start_app(window.pid, window.app_id)



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
        threading.Thread(target=periodically_pause).start()
        ipc.on("window::move", on_window_move)
        ipc.on("window::close", check_app_close)
        ipc.on("workspace::init", on_workspace_init)
        ipc.on('workspace::focus', on_workspace_focus)
        signal.signal(signal.SIGUSR1, lambda signal, frame: set_power_status(ipc))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
