import shlex
import subprocess


def _run_sub(cmd, *args, **kwargs):
    """Run shell commands via the subprocess module and return a dict with relevant info
    """
    cmd = shlex.split(cmd)
    if 'capture_output' not in kwargs:
        kwargs['capture_output'] = True
    output = subprocess.run(cmd, **kwargs)
    response = _sub_response(output)
    return response


def _sub_response(output):
    """Process the output from `subprocess.run`, mainly converting byte objects to
    strings and returning a simple dict with the relevant info we need from the output.
    """
    response = {
        "code": output.returncode,
        "out": output.stdout.decode(encoding="utf-8"),
        "err": output.stderr.decode(encoding="utf-8"),
        "out_raw": output.stdout,
        "err_raw": output.stderr,
    }
    return response
