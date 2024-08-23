# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import logging
import re
from reml.project import Project, Version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LTTngToolsProject(Project):
    def __init__(self) -> None:
        self._name = "LTTng-tools"
        self._changelog_project_name = "lttng-tools"
        self._release_template = """\
About this patch release
========================

{changelog}

**Full changelog**: {repo_url}/compare/{previous_tag}...{tag}

About {name} {series}
======================

{release_description}
"""
        self._release_descriptions = {
            "2.12": """\
This release is named after _Ta Meilleure_, a *Northeast IPA* beer brewed by Lagabière. Translating to "Your best one", this beer gives out strong aromas of passion fruit, lemon, and peaches. Tastewise, expect a lot of fruit, a creamy texture, and a smooth lingering hop bitterness.

The most notable features of this new release are:
  - session clearing,
  - uid and gid tracking,
  - file descriptor pooling (relay daemon),
  - per-session grouping (relay daemon),
  - working directory override (relay daemon),
  - new network reception entry/exit tracepoints (LTTng-modules),
  - statedump of interrupt threads (LTTng-modules),
  - statedump of x86 CPU topology (LTTng-modules),
  - new product UUID environment field (LTTng-modules).

Read on for a short description of each of these features and the links to this release!

Session clearing
---

You can use the new `lttng-clear` command to clear the contents of one or more tracing sessions.

In essence, this new feature allows you to prune the content of long-running sessions without destroying and reconfiguring them. This is especially useful to _clear_ a session's tracing data between attempts to reproduce a problem.

Clearing a tracing session deletes the contents of the tracing buffers and all local or streamed trace data on a remote peer. Note that an lttng-relayd daemon can be configured to disallow clear operations using the `LTTNG_RELAYD_DISALLOW_CLEAR` environment variable.

If a session is configured in snapshot mode, only the tracing buffers are cleared.

If a session is configured in live mode, any attached client that is lagging behind will finish the consumption of its current trace data packets and _jump forward_ in time to events generated after the beginning of the clear command.

uid and gid tracking
---

The existing `lttng-track` command has been expanded to support _uid_ and _gid_ tracking.

By default, a tracing session tracks all applications and users, following LTTng's permission model.
However, this new options allows you to restrict which users and groups are tracked by both the user space and kernel tracers.

In previous versions of LTTng, it was effectively possible to filter on the basis of uids and gids using the `--filter` mechanism. However, this dedicated filtering mechanism is both more efficient in terms of tracing overhead, but also prevents the creation of tracing buffers for users and groups which are not _tracked_.

Overall, this results in far less memory consumption by the user space tracer on systems which have multiple active users.

File descriptor pooling (relay daemon)
---

A number of users have reported having encountered file descriptor exhaustion issues when using the relay daemon to serve a large number of consumers or live clients.

The current on-disk CTF representation used by LTTng (and expected by a number of viewers) uses one file per CPU, per channel, to organize traces. This causes the default `RLIMIT_NOFILE` value (1024 on many systems) to be reached easily, especially when tracing systems with a large number of cores.

In order to alleviate this problem, the new `--fd-pool-size` option allows you to specify a maximal number of simultaneously opened file descriptors (using the soft `RLIMIT_NOFILE` resource limit of the process by default). This is meant as a work-around for users who can't bump the system-limit because of permission restrictions.

As its name indicates, this option causes the relay daemon to maintain a _pool_ (or _cache_) of open file descriptors which are re-purposed as needed. The most recently used files' file descriptors are kept open and only closed as the `--fd-pool-size` limit is reached, keeping the number of simultaneously opened file descriptors under the user-specified limit.

Note that setting this value too low can degrade the performance of the relay daemon.

Per-session grouping (relay daemon)
---

By default, the relay daemon writes the traces under a predefined directory hierarchy:
  `$LTTNG_HOME/lttng-traces/HOSTNAME/SESSION/DOMAIN` where
  - `HOSTNAME` is the remote hostname,
  - `SESSION` is the full session name,
  - `DOMAIN` is the tracing domain (`ust` or `kernel`),

Using the new relay daemon `--group-output-by-session` option, you can now change this hierarchy to group traces by sessions, rather than by hostname:
  `$LTTNG_HOME/lttng-traces/SESSION/HOST/DOMAIN`.

This proves especially useful if you are tracing a number of hosts (with different hostnames) which share the same session name as part of their configuration. Hence, a descriptive session name (e.g. `connection-hang`) can be used across a fleet of machines streaming to a given relay daemon.

Note that the default behaviour can be explicitly specified using the `--group-output-by-host` option.

Working directory override (relay daemon)
---

This small _quality of life_ feature allows you to override the _working directory_ of the relay daemon using the daemon's launch options (`-w PATH`/`--working-directory=PATH`).

New network reception entry/exit tracepoints (LTTng-modules)
---

New instrumentation hooks were added to the kernel tracer in order to trace the `entry` and `exit` tracepoints of the network reception code paths of the Linux kernel.

You can use those tracepoints to identify the bounds of a network reception and link the events that happen in the interim (e.g. `wakeup`s) to a specific network reception instance. Those tracepoints can also be used to analyse the network stack's latency.

Statedump of interrupt threads (LTTng-modules)
---

Threaded IRQs have an associated `thread` field in the `irqaction` structure which specifies the process to wake up when the IRQ happens. This field is now extracted as part of the `lttng_statedump_interrupt` statedump tracepoint.

You can use this information to know which processes handle the various IRQs. It is also possible to associate the events occurring in the context of those processes to their respective IRQ.

Statedump of x86 CPU topology (LTTng-modules)
---

A new `lttng_statedump_cpu_topology` tracepoint has been added to extract the active CPU/NUMA topology. You can use this information to know which CPUs are SMT siblings or part of the same socket. For the time being, only x86 is supported since all architectures describe their topologies differently.

The `architecture` field  is statically defined and should be present for all architecture implementations. Hence, it is possible for analysis tools to anticipate the event's layout.

Example output:
```
lttng_statedump_cpu_topology: { cpu_id = 3 }, { architecture = "x86", cpu_id = 0, vendor = "GenuineIntel", family = 6, model = 142, model_name = "Intel(R) Core(TM) i7-7600U CPU @ 2.80GHz", physical_id = 0, core_id = 0, cores = 2 }
```


New product UUID environment field (LTTng-modules)
---

The product UUID, taken from the DMI system information, is now saved as part of the kernel traces' environment fields as the `product_uuid`. You can use this field to uniquely identify a machine (virtual or physical) in order to correlate traces gathered on multiple virtual machines.
""",
            "2.13": """\
The most notable features of this new release are:

  - Event-rule matches condition triggers and new actions, allowing internal
    actions or external monitoring applications to quickly react when kernel
    or user-space instrumentation is hit,
  - Notification payload capture, allowing external monitoring applications
    to read elements of the instrumentation payload when instrumentation is
    hit.
  - Instrumentation API: vtracef and vtracelog (LTTng-UST),
  - User space time namespace context (LTTng-UST and LTTng-modules).

This release is named after "Nordicité", the product of a collaboration between
Champ Libre and Boréale. This farmhouse IPA is brewed with Kveik yeast and
Québec-grown barley, oats and juniper branches. The result is a remarkable
fruity hazy golden IPA that offers a balanced touch of resinous and woodsy
bitterness.

Based on the LTTng project's documented stable releases lifetime, this 2.13
release coincides with the end-of-life of the LTTng 2.11 release series.

Read on for a short description of each of the new features and the
links to this release.


Note on LTTng-UST backward compatibility
---

- soname major version change
  This release changes the LTTng-UST soname major from 0 to 1.

  The event notifier (triggers using an event-rule-matches condition)
  functionality required a significant rework of public data structures which
  should never have been made public in the first place.

  Bumping the soname major to 1, will require applications and tracepoint
  providers to be rebuilt against an updated LTTng-UST to use it.

  Old applications and tracepoint providers linked against libraries with
  major soname 0 should be able to co-exist on the same system.

- Building probe providers using a C++ compiler requires C++11

- API namespaceing
  The LTTng-UST API is now systematically namespaced under `lttng_ust_*` (e.g.
  `tracepoint()` becomes `lttng_ust_tracepoint()`).

  However, the non-namespaced names are still exposed to maintain API
  compatibility.


Event-rule matches condition and new actions
---

Expanding the trigger infrastructure and making it usable through the `lttng`
client was the core focus of this release.

A trigger is an association between a condition and one or more actions. When
the condition associated to a trigger is met, the actions associated to that
trigger are executed. The tracing does not have to be active for the conditions
to be met, and triggers are independent from tracing sessions.

Since their introduction as part of LTTng 2.10, new conditions and actions were
added to make this little-known mechanism more flexible.

For instance, before this release, triggers supported the following condition
types:
  - Buffer usage exceeded a given threshold,
  - Buffer usage went under a configurable threshold,
  - A session rotation occurred,
  - A session rotation completed.

A _notify_ action could be used to send a notification to a third party
applications whenever those conditions were met.

This made it possible, for instance, to disable certain event rules if the
tracing buffers were almost full. It could also be used to wait for session
rotations to be completed to start processing the resulting trace chunk
archives as part of various post-processing trace analyses.

This release introduces a new powerful condition type: event-rule matches.

This type of condition is met when the tracer encounters an event matching the
given even rule. The arguments describing the event rule are the same as those
describing the event rules of the `enable-event` command.

While this is not intended as a general replacement for the existing
high-throughput tracing facilities, this makes it possible for an application
to wait for a very-specific event to occur and take action whenever it occurs.
The purpose of event-rule matches triggers is to react quickly to an event
without the delay introduced by buffering.

For example, the following command will create a trigger that emits a
notification whenever the 'openat' system call is invoked with the
'/etc/passwd' filename argument.

```
$ lttng add-trigger
    --condition event-rule-matches
      --type=kernel:syscall
      --name='openat'
    --action notify
```

New actions were also introduced as part of this release:
  - **Start session**
    This action causes the LTTng session daemon to start tracing for the session
    with the given name. If no session with the given name exist at the time the
    condition is met, nothing is done.

  - **Stop session**
    This action causes the LTTng session daemon to stop tracing for the session
    with the given name. If no session with the given name exist at the time the
    condition is met, nothing is done.

  - **Rotate session**
    This action causes the LTTng session daemon to rotate the session with the
    given name. See `lttng-rotate(1)` for more information about the session
    rotation concept. If no session with the given name exist at the time the
    condition is met, nothing is done.

  - **Snapshot session**
    This action causes the LTTng session daemon to take a snapshot of the
    session with the given name. See `lttng-snapshot(1)` for more information
    about the session snapshot concept. If no session with the given name exist
    at the time the condition is met, nothing is done.

These new actions can also be combined together. For instance, the following
trigger will stop `my_session`, record a snapshot of `my_session`, and notify
any listening application when `/etc/passwd` is opened:

```
$ lttng add-trigger
    --condition event-rule-matches
      --type kernel:syscall
      --name 'openat'
      --filter 'filename == "/etc/passwd"'
    --action stop-session my_session
    --action snapshot-session my_session
    --action notify
```

For more information, see the following manual pages:
  - `lttng-add-trigger(1)`,
  - `lttng-remove-trigger(1)`,
  - `lttng-list-triggers(1)`.


Notification payload capture
---

The new event-rule matches condition type also allows 'captures'.
This allow event record and context fields to be captured when an event-rule
matches condition is satisfied.

The captured field values are made available in the evaluation object of the
notifications transmitted to listening applications.

Capture descriptors can be specified using a syntax reminiscent of the one used
by the filter expressions.

The following example will capture a process's name and the 'filename' argument
of all `openat()` system calls:

```
$ lttng add-trigger
    --condition event-rule-matches
      --type kernel:syscall
      --name 'openat'
      --capture 'filename'
      --capture '$ctx.procname'
    --action notify
```

See the `lttng-add-trigger(1)` manual page for more information.


vtracef and vtracelog (LTTng-UST)
---

New versions of the `tracef()` and `tracelog()` tracing helpers accepting
variable argument lists are introduced as `vtracef()` and `vtracelog()`.

See the `tracef(3)` and `tracelog(3)` manual pages for more information.


Add time namespace context (LTTng-UST and LTTng-modules)
---

It is now possible to add the time namespace of a process as a context to
channels (`time_ns`) using the `add-context` command.

See the `time_namespaces(7)` manual page for more information.
""",
        }
        super().__init__()

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        try:
            tokenized_version = series.split(".")
            if len(tokenized_version) != 2:
                return False
            if int(tokenized_version[0]) != 2:
                return False

            return True
        except:
            # Any error is the result of an unexpected release series format anyhow.
            return False

    def _update_version(self, new_version: Version) -> None:
        with open(self._repo_base_path + "/configure.ac", "r") as original:
            contents = original.read()
        exp = re.compile(r"AC_INIT.*")
        span = exp.search(contents).span()

        with open(self._repo_base_path + "/configure.ac", "w") as new:
            new.write(contents[0 : span[0]])
            new.write(
                "AC_INIT([lttng-tools],[{}],[jeremie.galarneau@efficios.com],[],[https://lttng.org])".format(
                    str(new_version)
                )
            )
            new.write(contents[span[1] :])

    def _get_tag_str(self, version: Version) -> str:
        return "v{}".format(str(version))

    def _commit_and_tag(self, new_version: Version, no_sign: bool) -> None:
        self._update_version(new_version)
        self._repo.git.add("ChangeLog", "configure.ac")

        tag = self._get_tag_str(new_version)
        commit_msg = "Update version to v{}".format(str(new_version))
        self._repo.git.commit("-s" if not no_sign else "", "-m" + commit_msg)
        self._repo.git.tag(
            "-s" if not no_sign else "",
            tag,
            "-m Version {}".format(str(new_version)),
        )
