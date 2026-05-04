from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx


async def fetch_robots_txt(client: httpx.AsyncClient, origin: str) -> Optional[str]:
    robots_url = urljoin(origin + "/", "robots.txt")
    try:
        r = await client.get(robots_url, follow_redirects=True)
        if r.status_code != 200:
            return None
        return r.text
    except httpx.HTTPError:
        return None


def build_robot_parser(robots_url: str, body: Optional[str]) -> Optional[RobotFileParser]:
    if body is None:
        return None
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(body.splitlines())
    return rp


def can_fetch(rp: Optional[RobotFileParser], user_agent: str, url: str) -> bool:
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)
