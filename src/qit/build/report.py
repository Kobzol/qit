import threading

import select
from enum import Enum


class ReportEvent(Enum):
    ProgressPush = "PROGRESS_PUSH"
    ProgressPop = "PROGRESS_POP"
    ProgressUpdate = "PROGRESS_UPDATE"
    Error = "ERROR"
    Unknown = "UNKNOWN"

    @staticmethod
    def find_by_tag(tag):
        if tag in [e.value for e in ReportEvent]:
            return ReportEvent(tag)
        else:
            return ReportEvent.Unknown


class ReportHandler(object):
    def __init__(self, fifo):
        self.fifo = fifo
        self.stop_event = threading.Event()
        self.callbacks = []
        self.read_thread = None

    def _on_message_received(self, tag, args):
        for callback in self.callbacks:
            callback(tag, args)

    def subscribe(self, callback):
        self.callbacks.append(callback)

    def start(self):
        self.read_thread = threading.Thread(target=self.read_fifo, args=(self.fifo,))
        self.read_thread.start()

    def stop(self):
        self.stop_event.set()
        self.callbacks.clear()
        self.read_thread.join()

    def read_fifo(self, fifo):
        with open(fifo, "r", buffering=1) as file:  # line buffered
            while not self.stop_event.is_set():
                if len(select.select([file], [], [], 0.1)[0]) != 0:
                    msg = file.readline().strip().split(" ")
                    tag = msg[0]
                    args = msg[1:]

                    if tag:
                        self._on_message_received(tag, args)
