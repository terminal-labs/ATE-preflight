"""
ATE Preflight:

First draft of a Python script to check system prerequisites before installing
ATE. This was developed for testing RHEL 7. In order to support other Linux
varients, we'll have to look for any differences between how RHEL 7 reports things
like RAM (using `free`) or storage (using `df`) and accomodate them.

While we report Passed/FAILED for things like Docker version, number of cores, etc.,
we're currently just reporting whether or not the Python socket module thinks it's
open. Not even sure if this is the right approach or if it's necessary. But it's in
the prerequisite docs so we decided to have a go at it.
"""

import re
import socket
import sys

from texttable import Texttable  # Python objects to table-formatted strings

from utils import _run_sub

# Pre-compiled regexes

RE_NUMERIC = re.compile(r"\d+")
RE_SPACE = re.compile(r" +")
RE_VERSION = re.compile(r"(\d+\.)+\d+")

# Configure expectations

DOCKER_LOGGING = "json-file"
MIN_DOCKER = "17.04"
MIN_COMPOSE = "1.11.0"
MIN_CORES = 4
MIN_RAM = 8_000_000
MIN_STORAGE = 1_000_000_000
SELINUX_ENFORCEMENT = "Permissive"

# Docker methods

def docker_installed():
    """Simple validation that the `docker` command exists. This method will be used to
    kill the script immediately upon running if `docker` is not found."""
    cmd = "docker --help"
    try:
        _run_sub(cmd)
    except FileNotFoundError:
        return False
    return True


def docker_json():
    """Get the value for Docker's logging format'"""
    cmd = "docker info --format '{{.LoggingDriver}}'"
    response = _run_sub(cmd)
    return response["out"]


def docker_version():
    """Get Docker version"""
    cmd = "docker --version"
    response = _run_sub(cmd)
    version = _get_version(response["out"])
    return version


def docker_compose_version():
    """Get Docker Compose version"""
    cmd = "docker-compose --version"
    response = _run_sub(cmd)
    version = _get_version(response["out"])
    return version


# SELinux enforcement


def selinux_enforcement():
    """Get the value of `getenforce` for SELinux"""
    cmd = "getenforce"
    response = _run_sub(cmd)
    enforcement = response["out"]
    return enforcement


# Hardware methods


def hardware_cores():
    """Get the number of CPU cores in the system"""
    cmd = "grep -c ^processor /proc/cpuinfo"
    response = _run_sub(cmd)
    cores = int(response["out"])
    return cores


def hardware_ram():
    """Get total amount of RAM. This could be done in other ways that might be easier.
    But I chose to be explicit about working with the value that corresponds to 'total':

                  total        used        free      shared  buff/cache   available
    Mem:        8007488     2204612      223096      168612     5579780     5331372
    Swap:             0           0           0

    """
    cmd = "free"
    response = _run_sub(cmd)
    free = response["out"]
    free = free.replace("Mem:", "")
    free = [output.strip() for output in free.splitlines()]
    del free[-1]
    ram_dict = {
        k: int(v) for k, v in zip(RE_SPACE.split(free[0]), RE_SPACE.split(free[1]))
    }
    return int(ram_dict["total"])


def hardware_storage():
    """Get total storage"""
    cmd = "df"
    response = _run_sub(cmd)
    numeric = RE_NUMERIC.finditer(response["out"])
    storage = max(int(m.group()) for m in numeric)
    return storage


# Checking ports


def port_open(port):
    """Check if a given port appears to be open"""
    socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = ("127.0.0.1", port)
    check = socket_.connect_ex(location)
    return check


# "Private" utility methods


def _version_tuple(str_):
    """Convert version str into tuple of ints for comparison:
    1.2.3 to (1, 2, 3)
    (1, 2, 3) >= (1, 2, 2) >> True
    """
    return tuple(map(int, (str_.split("."))))


def _get_version(str_):
    """Attempt to parse a version string from subprocess output"""
    search = RE_VERSION.search(str_)
    if search:
        return search.group()
    else:
        return None


def _strip_strings(row):
    """Stripe whitespace from strings in a list"""
    for idx, value in enumerate(row):
        if isinstance(value, str):
            row[idx] = value.strip()
    return row


def _failures_plural(failures):
    if failures == 1:
        return "FAILURE"
    else:
        return "FAILURES"


def _gte(str_):
    """Prepend '>=' to a string representing a configured minimum expectation"""
    return f">= {str_}"


def _gb(num):
    """Express byte-based numbers as gigabytes"""
    gb = round(num / 1_000_000)
    return f"{gb:,}GB"


if __name__ == "__main__":
    failures = 0

    # Verify that `docker` command is available
    if not docker_installed():
        print(
            "ERROR: The Docker command is unavailable. ",
            "Ensure that Docker is installed on the system."
        )
        sys.exit(1)

    # Set up tabular data output
    table = Texttable()
    table.set_cols_dtype(["t", "t", "t", "t"])
    table.set_cols_align(["l", "r", "r", "l"])
    table.add_row(["Requirement", "Expected", "Actual", "Passed?"])

    # Docker logging is set to "json-file"
    json_ = docker_json()
    row = ["Docker logging", DOCKER_LOGGING, json_, None]
    if DOCKER_LOGGING in json_:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Docker version
    version = docker_version()
    a, b = _version_tuple(version), _version_tuple(MIN_DOCKER)
    row = ["Docker version", _gte(MIN_DOCKER), version, None]
    if a >= b:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Docker compose version
    version = docker_compose_version()
    a, b = _version_tuple(version), _version_tuple(MIN_COMPOSE)
    row = ["Compose version", _gte(MIN_COMPOSE), version, None]
    if a >= b:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # SELinux enforcement
    enforcement = selinux_enforcement()
    row = ["SELinux enforcement", SELINUX_ENFORCEMENT, enforcement, None]
    if SELINUX_ENFORCEMENT in enforcement:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Hardware: CPI cores
    cores = hardware_cores()
    row = ["Hardware: CPU cores", _gte(MIN_CORES), cores, None]
    if cores >= MIN_CORES:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Hardware: RAM
    ram = hardware_ram()
    row = ["Hardware: RAM", _gte(_gb(MIN_RAM)), _gb(ram), None]
    if ram >= MIN_RAM:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Hardware: Storage

    storage = hardware_storage()
    row = ["Hardware: Storage", _gte(_gb(MIN_STORAGE)), _gb(storage), None]
    if storage >= MIN_STORAGE:
        row[-1] = "Passed"
    else:
        row[-1] = "FAILED"
        failures += 1
    row = _strip_strings(row)
    table.add_row(row)

    # Output tabular data
    print()
    print(table.draw())

    if failures:
        print()
        print(f"{failures} {_failures_plural(failures)}")
        print("Please contact Anaconda sales...")
        print()

    # Port info
    ports = {
        "SSH": 22,
        "HTTP": 80,
        "HTTPS": 443,
    }

    print("=" * 24)
    print()
    print("Port Information:")
    print()

    # Set up tabular data output
    table = Texttable()
    table.set_cols_dtype(["t", "i", "t"])
    table.set_cols_align(["l", "r", "l"])

    for name, port in ports.items():
        row = [name, port, None]
        check = port_open(port)

        if check == 0:
            row[-1] = "Open"
        else:
            row[-1] = "Closed"
        row = _strip_strings(row)
        table.add_row(row)

    print(table.draw())
    print()
