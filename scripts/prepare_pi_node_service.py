"""Prepare, but do not install, the hardened enrolled Pi heartbeat service."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys


_SAFE_ABSOLUTE_PATH = re.compile(r"/[A-Za-z0-9_./-]+\Z")
_UNIT_TEMPLATE = """[Unit]
Description=AURA enrolled Pi node heartbeat
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=aura-node
Group=aura-node
WorkingDirectory={project_root}
EnvironmentFile={environment_file}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStartPre=/usr/bin/python3 {project_root}/scripts/check_pi_node_heartbeat_config.py
ExecStart=/usr/bin/python3 {project_root}/scripts/run_pi_node_heartbeat.py
Restart=on-failure
RestartSec=5s
CPUQuota=10%
MemoryMax=128M
TasksMax=16
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
"""
_ENVIRONMENT_TEMPLATE = """# Copy to {environment_file} only after replacing every value.
# Keep the installed file private to the aura-node service account (mode 0600).
AURA_SENSOR_NODE_ID=replace-with-enrolled-node-id
AURA_SENSOR_NODE_TOKEN=replace-with-one-time-enrollment-token
AURA_SENSOR_API_URL=https://aura-hub.example.net
AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS=30
"""


def _validate_systemd_path(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or _SAFE_ABSOLUTE_PATH.fullmatch(value) is None
        or ".." in Path(value).parts
    ):
        raise ValueError(f"{label} must be a simple absolute POSIX path")
    return value.rstrip("/") or "/"


def prepare_service_bundle(
    output_dir: Path,
    *,
    project_root: str = "/opt/aura-companion",
    environment_file: str = "/etc/aura/aura-node.env",
) -> tuple[Path, Path]:
    """Write deterministic deployment templates into a new private directory."""
    project_root = _validate_systemd_path(project_root, "Project root")
    environment_file = _validate_systemd_path(environment_file, "Environment file")
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise ValueError("Output directory cannot be a symlink")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("Output path must be a directory")
    created_output_dir = not output_dir.exists()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and output_dir.stat().st_mode & 0o077:
        raise ValueError("Existing output directory must be private (mode 0700)")
    unit_path = output_dir / "aura-pi-node-heartbeat.service"
    env_path = output_dir / "aura-node.env.example"
    if unit_path.exists() or env_path.exists() or unit_path.is_symlink() or env_path.is_symlink():
        raise FileExistsError("Refusing to replace an existing Pi service template")

    unit_data = _UNIT_TEMPLATE.format(
        project_root=project_root,
        environment_file=environment_file,
    )
    with unit_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(unit_data)
    with env_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_ENVIRONMENT_TEMPLATE.format(environment_file=environment_file))
    if os.name != "nt":
        unit_path.chmod(0o644)
        env_path.chmod(0o600)
        if created_output_dir:
            output_dir.chmod(0o700)
    return unit_path, env_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Pi heartbeat service templates without installing or enabling them."
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--project-root", default="/opt/aura-companion")
    parser.add_argument("--environment-file", default="/etc/aura/aura-node.env")
    args = parser.parse_args()
    try:
        unit, env_example = prepare_service_bundle(
            args.output_dir,
            project_root=args.project_root,
            environment_file=args.environment_file,
        )
    except (OSError, ValueError) as error:
        print(f"AURA_PI_SERVICE_PREPARE_ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Prepared service template: {unit}")
    print(f"Prepared placeholder configuration: {env_example}")
    print("No service account, environment file, node credential, or systemd state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
