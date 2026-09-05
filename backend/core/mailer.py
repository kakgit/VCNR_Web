"""SMTP delivery for advertisement-sponsored movie gift emails."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from backend.core.config import Settings, get_settings

GIFT_QR_CID = "cinevault-gift-qr@cid"


def smtp_configured(settings: Settings | None = None) -> bool:
  """True when enough SMTP settings exist to attempt an email delivery."""
  config = settings or get_settings()
  return bool(config.smtp_host and config.smtp_from_email)


def send_email_message(
  *,
  to_email: str,
  subject: str,
  html_body: str,
  plain_body: str,
  attachments: list[tuple[str, bytes]] | None = None,
  inline_png: bytes | None = None,
  inline_cid: str | None = None,
) -> dict[str, object]:
  """Send an HTML + plain email with optional inline and attached PNG images.

  Returns ``{"sent": bool, "detail": str}``; never raises for expected mail
  failures so callers can surface a friendly message instead of a stack trace.
  """
  settings = get_settings()
  if not smtp_configured(settings):
    return {
      "sent": False,
      "detail": (
        "Email delivery is not configured on this server "
        "(set SMTP_HOST and SMTP_FROM_EMAIL)."
      ),
    }

  message = EmailMessage()
  message["Subject"] = subject
  message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
  message["To"] = to_email
  message["Message-ID"] = make_msgid(domain=settings.smtp_from_email.split("@")[-1] or "localhost")
  message.set_content(plain_body)
  message.add_alternative(html_body, subtype="html")

  if inline_png and inline_cid:
    # Inline copy referenced from the HTML body via <img src="cid:...">
    for part in message.iter_parts():
      if part.get_content_type() == "text/html":
        part.add_related(
          inline_png,
          maintype="image",
          subtype="png",
          cid=f"<{inline_cid}>",
        )
        break
  for attachment_name, attachment_png in attachments or []:
    # Downloadable copies for clients that block inline images.
    message.add_attachment(
      attachment_png,
      maintype="image",
      subtype="png",
      filename=attachment_name,
    )

  try:
    if settings.smtp_port == 465:
      with smtplib.SMTP_SSL(
        settings.smtp_host,
        settings.smtp_port,
        context=ssl.create_default_context(),
        timeout=20,
      ) as server:
        _login_if_configured(server, settings)
        server.send_message(message)
    else:
      with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.ehlo()
        if settings.smtp_use_tls:
          server.starttls(context=ssl.create_default_context())
          server.ehlo()
        _login_if_configured(server, settings)
        server.send_message(message)
    return {"sent": True, "detail": f"Email delivered to {to_email}."}
  except smtplib.SMTPAuthenticationError:
    return {"sent": False, "detail": "SMTP rejected the username/password (check SMTP_USERNAME/SMTP_PASSWORD)."}
  except smtplib.SMTPException as error:
    return {"sent": False, "detail": f"SMTP error: {error}"}
  except OSError as error:
    return {"sent": False, "detail": f"Could not reach the SMTP server: {error}"}


def send_advertisement_gift_email(
  *,
  to_email: str,
  subject: str,
  html_body: str,
  plain_body: str,
  qr_png: bytes | None = None,
  attachment_name: str = "cine-vault-movie-gift-qr.png",
) -> dict[str, object]:
  """Send the gift email with the QR inlined (CID) plus a PNG attachment."""
  attachments = [(attachment_name, qr_png)] if qr_png else None
  return send_email_message(
    to_email=to_email,
    subject=subject,
    html_body=html_body,
    plain_body=plain_body,
    attachments=attachments,
    inline_png=qr_png,
    inline_cid=GIFT_QR_CID,
  )


def _login_if_configured(server: smtplib.SMTP, settings: Settings) -> None:
  if settings.smtp_username and settings.smtp_password:
    server.login(settings.smtp_username, settings.smtp_password)


def build_gift_email_html(
  *,
  viewer_name: str,
  brand_name: str,
  brand_email: str,
  movie_title: str,
  qr_payload: str,
  frontend_origin: str,
) -> str:
  safe_viewer = viewer_name or "there"
  safe_brand = brand_name
  safe_movie = movie_title
  return f"""\
<html>
  <body style="margin:0;padding:24px;background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#1b2430;">
    <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px;border:1px solid #e3e8f0;">
      <p style="margin:0 0 16px;font-size:13px;letter-spacing:2px;text-transform:uppercase;color:#7a8699;">Cine Vault · Sponsored movie gift</p>
      <h1 style="margin:0 0 12px;font-size:22px;">Hi {safe_viewer}, a movie is waiting for you!</h1>
      <p style="margin:0 0 18px;line-height:1.55;">
        <strong>{safe_brand}</strong> is sponsoring <strong>{safe_movie}</strong> on Cine Vault
        and has sent you a movie gift code.
      </p>
      <div style="text-align:center;margin:0 0 18px;">
        <img alt="Movie gift QR code" src="cid:{GIFT_QR_CID}"
             style="width:260px;height:260px;border:1px solid #e3e8f0;border-radius:12px;padding:12px;" />
      </div>
      <ol style="margin:0 0 18px;padding-left:20px;line-height:1.7;">
        <li>Open your <strong>Cine Vault app</strong>.</li>
        <li>Use the QR scanner to scan this code.</li>
        <li>The movie <strong>{safe_movie}</strong> opens in your library, ready to watch.</li>
      </ol>
      <p style="margin:0 0 8px;font-size:12px;color:#7a8699;word-break:break-all;">
        Gift code payload: {qr_payload}
      </p>
      <p style="margin:0;font-size:12px;color:#7a8699;">
        Questions about this sponsorship? Contact the brand at {brand_email}.
      </p>
      <p style="margin:18px 0 0;font-size:12px;color:#98a3b3;text-align:center;">
        <a href="{frontend_origin}" style="color:#5b7cfa;">Cine Vault</a> · Enjoy the show 🍿
      </p>
    </div>
  </body>
</html>"""


def build_sponsor_passcode_list_email_html(
  *,
  brand_name: str,
  brand_email: str,
  movie_title: str,
  entries: list[dict[str, str]],
  frontend_origin: str,
) -> str:
  """Sponsor-facing email listing every generated QR ID passcode for sharing."""
  safe_brand = brand_name
  safe_movie = movie_title
  rows = "".join(
    "<tr>"
    f'<td style="padding:8px 10px;border-bottom:1px solid #e3e8f0;font-weight:700;white-space:nowrap;">#{index}</td>'
    f'<td style="padding:8px 10px;border-bottom:1px solid #e3e8f0;word-break:break-all;font-family:Consolas,Menlo,monospace;font-size:12px;">{entry["qr_payload"]}</td>'
    "</tr>"
    for index, entry in enumerate(entries, start=1)
  )
  return f"""\
<html>
  <body style="margin:0;padding:24px;background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#1b2430;">
    <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px;border:1px solid #e3e8f0;">
      <p style="margin:0 0 16px;font-size:13px;letter-spacing:2px;text-transform:uppercase;color:#7a8699;">Cine Vault · Sponsored show passcodes</p>
      <h1 style="margin:0 0 12px;font-size:22px;">{len(entries)} viewer passcode{"" if len(entries) == 1 else "s"} for "{safe_movie}"</h1>
      <p style="margin:0 0 18px;line-height:1.55;">
        <strong>{safe_brand}</strong> is sponsoring <strong>{safe_movie}</strong> on Cine Vault.
        Below are the QR ID passcodes for your {len(entries)} viewer{"" if len(entries) == 1 else "s"} —
        share one code per customer or client. Each viewer pastes the code in the movie page
        <strong>In-Branding</strong> box (or scans the attached QR) to receive the movie.
      </p>
      <table style="width:100%;border-collapse:collapse;margin:0 0 18px;">
        <thead>
          <tr>
            <th style="text-align:left;padding:8px 10px;background:#f4f6fb;border-bottom:2px solid #e3e8f0;font-size:12px;">#</th>
            <th style="text-align:left;padding:8px 10px;background:#f4f6fb;border-bottom:2px solid #e3e8f0;font-size:12px;">QR ID passcode</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin:0 0 8px;font-size:12px;color:#7a8699;">
        All QR images ({len(entries)}) are attached as PNG files, one per passcode.
      </p>
      <p style="margin:0;font-size:12px;color:#7a8699;">
        Questions about this sponsorship? Contact the Cine Vault team — brand contact: {brand_email}.
      </p>
      <p style="margin:18px 0 0;font-size:12px;color:#98a3b3;text-align:center;">
        <a href="{frontend_origin}" style="color:#5b7cfa;">Cine Vault</a> · Enjoy the show 🍿
      </p>
    </div>
  </body>
</html>"""
