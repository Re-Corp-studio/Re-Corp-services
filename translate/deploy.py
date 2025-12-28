#!/usr/bin/env python3
"""
PyInfra deployment script to install and configure the translate service on Arch Linux.
"""

from pyinfra.context import config
from pyinfra.operations import files, pacman, server, systemd

# Use sudo
config.SUDO = True

server.user(
    name="Create translate service user",
    user="translate",
    system=True,
    create_home=True,
)

for file in ["main.py", "requirements.txt", "service-account.json"]:
    files.put(
        name=f"Copy {file} to /opt/translate",
        src=file,
        dest=f"/opt/translate/{file}",
        user="translate",
        group="translate",
        mode="644",
    )

server.shell(
    name="Create Python virtualenv for translate service",
    commands=[
        "python3 -m venv /opt/translate/venv",
        "/opt/translate/venv/bin/pip install -r /opt/translate/requirements.txt",
    ],
    _sudo_user="translate",
)

files.put(
    name="Copy translate.service to /etc/systemd/system/translate.service",
    src="translate.service",
    dest="/etc/systemd/system/translate.service",
    user="root",
    group="root",
    mode="644",
)

files.directory(
    name="Create /var/lib/translate directory",
    path="/var/lib/translate",
    user="translate",
    group="translate",
    mode="755",
)

systemd.service(
    name="Enable and start translate service",
    service="translate.service",
    running=True,
    enabled=True,
    restarted=True,
)
