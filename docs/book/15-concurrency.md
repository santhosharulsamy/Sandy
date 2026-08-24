# Chapter 15 — Concurrency

Sandy's concurrency model is small and Go-flavored: run work as **tasks**, and
have tasks communicate over **channels**. The guiding principle is *share memory
by communicating* — pass data through channels rather than reaching into shared
variables.

## Spawning a task

`spawn(fn, args...)` runs a function as a background task and returns a handle.
`wait(task)` blocks until the task finishes and returns its result:

```sandy
fn work(n) {
    return n * n
}

t = spawn(work, 12)
print(wait(t))       # 144
```

If the task raises an error, `wait` re-raises it, so you can wrap `wait` in a
`try`:

```sandy
fn boom() { throw "kaboom" }
b = spawn(boom)
try { wait(b) } catch e { print("task failed: " + e) }   # task failed: kaboom
```

## Channels

A channel carries values between tasks. Create one with `channel()`, then `send`
and `recv`:

```sandy
ch = channel()

fn producer() {
    send(ch, 42)
}
spawn(producer)

print(recv(ch))      # 42
```

`send` and `recv` **block to synchronize**:

- `channel()` — an **unbuffered** channel: a `send` waits until a `recv` takes
  the value (a rendezvous), so the two tasks hand off directly.
- `channel(n)` — a **buffered** channel holding up to `n` values before a sender
  blocks.

Because the operations block, values come out in a well-defined order even though
the work runs concurrently — which is what makes concurrent programs testable and
predictable.

## Closing a channel

`close(ch)` marks a channel finished. A `recv` on a drained, closed channel
returns `nil`, which gives a clean way to stream results and stop:

```sandy
stream = channel()

fn emit() {
    for k in range(1, 4) {
        send(stream, k)
    }
    close(stream)
}
spawn(emit)

v = recv(stream)
while v != nil {
    print(v)         # 1, 2, 3
    v = recv(stream)
}
```

## A worker pool

Putting it together — fan several tasks out and collect their results through one
channel:

```sandy
jobs = [1, 2, 3, 4, 5]
results = channel(len(jobs))

fn work(n) {
    send(results, n * n)
}
for n in jobs {
    spawn(work, n)
}

total = 0
i = 0
while i < len(jobs) {
    total += recv(results)
    i += 1
}
print(total)         # 55
```

## Safety

Channels are internally synchronized, so passing values through them is always
safe. Sharing a plain variable between tasks *without* a channel is a data race —
exactly as in Go. The rule of thumb: **communicate through channels**, and reach
for shared state only when you know what you're doing.

## Where it runs

Tasks are real threads. `spawn` runs on the default engine (the interpreter);
`channel`, `send`, `recv`, and `close` work everywhere. Because concurrency is
inherently dynamic, it is not part of the native-compilation subset — concurrent
programs run on the interpreter.

The next chapter turns to the other end of the spectrum: compiling for speed.
