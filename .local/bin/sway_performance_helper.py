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

class PowerStatus(IntEnum):
    NOT_A_LAPTOP = 1
    ON_AC = 18
    ON_BATTERY = 19

class MySignal(IntEnum):
    SIGCONT = 18
    SIGSTOP = 19

def signal_firefox(signal: MySignal):
    global FIREFOX_RUNNING
    if FIREFOX_RUNNING and signal == MySignal.SIGCONT:
        return
    if not FIREFOX_RUNNING and signal == MySignal.SIGSTOP:
        return
    FIREFOX_RUNNING = not FIREFOX_RUNNING
    global FIREFOX_PID
    parent = psutil.Process(FIREFOX_PID)
    for child in parent.children(recursive=True):
        child.send_signal(signal)


def check_firefox_close(ipc, event):
    global num_of_firefox_windows
    if event.container.app_id == 'firefox':
        if num_of_firefox_windows == 1:
            global FIREFOX_PID
            FIREFOX_PID = -1
        num_of_firefox_windows-=1


def check_firefox_open(ipc, event):
    global num_of_firefox_windows
    if event.container.app_id == 'firefox':
        if num_of_firefox_windows == 0:
            global FIREFOX_PID
            FIREFOX_PID = event.container.pid
        num_of_firefox_windows+=1


def on_window_focus(ipc, event):
    # race condition workaround:
    focused = ipc.get_tree().find_focused()
    if focused is None:
        return
    descendants = focused.workspace().descendants()
    if len(descendants) == 1 and descendants[0].type != 'floating_con':
        descendants[0].command("fullscreen enable")
        # if len([output for output in ipc.get_outputs() if output.active]) == 1:


def on_workspace_init_or_focus(ipc, event=None):
    global POWER_STATUS
    if POWER_STATUS != PowerStatus.ON_BATTERY:
        return
    global FIREFOX_PID
    if FIREFOX_PID == -1:
        return
    if ipc.get_tree().find_by_pid(FIREFOX_PID)[0].visible:
        signal_firefox(MySignal.SIGCONT)
    else:
        signal_firefox(MySignal.SIGSTOP)


def exit_handler(ipc):
    global FIREFOX_PID
    global POWER_STATUS
    if FIREFOX_PID != -1 and POWER_STATUS != PowerStatus.NOT_A_LAPTOP:
        signal_firefox(MySignal.SIGCONT)

    ipc.main_quit()
    sys.exit(0)


def set_power_status(ipc):
    global POWER_STATUS
    ac_adapter = None
    for f in glob.glob('/sys/class/power_supply/AC*', recursive=False):
        ac_adapter = f
        break
    if ac_adapter is None:
        POWER_STATUS = PowerStatus.NOT_A_LAPTOP
        return
    with open(f'{ac_adapter}/online', mode='rb') as fd:
        res = fd.read().decode().split('\x0A')[0]
        if res == '0':
            POWER_STATUS = PowerStatus.ON_BATTERY
        else:
            POWER_STATUS = PowerStatus.ON_AC

    global FIREFOX_PID
    if FIREFOX_PID == -1:
        return
    if POWER_STATUS == PowerStatus.ON_BATTERY and not ipc.get_tree().find_by_pid(FIREFOX_PID)[0].visible:
        signal_firefox(MySignal.SIGSTOP)
    else:
        signal_firefox(MySignal.SIGCONT)


def set_firefox_pid_init(ipc, event=None) -> None:
    global num_of_firefox_windows
    global FIREFOX_PID
    for window in ipc.get_tree():
        if window.app_id == 'firefox':
            if FIREFOX_PID == -1:
                FIREFOX_PID = window.pid
            num_of_firefox_windows+=1

if __name__ == "__main__":
    ipc = i3ipc.Connection()

    # we assume the sigstop/sigcont status of firefox to be running when we start the script
    FIREFOX_RUNNING: bool = True

    num_of_firefox_windows: int = 0
    FIREFOX_PID: int = -1
    set_firefox_pid_init(ipc)
    POWER_STATUS = None
    set_power_status(ipc)

    ipc.on("window::focus", on_window_focus)
    if POWER_STATUS != PowerStatus.NOT_A_LAPTOP:
        ipc.on("window::new", check_firefox_open)
        ipc.on("window::close", check_firefox_close)
        ipc.on("workspace::init", on_workspace_init_or_focus)
        ipc.on('workspace::focus', on_workspace_init_or_focus)
        signal.signal(signal.SIGUSR1, lambda signal, frame: set_power_status(ipc))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: exit_handler(ipc))

    ipc.main()
