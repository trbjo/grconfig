#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import sys
sys.path.append('/home/tb/code/i3ipc-python')

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
    for child in parent.children(recursive=True):
        child.send_signal(signal)

def on_window_new_or_close(ipc, event):
    check_firefox_exists(ipc, event)

def on_window_focus(ipc, event):
    descendants = ipc.get_tree().find_focused().workspace().descendants()
    if len(descendants) == 1:
        descendants[0].command("fullscreen enable")
        # if len([output for output in ipc.get_outputs() if output.active]) == 1:

def on_workspace_init_or_focus(ipc, event):
    global POWER_STATUS
    if POWER_STATUS == PowerStatus.ON_BATTERY:
        global FIREFOX_PID
        if FIREFOX_PID != -1:
            if ipc.get_tree().find_by_pid(FIREFOX_PID)[0].visible:
                signal_firefox(FIREFOX_PID, MySignal.SIGCONT)
            else:
                signal_firefox(FIREFOX_PID, MySignal.SIGSTOP)


def exit_handler(ipc):
    global POWER_STATUS
    global FIREFOX_PID
    if POWER_STATUS != PowerStatus.NOT_A_LAPTOP and FIREFOX_PID != -1:
        signal_firefox(FIREFOX_PID, MySignal.SIGCONT)
    ipc.main_quit()
    sys.exit(0)


def should_firefox_continue(ipc):
    global POWER_STATUS
    ac_adapter = None
    for f in glob.glob('/sys/class/power_supply/AC*', recursive=False):
        ac_adapter = f
        break

    if ac_adapter is None:
        POWER_STATUS = PowerStatus.NOT_A_LAPTOP
    else:
        with open(f'{ac_adapter}/online', mode='rb') as fd:
            res = fd.read().decode().split('\x0A')[0]
            if res == '0':
                POWER_STATUS = PowerStatus.ON_BATTERY
            else:
                POWER_STATUS = PowerStatus.ON_AC

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


if __name__ == "__main__":
    ipc = i3ipc.Connection()
    prev_workspace = ipc.get_tree().find_focused().workspace().num

    FIREFOX_PID: int = -1
    check_firefox_exists(ipc)

    POWER_STATUS = None
    should_firefox_continue(ipc)

    signal.signal(signal.SIGUSR1, lambda signal, frame: should_firefox_continue(ipc))
    ipc.on("window::focus", on_window_focus)
    ipc.on("window::new", on_window_new_or_close)
    ipc.on("window::close", on_window_new_or_close)
    ipc.on("workspace::init", on_workspace_init_or_focus)
    ipc.on('workspace::focus', on_workspace_init_or_focus)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
