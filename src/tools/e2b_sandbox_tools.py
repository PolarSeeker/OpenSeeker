

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import tempfile
import urllib.error
import urllib.request
from dataclasses import replace
from urllib.parse import urlparse

from e2b import CommandResult
from e2b_code_interpreter import Sandbox

E2B_API_KEY = os.environ.get("E2B_API_KEY")
LOGS_DIR = os.environ.get("LOGS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "logs"))

DEFAULT_TEMPLATE_ID = "1av7fdjfvcparqo8efq6"
DEFAULT_TIMEOUT = 600
MAX_RESULT_LEN = 20_000
MAX_ERROR_LEN = 4_000

DEFAULT_CLI_DOWNLOAD_URL = "https://arxiv.org/pdf/2603.15594"
DEFAULT_CLI_RUN_COMMAND = "ls -R"
DEFAULT_CLI_PYTHON_CODE = """import math
lat1 = 32.82556
lon1 = -82.72444
lat2 = 34.991
lon2 = -83.785
lat1r = math.radians(lat1)
lat2r = math.radians(lat2)
lon1r = math.radians(lon1)
lon2r = math.radians(lon2)
R = 3958.8
Delta_lat = lat2r - lat1r
Delta_lon = lon2r - lon1r
a = math.sin(Delta_lat/2)**2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(Delta_lon/2)**2
c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
distance = R * c
print(distance)"""

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def _download_url_to_host_tempfile(url: str, suffix: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 OpenSeeker-e2b-tools/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL fetch failed: {e}") from e
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


INVALID_SANDBOX_IDS = {
    "default",
    "sandbox1",
    "sandbox",
    "some_id",
    "new_sandbox",
    "python",
    "create_sandbox",
    "sandbox123",
    "temp",
    "sandbox-0",
    "sandbox-1",
    "sandbox_0",
    "sandbox_1",
    "new",
    "0",
    "auto",
    "default_sandbox",
    "none",
    "sandbox_12345",
    "dummy",
    "sandbox_01",
}


def looks_like_dir(path: str) -> bool:
    if os.path.isdir(path):
        return True
    if path.endswith(os.path.sep) or not os.path.splitext(path)[1]:
        return True
    return False


def truncate_result(result: str) -> str:
    if len(result) > MAX_RESULT_LEN:
        return result[:MAX_RESULT_LEN] + " [Result truncated due to length limit]"
    return result


def format_command_result_text(result: CommandResult) -> str:
    """Normalize ``CommandResult`` text to match MCP examples (``error=None`` → ``error=''``)."""
    if result.error is None:
        result = replace(result, error="")
    return str(result)


def format_execution_text(execution) -> str:
    """Normalize Python cell result to stable ``Execution(...)`` line (parity with legacy tool-code-sandbox)."""
    return repr(execution)


def parse_sandbox_id(create_sandbox_message: str) -> str | None:
    """Parse sandbox id from successful `create_sandbox` return string."""
    if "[ERROR]" in create_sandbox_message:
        return None
    if "sandbox_id:" not in create_sandbox_message:
        return None
    return create_sandbox_message.split("sandbox_id:")[-1].strip()


def _print_tool_io(tool_name: str, payload: dict, output: str, ok: bool) -> None:
    status = f"{GREEN}OK{RESET}" if ok else f"{RED}ERROR{RESET}"
    print(f"\n{tool_name} input:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"{tool_name} output:")
    print(output)
    print(f"{tool_name} status: {status}")


def _is_error_output(output: str) -> bool:
    return "[ERROR]" in output or "Traceback" in output


def _run_command_ok(output: str) -> bool:
    return not _is_error_output(output) and "exit_code=0" in output and "error=''" in output


def _run_python_ok(output: str) -> bool:
    return not _is_error_output(output) and "Error: None" in output


def _upload_ok(output: str) -> bool:
    return not _is_error_output(output) and output.startswith("File uploaded to ")


def _download_ok(output: str) -> bool:
    return not _is_error_output(output) and output.startswith("File downloaded to ")


def _path_from_file_message(output: str, prefix: str) -> str | None:
    if output.startswith(prefix):
        return output.split(prefix, 1)[-1].strip()
    return None


def new_sandbox(timeout: int = DEFAULT_TIMEOUT) -> Sandbox:
    """Create an E2B Code Interpreter sandbox across old/new SDK versions."""
    create = getattr(Sandbox, "create", None)
    if callable(create):
        kwargs = {"timeout": timeout, "api_key": E2B_API_KEY}
        if DEFAULT_TEMPLATE_ID:
            kwargs["template"] = DEFAULT_TEMPLATE_ID
        try:
            return create(**kwargs)
        except TypeError as e:
            if "template" not in str(e):
                raise
            kwargs.pop("template", None)
            return create(**kwargs)

    kwargs = {"timeout": timeout, "api_key": E2B_API_KEY}
    if DEFAULT_TEMPLATE_ID:
        kwargs["template"] = DEFAULT_TEMPLATE_ID
    return Sandbox(**kwargs)


def get_sandbox_id(sandbox: Sandbox) -> str:
    """Return sandbox id for both legacy and current SDK object shapes."""
    sandbox_id = getattr(sandbox, "sandbox_id", None)
    if sandbox_id:
        return str(sandbox_id)
    info = sandbox.get_info()
    sandbox_id = getattr(info, "sandbox_id", None) or getattr(info, "id", None)
    if sandbox_id:
        return str(sandbox_id)
    raise RuntimeError("Could not read sandbox_id from E2B sandbox info.")


async def create_sandbox(timeout: int = DEFAULT_TIMEOUT) -> str:
    """Create a Linux sandbox (E2B). Returns message including ``sandbox_id`` or ``[ERROR]``."""
    if not E2B_API_KEY:
        return "[ERROR]: E2B_API_KEY is not set."
    max_retries = 5
    timeout = min(timeout, DEFAULT_TIMEOUT)
    for attempt in range(1, max_retries + 1):
        sandbox = None
        try:
            sandbox = new_sandbox(timeout=timeout)
            sandbox_id = get_sandbox_id(sandbox)
            tmpfiles_dir = os.path.join(LOGS_DIR, "tmpfiles")
            os.makedirs(tmpfiles_dir, exist_ok=True)
            return f"Sandbox created with sandbox_id: {sandbox_id}"
        except Exception as e:
            if attempt == max_retries:
                error_details = str(e)[:MAX_ERROR_LEN]
                return (
                    f"[ERROR]: Failed to create sandbox after {max_retries} attempts: "
                    f"{error_details}, please retry later."
                )
            await asyncio.sleep(attempt**2)
        finally:
            if sandbox is not None:
                try:
                    sandbox.set_timeout(timeout)
                except Exception:
                    pass
    return "[ERROR]: Unexpected create_sandbox failure."


async def run_command(command: str, sandbox_id: str) -> str:
    """Run a shell command in the sandbox; returns CommandResult string or error."""
    if not E2B_API_KEY:
        return "[ERROR]: E2B_API_KEY is not set."
    if sandbox_id in INVALID_SANDBOX_IDS:
        return (
            f"[ERROR]: '{sandbox_id}' is not a valid sandbox_id. "
            "Please create a real sandbox first using create_sandbox."
        )
    try:
        sandbox = Sandbox.connect(sandbox_id, api_key=E2B_API_KEY)
    except Exception:
        return (
            f"[ERROR]: Failed to connect to sandbox {sandbox_id}. "
            "Make sure the sandbox is created and the sandbox_id is correct."
        )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            sandbox.set_timeout(DEFAULT_TIMEOUT)
            result = sandbox.commands.run(command)
            return truncate_result(format_command_result_text(result))
        except Exception as e:
            if attempt == max_retries:
                error_details = str(e)[:MAX_ERROR_LEN]
                return (
                    f"[ERROR]: Failed to run command after {max_retries} attempts.\n\n"
                    f"Exception type: {type(e).__name__}\nDetails: {error_details}"
                )
            await asyncio.sleep(attempt**2)
        finally:
            try:
                sandbox.set_timeout(DEFAULT_TIMEOUT)
            except Exception:
                pass
    return "[ERROR]: Unexpected run_command failure."


async def run_python_code(code_block: str, sandbox_id: str) -> str:
    """Execute Python in the sandbox, or stateless one-off if sandbox_id is invalid/empty."""
    if not E2B_API_KEY:
        return "[ERROR]: E2B_API_KEY is not set."
    if not sandbox_id or sandbox_id in INVALID_SANDBOX_IDS:
        try:
            sandbox = new_sandbox(timeout=DEFAULT_TIMEOUT)
            try:
                execution = sandbox.run_code(code_block)
                return truncate_result(format_execution_text(execution))
            finally:
                sandbox.kill()
        except Exception as e:
            error_details = str(e)[:MAX_ERROR_LEN]
            return (
                f"[ERROR]: Failed to run code in stateless mode. "
                f"Exception type: {type(e).__name__}, Details: {error_details}"
            )

    try:
        sandbox = Sandbox.connect(sandbox_id, api_key=E2B_API_KEY)
    except Exception:
        return (
            f"[ERROR]: Failed to connect to sandbox {sandbox_id}. "
            "Make sure the sandbox is created and the sandbox_id is correct."
        )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            sandbox.set_timeout(DEFAULT_TIMEOUT)
            execution = sandbox.run_code(code_block)
            return truncate_result(format_execution_text(execution))
        except Exception as e:
            if attempt == max_retries:
                error_details = str(e)[:MAX_ERROR_LEN]
                return (
                    f"[ERROR]: Failed to run code in sandbox {sandbox_id} after {max_retries} attempts. "
                    f"Exception type: {type(e).__name__}, Details: {error_details}"
                )
            await asyncio.sleep(attempt**2)
        finally:
            try:
                sandbox.set_timeout(DEFAULT_TIMEOUT)
            except Exception:
                pass
    return "[ERROR]: Unexpected run_python_code failure."


async def upload_file_from_local_to_sandbox(
    sandbox_id: str,
    local_file_path: str,
    sandbox_file_path: str = ".",
) -> str:
    """Upload a local file; ``sandbox_file_path`` is remote dir or full file path (same as download)."""
    if not E2B_API_KEY:
        return "[ERROR]: E2B_API_KEY is not set."
    if sandbox_id in INVALID_SANDBOX_IDS:
        return (
            f"[ERROR]: '{sandbox_id}' is not a valid sandbox_id. "
            "Please create a real sandbox first using create_sandbox."
        )
    try:
        sandbox = Sandbox.connect(sandbox_id, api_key=E2B_API_KEY)
    except Exception:
        return (
            f"[ERROR]: Failed to connect to sandbox {sandbox_id}. "
            "Make sure the sandbox is created and the sandbox_id is correct."
        )

    try:
        sandbox.set_timeout(DEFAULT_TIMEOUT)
        if not os.path.exists(local_file_path):
            return f"[ERROR]: Local file does not exist: {local_file_path}"
        if not os.path.isfile(local_file_path):
            return f"[ERROR]: Path is not a file: {local_file_path}"

        local_base = os.path.basename(local_file_path)
        if looks_like_dir(sandbox_file_path):
            uploaded_file_path = os.path.normpath(
                os.path.join(sandbox_file_path, local_base)
            )
        else:
            uploaded_file_path = os.path.normpath(sandbox_file_path)

        parent_dir = os.path.dirname(uploaded_file_path)
        if parent_dir and parent_dir != "/":
            mkdir_result = sandbox.commands.run(f"mkdir -p {shlex.quote(parent_dir)}")
            if mkdir_result.exit_code != 0:
                mkdir_result_str = format_command_result_text(mkdir_result)[
                    :MAX_ERROR_LEN
                ]
                return (
                    f"[ERROR]: Failed to create directory {parent_dir} in sandbox "
                    f"{sandbox_id}: {mkdir_result_str}"
                )

        with open(local_file_path, "rb") as f:
            sandbox.files.write(uploaded_file_path, f)

        return f"File uploaded to {uploaded_file_path}"
    except Exception as e:
        error_details = str(e)[:MAX_ERROR_LEN]
        return f"[ERROR]: Failed to upload file {local_file_path} to sandbox {sandbox_id}: {error_details}"
    finally:
        try:
            sandbox.set_timeout(DEFAULT_TIMEOUT)
        except Exception:
            pass


async def download_file_from_internet_to_sandbox(
    sandbox_id: str,
    url: str,
    sandbox_file_path: str = ".",
) -> str:
    """Download a URL inside the sandbox using ``wget``."""
    if not E2B_API_KEY:
        return "[ERROR]: E2B_API_KEY is not set."
    if sandbox_id in INVALID_SANDBOX_IDS:
        return (
            f"[ERROR]: '{sandbox_id}' is not a valid sandbox_id. "
            "Please create a real sandbox first using create_sandbox."
        )
    try:
        sandbox = Sandbox.connect(sandbox_id, api_key=E2B_API_KEY)
    except Exception:
        return (
            f"[ERROR]: Failed to connect to sandbox {sandbox_id}. "
            "Make sure the sandbox is created and the sandbox_id is correct."
        )

    try:
        sandbox.set_timeout(DEFAULT_TIMEOUT)
        parsed_url = urlparse(url)
        basename = os.path.basename(parsed_url.path) or "downloaded_file"
        if "?" in basename:
            basename = basename.split("?")[0]
        if "#" in basename:
            basename = basename.split("#")[0]

        if looks_like_dir(sandbox_file_path):
            downloaded_file_path = os.path.join(sandbox_file_path, basename)
        else:
            downloaded_file_path = sandbox_file_path
        downloaded_file_path = os.path.normpath(downloaded_file_path)

        parent_dir = os.path.dirname(downloaded_file_path)
        if parent_dir and parent_dir != "/":
            mkdir_result = sandbox.commands.run(f"mkdir -p {shlex.quote(parent_dir)}")
            if mkdir_result.exit_code != 0:
                mkdir_result_str = format_command_result_text(mkdir_result)[
                    :MAX_ERROR_LEN
                ]
                return (
                    f"[ERROR]: Failed to create directory {parent_dir} in sandbox "
                    f"{sandbox_id}: {mkdir_result_str}"
                )

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            safe_url = shlex.quote(url)
            safe_path = shlex.quote(downloaded_file_path)
            cmd = f"wget {safe_url} -O {safe_path}"
            try:
                result = sandbox.commands.run(cmd)
                if result.exit_code == 0:
                    return f"File downloaded to {downloaded_file_path}"
                if attempt < max_retries:
                    await asyncio.sleep(4**attempt)
                    continue
                error_details = ""
                if hasattr(result, "stderr") and result.stderr:
                    error_details = f"stderr: {result.stderr}"[:MAX_ERROR_LEN]
                return (
                    f"[ERROR]: Failed to download file from {url} to {downloaded_file_path} "
                    f"after {max_retries} attempts.\n\nexit_code: {result.exit_code}\n\n"
                    f"Details: {error_details}"
                )
            except Exception as e:
                if attempt == max_retries:
                    error_details = str(e)[:MAX_ERROR_LEN]
                    return (
                        f"[ERROR]: Failed to download file from {url} to {downloaded_file_path}. "
                        f"Exception: {error_details}"
                    )
                await asyncio.sleep(4**attempt)
        return "[ERROR]: Unexpected download loop exit."
    except Exception as e:
        error_details = str(e)[:MAX_ERROR_LEN]
        return f"[ERROR]: Failed to download file from {url}: {error_details}"
    finally:
        try:
            sandbox.set_timeout(DEFAULT_TIMEOUT)
        except Exception:
            pass


def _run_unit_checks() -> None:
    assert looks_like_dir(os.path.join("some", "path", "noextension")) is True
    assert looks_like_dir(".") is True
    assert looks_like_dir("downloads/muniinc.xlsx") is False
    assert truncate_result("ab") == "ab"
    assert "truncated" in truncate_result("x" * (MAX_RESULT_LEN + 10)).lower()
    assert parse_sandbox_id("Sandbox created with sandbox_id: abc-123") == "abc-123"
    assert parse_sandbox_id("[ERROR]: x") is None
    normalized = format_command_result_text(
        CommandResult(stderr="", stdout=".\n", exit_code=0, error=None)
    )
    assert "error=''" in normalized
    assert "error=None" not in normalized
    print("unit checks: ok")


async def _integration_main_all(cli: argparse.Namespace) -> None:
    timeout = min(cli.timeout, DEFAULT_TIMEOUT)
    create_input = {"timeout": timeout}
    created = await create_sandbox(timeout=timeout)
    sid = parse_sandbox_id(created)
    _print_tool_io("create_sandbox", create_input, created, sid is not None)
    sid = parse_sandbox_id(created)
    if not sid:
        return

    command_input = {"sandbox_id": sid, "command": cli.command}
    out_cmd = await run_command(cli.command, sid)
    _print_tool_io("run_command", command_input, out_cmd, _run_command_ok(out_cmd))

    python_input = {"code_block": cli.code, "sandbox_id": sid}
    out_py = await run_python_code(cli.code, sid)
    _print_tool_io("run_python_code", python_input, out_py, _run_python_ok(out_py))

    upload_local = cli.local_file
    tmp_path: str | None = None
    tmp_fetched: str | None = None
    try:
        if upload_local:
            local_path = upload_local
        else:
            try:
                tmp_fetched = _download_url_to_host_tempfile(
                    DEFAULT_CLI_DOWNLOAD_URL, suffix="_2603.15594.pdf"
                )
                local_path = tmp_fetched
            except Exception as e:
                print(
                    f"[WARN]: Failed to prefetch {DEFAULT_CLI_DOWNLOAD_URL} for upload: {e}. "
                    "Falling back to a small temporary text file."
                )
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix="_e2b_upload_test.txt", delete=False
                ) as tmp:
                    tmp.write("upload probe\n")
                    tmp_path = tmp.name
                local_path = tmp_path

        upload_input = {
            "sandbox_id": sid,
            "local_file_path": local_path,
            "sandbox_file_path": cli.remote_path,
        }
        up = await upload_file_from_local_to_sandbox(sid, local_path, cli.remote_path)
        _print_tool_io("upload_file_from_local_to_sandbox", upload_input, up, _upload_ok(up))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if tmp_fetched:
            try:
                os.unlink(tmp_fetched)
            except OSError:
                pass

    download_input = {
        "sandbox_id": sid,
        "url": cli.url,
        "sandbox_file_path": cli.remote_path,
    }
    dl = await download_file_from_internet_to_sandbox(
        sid,
        cli.url,
        cli.remote_path,
    )
    _print_tool_io(
        "download_file_from_internet_to_sandbox",
        download_input,
        dl,
        _download_ok(dl),
    )
    downloaded_path = _path_from_file_message(dl, "File downloaded to ")
    if downloaded_path:
        preview_cmd = f"python3 - <<'PY'\nfrom pathlib import Path\np = Path({downloaded_path!r})\ndata = p.read_bytes()[:200]\nprint(data.decode('latin-1', errors='replace'))\nPY"
        preview = await run_command(preview_cmd, sid)
        _print_tool_io(
            "download_file_preview_first_200_chars",
            {"sandbox_id": sid, "command": preview_cmd},
            preview,
            _run_command_ok(preview),
        )


async def _integration_dispatch(cli: argparse.Namespace) -> None:
    timeout = min(cli.timeout, DEFAULT_TIMEOUT)

    async def ensure_sandbox_id() -> str | None:
        if cli.sandbox_id and cli.sandbox_id.strip():
            return cli.sandbox_id.strip()
        if cli.no_auto_sandbox:
            print(
                "[ERROR]: Pass --sandbox-id when reusing an existing sandbox, "
                "or remove --no-auto-sandbox to create one automatically."
            )
            return None
        created = await create_sandbox(timeout=timeout)
        sid = parse_sandbox_id(created)
        _print_tool_io("create_sandbox", {"timeout": timeout}, created, sid is not None)
        if not sid:
            print("[ERROR]: Could not parse sandbox_id from create_sandbox output.")
        return sid

    t = cli.tool
    if t == "all":
        await _integration_main_all(cli)
        return

    if t == "create_sandbox":
        msg = await create_sandbox(timeout=timeout)
        _print_tool_io("create_sandbox", {"timeout": timeout}, msg, parse_sandbox_id(msg) is not None)
        return

    if t == "run_command":
        sid = await ensure_sandbox_id()
        if not sid:
            return
        out = await run_command(cli.command, sid)
        _print_tool_io(
            "run_command",
            {"sandbox_id": sid, "command": cli.command},
            truncate_result(out),
            _run_command_ok(out),
        )
        return

    if t == "run_python_code":
        if cli.stateless_python:
            out = await run_python_code(cli.code, "")
            _print_tool_io(
                "run_python_code",
                {"code_block": cli.code, "sandbox_id": ""},
                truncate_result(out),
                _run_python_ok(out),
            )
            return
        sid = await ensure_sandbox_id()
        if not sid:
            return
        out = await run_python_code(cli.code, sid)
        _print_tool_io(
            "run_python_code",
            {"code_block": cli.code, "sandbox_id": sid},
            truncate_result(out),
            _run_python_ok(out),
        )
        return

    if t == "upload":
        if not cli.local_file:
            print("[ERROR]: upload requires --local-file.")
            return
        sid = await ensure_sandbox_id()
        if not sid:
            return
        out = await upload_file_from_local_to_sandbox(
            sid, cli.local_file, cli.remote_path
        )
        _print_tool_io(
            "upload_file_from_local_to_sandbox",
            {
                "sandbox_id": sid,
                "local_file_path": cli.local_file,
                "sandbox_file_path": cli.remote_path,
            },
            out,
            _upload_ok(out),
        )
        return

    if t == "download":
        sid = await ensure_sandbox_id()
        if not sid:
            return
        out = await download_file_from_internet_to_sandbox(
            sid, cli.url, cli.remote_path
        )
        _print_tool_io(
            "download_file_from_internet_to_sandbox",
            {"sandbox_id": sid, "url": cli.url, "sandbox_file_path": cli.remote_path},
            truncate_result(out[:800] if len(out) > 800 else out),
            _download_ok(out),
        )
        return

    print(f"[ERROR]: unknown --tool {t!r}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "E2B sandbox tool self-checks with Python async APIs and MiroFlow-compatible outputs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --unit-only
  %(prog)s --tool create_sandbox
  %(prog)s --tool run_command --sandbox-id '<existing-id>' --command 'uname -a'
  %(prog)s --tool run_command
  %(prog)s --tool run_python_code --code 'print(1+1)'
  %(prog)s --tool run_python_code --stateless-python --code 'print(2)'
  %(prog)s --tool upload --local-file ./2603.15594.pdf --remote-path .
  %(prog)s --tool download --url https://arxiv.org/pdf/2603.15594
  %(prog)s --tool all
""".rstrip(),
    )
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run local unit checks only without connecting to E2B.",
    )
    parser.add_argument(
        "--tool",
        "-t",
        choices=(
            "all",
            "create_sandbox",
            "run_command",
            "run_python_code",
            "upload",
            "download",
        ),
        default="all",
        help="Tool to run during integration checks; default runs the full flow.",
    )
    parser.add_argument(
        "--sandbox-id",
        default="",
        help="Existing sandbox_id; leave empty to create one automatically unless --no-auto-sandbox is set.",
    )
    parser.add_argument(
        "--no-auto-sandbox",
        action="store_true",
        help="Disable automatic sandbox creation and fail if --sandbox-id is missing.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"create_sandbox timeout in seconds, capped at {DEFAULT_TIMEOUT}.",
    )
    parser.add_argument(
        "--command",
        default=DEFAULT_CLI_RUN_COMMAND,
        help="Shell command used by run_command or all.",
    )
    parser.add_argument(
        "--code",
        default=DEFAULT_CLI_PYTHON_CODE,
        help="Python source string used by run_python_code or all.",
    )
    parser.add_argument(
        "--stateless-python",
        action="store_true",
        help="For run_python_code only: use a temporary sandbox and destroy it after execution.",
    )
    parser.add_argument(
        "--local-file",
        default="",
        help="Local file path for upload or all; all prefetches the default arXiv PDF when omitted.",
    )
    parser.add_argument(
        "--remote-path",
        default=".",
        help="Sandbox path for upload, download, or all; accepts a directory or full file path.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CLI_DOWNLOAD_URL,
        help="Download URL for download or all.",
    )
    args = parser.parse_args()
    if args.unit_only:
        _run_unit_checks()
        return
    if not os.environ.get("E2B_API_KEY"):
        print(
            "E2B_API_KEY not set: running --unit-only checks. "
            "Export E2B_API_KEY and re-run for full integration demo."
        )
        _run_unit_checks()
        return
    asyncio.run(_integration_dispatch(args))


if __name__ == "__main__":
    main()
