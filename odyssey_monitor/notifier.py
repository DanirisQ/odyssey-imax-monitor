from __future__ import annotations

from email.message import EmailMessage
import html
import smtplib

from .config import Config
from .models import Showtime


def _subject(items: list[Showtime]) -> str:
    by_date: dict[str, list[str]] = {}
    for s in items:
        by_date.setdefault(s.show_date, []).append(s.start_time)
    bits = []
    for day, times in sorted(by_date.items()):
        short_day = day[5:].replace("-", "/")
        bits.append(f"{short_day} {'/'.join(sorted(times))}")
    suffix = "；".join(bits)
    return f"[MOViE MOViE] 奥德赛新增 IMAX 场次：{suffix}"


def _plain(items: list[Showtime], detected_at: str, cfg: Config) -> str:
    lines = [
        "MOViE MOViE 前滩太古里《奥德赛》发现新的 IMAX 场次。",
        "",
    ]
    for s in sorted(items, key=lambda x: (x.show_date, x.start_time)):
        lines.append(f"- {s.show_date} {s.start_time} | {s.hall or 'IMAX'} | {s.version or s.language}")
    lines += [
        "",
        f"首次抓取到这些场次的时间：{detected_at}",
        f"影院：{cfg.cinema_name}",
        f"猫眼影院页：{cfg.cinema_url}",
        "",
        "注：这是‘首次被监控程序看到’的时间，因此开票实际时间通常会早于它 0～一个轮询周期。",
    ]
    return "\n".join(lines)


def _html(items: list[Showtime], detected_at: str, cfg: Config) -> str:
    rows = "".join(
        "<tr>"
        f"<td style='padding:8px;border-bottom:1px solid #eee'>{html.escape(s.show_date)}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee'><b>{html.escape(s.start_time)}</b></td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee'>{html.escape(s.hall or 'IMAX')}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee'>{html.escape(s.version or s.language)}</td>"
        "</tr>"
        for s in sorted(items, key=lambda x: (x.show_date, x.start_time))
    )
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;line-height:1.55;color:#222">
      <h2 style="margin-bottom:8px">《奥德赛》新增 IMAX 场次</h2>
      <p style="margin-top:0">{html.escape(cfg.cinema_name)}</p>
      <table style="border-collapse:collapse;min-width:520px">
        <thead><tr><th style="text-align:left;padding:8px">日期</th><th style="text-align:left;padding:8px">时间</th><th style="text-align:left;padding:8px">影厅</th><th style="text-align:left;padding:8px">版本</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p><b>首次抓取时间：</b>{html.escape(detected_at)}</p>
      <p><a href="{html.escape(cfg.cinema_url)}">打开猫眼影院页</a></p>
      <p style="font-size:12px;color:#666">监控时间是程序第一次看到该排片的时间；实际开票可能早 0～一个轮询周期。</p>
    </div>
    """


def send_new_showtimes(items: list[Showtime], detected_at: str, cfg: Config) -> None:
    if not items:
        return
    if not cfg.email_ready:
        raise RuntimeError("Email settings are incomplete. Configure SMTP_* and EMAIL_* variables.")

    msg = EmailMessage()
    msg["Subject"] = _subject(items)
    msg["From"] = cfg.email_from
    msg["To"] = ", ".join(cfg.email_to)
    msg.set_content(_plain(items, detected_at, cfg))
    msg.add_alternative(_html(items, detected_at, cfg), subtype="html")

    if cfg.smtp_use_ssl:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
            server.login(cfg.smtp_user, cfg.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
            server.ehlo()
            if cfg.smtp_starttls:
                server.starttls()
                server.ehlo()
            server.login(cfg.smtp_user, cfg.smtp_password)
            server.send_message(msg)
