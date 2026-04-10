import argparse
import datetime as dt
import json
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
TEST_PRINT = PROJECT_DIR / "test_print.py"
PROFILES_DIR = PROJECT_DIR / "profiles"
LINUX_DRIVER_SRC_DIR = Path(
    "/home/tt18/Downloads/Star_CUPS_Driver-3.17.0_linux/SourceCode/Star_CUPS_Driver"
)
WINDOWS_CONFIG_DIR = Path("/home/tt18/Downloads/tsp100_v770/Windows/ConfigurationSettingFiles")
TSP100IIU_TIPS_DIR = Path(
    "/home/tt18/Downloads/Star_CUPS_Driver-3.17.0_linux/SourceCode/Star_CUPS_Driver/Tips/TSP100IIU"
)
TSP100IIU_PRESETS = {
    "backfeed-default": "1.BackFeed_default/BackFeed_default.dat",
    "backfeed-11mm": "2.BackFeed_11mm/BackFeed_11mm.dat",
    "backfeed-10mm": "3.BackFeed_10mm/BackFeed_10mm.dat",
    "backfeed-9mm": "4.BackFeed_9mm/BackFeed_9mm.dat",
    "backfeed-8mm": "5.BackFeed_8mm/BackFeed_8mm.dat",
    "backfeed-7mm": "6.BackFeed_7mm/BackFeed_7mm.dat",
    "backfeed-6mm": "7.BackFeed_6mm/BackFeed_6mm.dat",
    "backfeed-5mm": "8.BackFeed_5mm/BackFeed_5mm.dat",
    "backfeed-4mm": "9.BackFeed_4mm/BackFeed_4mm.dat",
    "backfeed-3mm": "10.BackFeed_3mm/BackFeed_3mm.dat",
    "compression-default": "11.Compression_default/Compression_default.dat",
    "compression-75": "12.Compression_75%/Compression_75%.dat",
    "compression-50": "13.Compression_50%/Compression_50%.dat",
}
MSW_THERMAL_LINUX_DAT = Path(
    "/home/tt18/Downloads/Star_CUPS_Driver-3.17.0_linux/SourceCode/Star_CUPS_Driver/Tips/MSW_Setting/ThermalPrinter/linux.dat"
)


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def cups_orientation(orientation: str) -> list[str]:
    if orientation == "portrait":
        return ["-o", "orientation-requested=3"]
    if orientation == "landscape":
        return ["-o", "orientation-requested=4"]
    return []


def require_cmd(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required command not found: {name}")
    return found


def current_lpoptions(printer: str) -> dict[str, str]:
    lpoptions = require_cmd("lpoptions")
    proc = run_cmd([lpoptions, "-p", printer], check=False)
    if proc.returncode != 0:
        return {}
    options: dict[str, str] = {}
    for token in proc.stdout.strip().split():
        if "=" in token:
            k, v = token.split("=", 1)
            options[k] = v
    return options


def send_raw_dat(printer: str, dat_path: Path) -> int:
    if not dat_path.exists():
        print(f"File not found: {dat_path}", file=sys.stderr)
        return 2
    lpr = shutil.which("lpr")
    lp = shutil.which("lp")
    if lpr:
        cmd = [lpr, "-o", "raw", "-P", printer, str(dat_path)]
    elif lp:
        cmd = [lp, "-d", printer, "-o", "raw", str(dat_path)]
    else:
        print("Required command not found: lp/lpr", file=sys.stderr)
        return 1
    proc = run_cmd(cmd, check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to send raw data", file=sys.stderr)
        return proc.returncode or 1
    print(proc.stdout.strip() or f"Sent raw data to '{printer}': {dat_path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    lpstat = require_cmd("lpstat")
    commands = [
        [lpstat, "-p", args.printer],
        [lpstat, "-d"],
        [lpstat, "-v"],
    ]
    for cmd in commands:
        proc = run_cmd(cmd, check=False)
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
    return 0


def cmd_queues(_: argparse.Namespace) -> int:
    lpstat = require_cmd("lpstat")
    proc = run_cmd([lpstat, "-p", "-d"], check=False)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    lpstat = require_cmd("lpstat")
    cmd = [lpstat, "-W", args.scope, "-o", args.printer]
    proc = run_cmd(cmd, check=False)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    else:
        print("(no jobs)")
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return 0


def cmd_list_options(args: argparse.Namespace) -> int:
    lpoptions = require_cmd("lpoptions")
    proc = run_cmd([lpoptions, "-p", args.printer, "-l"], check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to list options", file=sys.stderr)
        return proc.returncode or 1
    print(proc.stdout.strip())
    return 0


def cmd_set_options(args: argparse.Namespace) -> int:
    lpoptions = require_cmd("lpoptions")
    set_args = []
    for item in args.option:
        if "=" not in item:
            print(f"Invalid --option value (expected KEY=VALUE): {item}", file=sys.stderr)
            return 2
        set_args.extend(["-o", item])
    proc = run_cmd([lpoptions, "-p", args.printer] + set_args, check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to set options", file=sys.stderr)
        return proc.returncode or 1
    print(f"Updated options for printer '{args.printer}':")
    for item in args.option:
        print(f"  {item}")
    return 0


def cmd_set_default(args: argparse.Namespace) -> int:
    lpoptions = require_cmd("lpoptions")
    proc = run_cmd([lpoptions, "-d", args.printer], check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to set default printer", file=sys.stderr)
        return proc.returncode or 1
    print(f"Default printer set to: {args.printer}")
    return 0


def cmd_print_file(args: argparse.Namespace) -> int:
    lp = require_cmd("lp")
    path = Path(args.path).expanduser()
    if not path.exists() or not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    cmd = [lp, "-d", args.printer, "-n", str(args.copies)] + cups_orientation(args.orientation) + [str(path)]
    proc = run_cmd(cmd, check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to print file", file=sys.stderr)
        return proc.returncode or 1
    print(proc.stdout.strip() or f"Sent file to '{args.printer}': {path}")
    return 0


def cmd_print_text(args: argparse.Namespace) -> int:
    if not TEST_PRINT.exists():
        print(f"Missing print engine: {TEST_PRINT}", file=sys.stderr)
        return 2

    text = args.text
    if args.text_file:
        text_path = Path(args.text_file).expanduser()
        if not text_path.exists():
            print(f"Text file not found: {text_path}", file=sys.stderr)
            return 2
        text = text_path.read_text(encoding="utf-8")

    cmd = [
        sys.executable,
        str(TEST_PRINT),
        "--printer",
        args.printer,
        "--mode",
        args.mode,
        "--layout",
        args.layout,
        "--orientation",
        args.orientation,
        "--font-size",
        str(args.font_size),
        "--width-px",
        str(args.width_px),
        "--height-px",
        str(args.height_px),
        "--line-spacing",
        str(args.line_spacing),
        "--column-spacing",
        str(args.column_spacing),
        "--text",
        text,
    ]
    if args.font_path:
        cmd.extend(["--font-path", args.font_path])

    proc = run_cmd(cmd, check=False)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to print text", file=sys.stderr)
        return proc.returncode or 1
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = (
        "STAR PRINT TEST\n"
        f"{now}\n"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
        "0123456789\n"
        "おみくじ テスト\n"
        "大吉\n"
    )
    test_args = argparse.Namespace(
        printer=args.printer,
        mode=args.mode,
        layout=args.layout,
        orientation=args.orientation,
        font_size=args.font_size,
        width_px=args.width_px,
        height_px=args.height_px,
        line_spacing=args.line_spacing,
        column_spacing=args.column_spacing,
        text=payload,
        text_file=None,
        font_path=args.font_path,
    )
    return cmd_print_text(test_args)


def cmd_tsp100iiu_list(_: argparse.Namespace) -> int:
    print("TSP100IIU presets:")
    for key in TSP100IIU_PRESETS:
        print(f"  {key}")
    return 0


def cmd_tsp100iiu_apply(args: argparse.Namespace) -> int:
    preset_path = TSP100IIU_TIPS_DIR / TSP100IIU_PRESETS[args.preset]
    rc = send_raw_dat(args.printer, preset_path)
    if rc != 0:
        return rc
    print(f"Applied preset '{args.preset}' to '{args.printer}'")
    print("Power-cycle printer to ensure setting is reflected.")
    return 0


def cmd_msw_thermal_apply(args: argparse.Namespace) -> int:
    if args.dat_path:
        dat_path = Path(args.dat_path).expanduser()
    else:
        dat_path = MSW_THERMAL_LINUX_DAT
    rc = send_raw_dat(args.printer, dat_path)
    if rc == 0:
        print("Applied MSW thermal setting data. Verify with printer self-test if needed.")
    return rc


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []
    required_bins = ["lpstat", "lpoptions", "lp", "python3"]
    for name in required_bins:
        checks.append((f"command:{name}", shutil.which(name) is not None, shutil.which(name) or "missing"))

    checks.append(("test_print.py", TEST_PRINT.exists(), str(TEST_PRINT)))
    checks.append(("driver_source", LINUX_DRIVER_SRC_DIR.exists(), str(LINUX_DRIVER_SRC_DIR)))
    checks.append(("tsp100iiu_tips", TSP100IIU_TIPS_DIR.exists(), str(TSP100IIU_TIPS_DIR)))
    checks.append(("windows_config", WINDOWS_CONFIG_DIR.exists(), str(WINDOWS_CONFIG_DIR)))

    lpinfo = shutil.which("lpinfo")
    model_ok = False
    model_msg = "lpinfo missing"
    if lpinfo:
        proc = run_cmd([lpinfo, "-m"], check=False)
        if proc.returncode == 0 and "star/tsp143.ppd" in proc.stdout:
            model_ok = True
            model_msg = "star/tsp143.ppd found"
        elif proc.returncode == 0:
            model_msg = "star/tsp143.ppd not found"
        else:
            model_msg = proc.stderr.strip() or "lpinfo failed"
    checks.append(("cups_model", model_ok, model_msg))

    queue_ok = False
    queue_msg = ""
    lpstat = shutil.which("lpstat")
    if lpstat:
        proc = run_cmd([lpstat, "-p", args.printer], check=False)
        queue_ok = proc.returncode == 0 and f"printer {args.printer}" in proc.stdout
        queue_msg = proc.stdout.strip() or proc.stderr.strip()
    checks.append((f"queue:{args.printer}", queue_ok, queue_msg or "missing"))

    all_ok = True
    for name, ok, msg in checks:
        status = "OK" if ok else "NG"
        print(f"[{status}] {name} :: {msg}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("Doctor found issues. Fix NG items first.", file=sys.stderr)
        return 1
    return 0


def cmd_install_driver(args: argparse.Namespace) -> int:
    src_dir = Path(args.source_dir).expanduser()
    if not src_dir.exists():
        print(f"Source dir not found: {src_dir}", file=sys.stderr)
        return 2

    print(f"Using source dir: {src_dir}")
    steps = [
        ["make", "clean"],
        ["make"],
    ]
    for step in steps:
        proc = run_cmd(step, check=False) if src_dir == Path(".") else subprocess.run(
            step, cwd=src_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            print(proc.stdout.strip())
            print(proc.stderr.strip(), file=sys.stderr)
            return proc.returncode or 1
        if proc.stdout.strip():
            print(proc.stdout.strip())

    install_cmd = ["sudo", "make", "install"] if args.use_sudo else ["make", "install"]
    proc = subprocess.run(install_cmd, cwd=src_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(proc.stdout.strip())
        print(proc.stderr.strip(), file=sys.stderr)
        return proc.returncode or 1
    if proc.stdout.strip():
        print(proc.stdout.strip())
    print("Driver install finished.")
    return 0


def cmd_profile_list(_: argparse.Namespace) -> int:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(PROFILES_DIR.glob("*.json"))
    if not files:
        print("(no profiles)")
        return 0
    for fp in files:
        print(fp.name)
    return 0


def cmd_profile_save(args: argparse.Namespace) -> int:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILES_DIR / f"{args.name}.json"
    payload = {
        "printer": args.printer,
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        "lpoptions": current_lpoptions(args.printer),
        "print_defaults": {
            "mode": args.mode,
            "layout": args.layout,
            "orientation": args.orientation,
            "font_size": args.font_size,
            "width_px": args.width_px,
            "height_px": args.height_px,
            "line_spacing": args.line_spacing,
            "column_spacing": args.column_spacing,
            "font_path": args.font_path,
        },
    }
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved profile: {profile_path}")
    return 0


def cmd_profile_apply(args: argparse.Namespace) -> int:
    profile_path = PROFILES_DIR / f"{args.name}.json"
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}", file=sys.stderr)
        return 2
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    options = data.get("lpoptions", {})
    if not options:
        print("No lpoptions in profile.")
        return 0
    set_args = []
    for k, v in options.items():
        set_args.extend(["-o", f"{k}={v}"])
    lpoptions = require_cmd("lpoptions")
    proc = run_cmd([lpoptions, "-p", args.printer] + set_args, check=False)
    if proc.returncode != 0:
        print(proc.stderr.strip() or "Failed to apply profile", file=sys.stderr)
        return proc.returncode or 1
    print(f"Applied profile '{args.name}' to '{args.printer}'")
    return 0


def _xml_setting_text(elem: ET.Element, name: str) -> str | None:
    for s in elem.findall(".//setting"):
        if s.get("name") == name and s.text is not None:
            return s.text.strip()
    return None


def cmd_win_xml_summary(args: argparse.Namespace) -> int:
    xml_path = Path(args.path).expanduser()
    if not xml_path.exists():
        print(f"XML not found: {xml_path}", file=sys.stderr)
        return 2
    root = ET.fromstring(xml_path.read_text(encoding="utf-8", errors="ignore"))

    source_plugin = _xml_setting_text(root, "Source Emulator Plugin Path")
    target_plugin = _xml_setting_text(root, "Target Converter Plugin Path")
    model = _xml_setting_text(root, "Model")
    paper_width = _xml_setting_text(root, "Paper Width")
    etb = _xml_setting_text(root, "ETBSetting")
    cut_keys = 0
    delimiter_keys = 0
    for key in root.findall(".//Key0/..") + root.findall(".//CmdSubPP"):
        for item in key:
            if not item.tag.startswith("Key"):
                continue
            kt = _xml_setting_text(item, "Key Type")
            if kt == "Cut":
                cut_keys += 1
            if kt == "Delimiter":
                delimiter_keys += 1

    print(f"xml: {xml_path}")
    if source_plugin:
        print(f"  source_emulator: {source_plugin}")
    if target_plugin:
        print(f"  target_converter: {target_plugin}")
    if model:
        print(f"  model: {model}")
    if paper_width:
        print(f"  paper_width: {paper_width}")
    if etb:
        print(f"  etb_setting: {etb}")
    print(f"  cut_rules: {cut_keys}")
    print(f"  delimiter_rules: {delimiter_keys}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Star/CUPS utility for normal printer-like operations",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--printer", default="star", help="CUPS printer queue name")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="Show printer status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("queues", help="List printers and default queue")
    p.set_defaults(func=cmd_queues)

    p = sub.add_parser("jobs", help="List jobs for the printer")
    p.add_argument("--scope", choices=["all", "completed", "not-completed"], default="not-completed")
    p.set_defaults(func=cmd_jobs)

    p = sub.add_parser("list-options", help="List printer options")
    p.set_defaults(func=cmd_list_options)

    p = sub.add_parser("set-options", help="Set one or more printer options")
    p.add_argument("--option", action="append", required=True, help="KEY=VALUE (repeatable)")
    p.set_defaults(func=cmd_set_options)

    p = sub.add_parser("set-default", help="Set default CUPS printer")
    p.set_defaults(func=cmd_set_default)

    p = sub.add_parser("print-file", help="Print an existing file with CUPS")
    p.add_argument("path", help="Path to file")
    p.add_argument("--copies", type=int, default=1, help="Number of copies")
    p.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="portrait")
    p.set_defaults(func=cmd_print_file)

    p = sub.add_parser("print-text", help="Print raw/image text using test_print.py engine")
    p.add_argument("--text", default="OMIKUJI TEST\n", help="Text payload")
    p.add_argument("--text-file", help="Read text payload from UTF-8 file")
    p.add_argument("--mode", choices=["text", "image"], default="image")
    p.add_argument("--layout", choices=["horizontal", "vertical"], default="horizontal")
    p.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="portrait")
    p.add_argument("--font-path", default=None)
    p.add_argument("--font-size", type=int, default=30)
    p.add_argument("--width-px", type=int, default=576)
    p.add_argument("--height-px", type=int, default=1400)
    p.add_argument("--line-spacing", type=int, default=4)
    p.add_argument("--column-spacing", type=int, default=8)
    p.set_defaults(func=cmd_print_text)

    p = sub.add_parser("test", help="Print a built-in test page")
    p.add_argument("--mode", choices=["text", "image"], default="image")
    p.add_argument("--layout", choices=["horizontal", "vertical"], default="horizontal")
    p.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="portrait")
    p.add_argument("--font-path", default=None)
    p.add_argument("--font-size", type=int, default=30)
    p.add_argument("--width-px", type=int, default=576)
    p.add_argument("--height-px", type=int, default=1400)
    p.add_argument("--line-spacing", type=int, default=4)
    p.add_argument("--column-spacing", type=int, default=8)
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("tsp100iiu-list", help="List TSP100IIU utility presets")
    p.set_defaults(func=cmd_tsp100iiu_list)

    p = sub.add_parser("tsp100iiu-apply", help="Apply TSP100IIU backfeed/compression preset")
    p.add_argument("--preset", choices=sorted(TSP100IIU_PRESETS.keys()), required=True)
    p.set_defaults(func=cmd_tsp100iiu_apply)

    p = sub.add_parser("msw-thermal-apply", help="Apply official MSW thermal linux.dat in raw mode")
    p.add_argument("--dat-path", help="Override .dat path (default: official linux.dat)")
    p.set_defaults(func=cmd_msw_thermal_apply)

    p = sub.add_parser("doctor", help="Run Raspberry Pi readiness checks")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("install-driver", help="Build and install Star CUPS driver from source")
    p.add_argument("--source-dir", default=str(LINUX_DRIVER_SRC_DIR), help="Star driver source directory")
    p.add_argument("--use-sudo", action="store_true", help="Run install step with sudo")
    p.set_defaults(func=cmd_install_driver)

    p = sub.add_parser("profile-list", help="List saved profiles")
    p.set_defaults(func=cmd_profile_list)

    p = sub.add_parser("profile-save", help="Save current printer options and print defaults")
    p.add_argument("--name", required=True, help="Profile name")
    p.add_argument("--mode", choices=["text", "image"], default="image")
    p.add_argument("--layout", choices=["horizontal", "vertical"], default="horizontal")
    p.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="portrait")
    p.add_argument("--font-path", default=None)
    p.add_argument("--font-size", type=int, default=30)
    p.add_argument("--width-px", type=int, default=576)
    p.add_argument("--height-px", type=int, default=1400)
    p.add_argument("--line-spacing", type=int, default=4)
    p.add_argument("--column-spacing", type=int, default=8)
    p.set_defaults(func=cmd_profile_save)

    p = sub.add_parser("profile-apply", help="Apply saved profile lpoptions to a printer queue")
    p.add_argument("--name", required=True, help="Profile name")
    p.set_defaults(func=cmd_profile_apply)

    p = sub.add_parser("win-xml-summary", help="Summarize Windows config XML for cross-platform tuning")
    p.add_argument("path", help="Path to Windows config XML (escpos.xml/default config.xml)")
    p.set_defaults(func=cmd_win_xml_summary)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: command failed ({exc.returncode}): {shlex.join(exc.cmd)}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
