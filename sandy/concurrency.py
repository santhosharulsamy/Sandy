"""Concurrency for Sandy: lightweight tasks and channels.

The model is Go-flavored and deliberately small:

  * `spawn(fn, args...)` runs a function as a background **task** and returns a
    handle; `wait(task)` blocks for it and yields its return value (re-raising
    any error the task hit).
  * a **channel** is the safe way for tasks to communicate — "share memory by
    communicating." `send`/`recv` block to synchronize; an unbuffered channel
    (`channel()`) is a rendezvous, a buffered one (`channel(n)`) holds up to n
    values before a sender blocks. `close(ch)` ends it; `recv` on a drained,
    closed channel returns nil.

Tasks are real OS threads. Channels are internally synchronized, so passing
values through them is safe; sharing plain variables between tasks without a
channel is a data race, exactly as in Go.
"""

import threading
from collections import deque

from .errors import RuntimeErrorSandy


class Task:
    _sandy_type = "task"

    def __init__(self):
        self.thread = None
        self.result = None
        self.error = None
        self.done = False

    def __repr__(self):
        return "<task>"


class Channel:
    _sandy_type = "channel"

    def __init__(self, capacity):
        self.cap = capacity
        self.items = deque()
        self.closed = False
        self.cond = threading.Condition()

    def send(self, value, line):
        with self.cond:
            if self.closed:
                raise RuntimeErrorSandy("send on a closed channel", line)
            self.items.append(value)
            self.cond.notify_all()
            # Block until the buffer drains to capacity (rendezvous when cap 0).
            while len(self.items) > self.cap and not self.closed:
                self.cond.wait()

    def recv(self, line):
        with self.cond:
            while not self.items and not self.closed:
                self.cond.wait()
            if not self.items:
                return None            # closed and drained
            value = self.items.popleft()
            self.cond.notify_all()
            return value

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()

    def length(self):
        with self.cond:
            return len(self.items)

    def __repr__(self):
        return "<channel>"


def spawn(interp, fn, args, line):
    """Run `fn(args...)` as a background task, returning a Task handle."""
    task = Task()

    def run():
        try:
            task.result = interp.call(fn, args, line)
        except Exception as e:            # noqa: BLE001 - surfaced via wait()
            task.error = e
        finally:
            task.done = True

    task.thread = threading.Thread(target=run, daemon=True)
    task.thread.start()
    return task


def wait(task, line):
    """Block until `task` finishes; return its value or re-raise its error."""
    task.thread.join()
    if task.error is not None:
        raise task.error
    return task.result
