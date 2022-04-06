#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys

sys.path.append('/home/tb/code/i3ipc-python')

import i3ipc
from i3ipc.connection import *
from i3ipc.events import *
import signal
from typing import Set, List
from functools import partial
from enum import Enum, IntEnum
import glob
import psutil

class PowerStatus(IntEnum):
    NOT_A_LAPTOP = 1
    ON_AC = 18
    ON_BATTERY = 19

class MySignal(IntEnum):
    SIGCONT = 18
    SIGSTOP = 19

def signal_firefox(signal: MySignal):
    global firefox_running
    if firefox_running and signal == MySignal.SIGCONT:
        return
    if not firefox_running and signal == MySignal.SIGSTOP:
        return
    firefox_running = not firefox_running
    parent = psutil.Process(firefox_pid)
    for child in parent.children(recursive=True):
        child.send_signal(signal)

def signal_alacritty(alacrittys: List[int]):
    for alacritty in alacrittys:
        psutil.Process(alacritty).send_signal(MySignal.SIGSTOP)


def check_firefox_close(_, event: WindowEvent):
    global num_of_firefox_windows
    global alacrittys
    if event.container.app_id == 'Alacritty':
        pid: int = event.container.pid
        alacrittys.remove(pid)
    if event.container.app_id == 'firefox':
        if num_of_firefox_windows == 1:
            global firefox_pid
            firefox_pid = -1
        num_of_firefox_windows-=1


def check_firefox_open(ipc: Connection, event: WindowEvent):
    global num_of_firefox_windows
    global alacrittys
    if event.container.app_id == 'Alacritty':
        pid: int = event.container.pid
        alacrittys.add(pid)
    elif event.container.app_id == 'firefox':
        if num_of_firefox_windows == 0:
            global firefox_pid
            firefox_pid = event.container.pid
        num_of_firefox_windows+=1


def on_window_focus(ipc: Connection, event: WindowEvent):
    app = event.ipc_data['container']
    if app['app_id'] == 'Alacritty':
        psutil.Process(app['pid']).send_signal(signal.SIGCONT)

    # race condition workaround:
    focused = ipc.get_tree().find_focused()
    if focused is None:
        return

    descendants = focused.workspace().descendants()
    if len(descendants) == 1 and descendants[0].type != 'floating_con':
        descendants[0].command("fullscreen enable")
        # if len([output for output in ipc.get_outputs() if output.active]) == 1:


def on_workspace_focus(ipc: Connection, event: WorkspaceEvent):
    for window in ipc.get_tree():
        if window.app_id == 'Alacritty':
            if window.visible:
                psutil.Process(window.pid).send_signal(signal.SIGCONT)
            else:
                psutil.Process(window.pid).send_signal(MySignal.SIGSTOP)

    if power_status != PowerStatus.ON_BATTERY:
        return
    if firefox_pid == -1:
        return
    elif ipc.get_tree().find_by_pid(firefox_pid)[0].visible:
        signal_firefox(MySignal.SIGCONT)
    else:
        signal_firefox(MySignal.SIGSTOP)


def on_workspace_init(ipc: Connection, event: WorkspaceEvent):
    if power_status != PowerStatus.ON_BATTERY:
        return
    if firefox_pid == -1:
        return
    signal_alacritty(alacrittys)
    signal_firefox(MySignal.SIGSTOP)


def exit_handler(ipc: Connection):
    if firefox_pid != -1 and power_status != PowerStatus.NOT_A_LAPTOP:
        signal_firefox(MySignal.SIGCONT)
    ipc.main_quit()
    sys.exit(0)


def set_power_status(ipc: Connection):
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

    if firefox_pid == -1:
        return
    if power_status == PowerStatus.ON_BATTERY and not ipc.get_tree().find_by_pid(firefox_pid)[0].visible:
        signal_firefox(MySignal.SIGSTOP)
    else:
        signal_firefox(MySignal.SIGCONT)


def set_init_pids(ipc: Connection, event=None) -> None:
    global num_of_firefox_windows
    global firefox_pid
    global sublime_pid
    global alacrittys
    for window in ipc.get_tree():
        if window.app_id == 'firefox':
            if firefox_pid == -1:
                firefox_pid = window.pid
            num_of_firefox_windows+=1
        elif window.app_id == 'Alacritty':
            alacrittys.add(window.pid)
        elif window.app_id == 'sublime_text':
            sublime_pid = window.pid


if __name__ == "__main__":
    ipc: Connection = i3ipc.Connection()
    alacrittys: Set[int] = set()

    # we assume the sigstop/sigcont status of firefox to be running when we start the script
    firefox_running: bool = True

    num_of_firefox_windows: int = 0
    firefox_pid: int = -1
    sublime_pid: int = -1
    set_init_pids(ipc)
    power_status = None
    set_power_status(ipc)

    ipc.on("window::focus", on_window_focus)
    if power_status != PowerStatus.NOT_A_LAPTOP:
        ipc.on("window::new", check_firefox_open)
        ipc.on("window::close", check_firefox_close)
        ipc.on("workspace::init", on_workspace_init)
        ipc.on('workspace::focus', on_workspace_focus)
        signal.signal(signal.SIGUSR1, lambda signal, frame: set_power_status(ipc))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
