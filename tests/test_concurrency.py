"""Tests for Sandy concurrency: spawn/wait and channels.

Output is made deterministic by synchronizing through channels, so these are
stable despite running real background tasks.

Run with:  python -m unittest tests.test_concurrency
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.interpreter import Interpreter
from sandy.runtime import run_source, run_source_vm


def run(src):
    out = io.StringIO()
    run_source(src, Interpreter(out=out))
    return out.getvalue()


class TestConcurrency(unittest.TestCase):
    def test_spawn_and_wait_returns_result(self):
        self.assertEqual(
            run("fn sq(n) { return n * n }\nt = spawn(sq, 9)\nprint(wait(t))\n"),
            "81\n")

    def test_unbuffered_channel_rendezvous(self):
        src = ("ch = channel()\nfn p() { send(ch, 42) }\nspawn(p)\n"
               "print(recv(ch))\n")
        self.assertEqual(run(src), "42\n")

    def test_fan_in_from_many_workers(self):
        src = ("results = channel(10)\n"
               "fn worker(id) { send(results, id * 10) }\n"
               "i = 1\nwhile i <= 5 { spawn(worker, i)\n i += 1 }\n"
               "total = 0\ni = 0\nwhile i < 5 { total += recv(results)\n i += 1 }\n"
               "print(total)\n")
        self.assertEqual(run(src), "150\n")

    def test_close_then_drain_returns_nil(self):
        src = ("s = channel(3)\n"
               "fn emit() { for k in range(1, 4) { send(s, k) }\n close(s) }\n"
               "spawn(emit)\nsum = 0\nv = recv(s)\n"
               "while v != nil { sum += v\n v = recv(s) }\nprint(sum)\n")
        self.assertEqual(run(src), "6\n")

    def test_task_error_is_reraised_by_wait(self):
        src = ('fn boom() { throw "kaboom" }\nb = spawn(boom)\n'
               'msg = "none"\ntry { wait(b) } catch e { msg = e }\nprint(msg)\n')
        self.assertEqual(run(src), "kaboom\n")

    def test_buffered_channel_does_not_block_sender(self):
        # Capacity 2: the main task sends twice without a receiver, then reads.
        src = ("c = channel(2)\nsend(c, 1)\nsend(c, 2)\n"
               "print(recv(c))\nprint(recv(c))\n")
        self.assertEqual(run(src), "1\n2\n")

    def test_channel_and_task_types(self):
        self.assertEqual(
            run("print(type(channel()))\n"
                "fn f() { return 1 }\nprint(type(spawn(f)))\n"),
            "channel\ntask\n")

    def test_spawn_needs_a_function(self):
        from sandy.errors import RuntimeErrorSandy
        with self.assertRaises(RuntimeErrorSandy):
            run("spawn(5)\n")

    def test_channels_work_but_spawn_rejects_vm_functions(self):
        # Channels are engine-independent; spawn under the VM gets a VM function
        # value and reports the clear "default engine" error.
        vout = io.StringIO()
        run_source_vm("c = channel(1)\nsend(c, 7)\nprint(recv(c))\n", out=vout)
        self.assertEqual(vout.getvalue(), "7\n")
        from sandy.errors import RuntimeErrorSandy
        with self.assertRaises(RuntimeErrorSandy):
            run_source_vm("fn f() { return 1 }\nspawn(f)\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
