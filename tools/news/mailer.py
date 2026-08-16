"""Send one plain-text message, and get the credential from the Keychain.

The daily run is unattended, so the only way a failure reaches a human is a
message that leaves this machine. macOS ships `sendmail`, but postfix is not
running and is not configured to relay, so anything handed to it queues
locally forever — the appearance of a working alarm with none of the
substance. This talks SMTP directly instead.

**The password is never in this repository and never in a config file.** It
lives in the login Keychain, put there by hand with:

    security add-generic-password -a <account> -s global-nu-smtp -w

and read back here with `security find-generic-password -w`. That keeps the
secret in the one place macOS already protects, out of git, out of backups of
this directory, and out of any process listing — which `--password` on a
command line would not.
"""
from __future__ import annotations

import smtplib
import ssl
import subprocess
from email.message import EmailMessage

KEYCHAIN_SERVICE = "global-nu-smtp"


def build_message(subject: str, body: str, sender: str,
                  recipient: str) -> EmailMessage:
    """One plain-text message.

    Plain text on purpose: this is a machine writing to one person about a
    broken job, and an HTML part would add a way to render wrongly without
    adding anything to read.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    return msg


def keychain_password(account: str,
                      service: str = KEYCHAIN_SERVICE) -> str | None:
    """The SMTP password from the login Keychain, or None if it is not there.

    None rather than an exception: a missing credential must degrade the
    alarm, never stop the recovery attempt that matters more.
    """
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", account,
             "-s", service, "-w"],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    password = out.stdout.strip()
    return password or None


def send(msg: EmailMessage, host: str, port: int, account: str,
         password: str) -> None:
    """Deliver over STARTTLS. Raises on failure; the caller decides."""
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls(context=context)
        smtp.login(account, password)
        smtp.send_message(msg)
