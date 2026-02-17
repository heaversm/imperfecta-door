#!/usr/bin/env python3
"""Minimal WLED API client for local prototyping.

Usage examples:
  python wled_client.py --host 192.168.1.50 status
  python wled_client.py --host 192.168.1.50 on
  python wled_client.py --host 192.168.1.50 off
  python wled_client.py --host 192.168.1.50 color --rgb 255,120,20 --brightness 180
  python wled_client.py --host 192.168.1.50 preset --id 1
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Any

import requests


class WLEDClient:
    def __init__(self, host: str, timeout: float = 5.0) -> None:
        self.base = f"http://{host}"
        self.timeout = timeout

    def get_state(self) -> Dict[str, Any]:
        res = requests.get(f"{self.base}/json/state", timeout=self.timeout)
        res.raise_for_status()
        return res.json()

    def post_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        res = requests.post(
            f"{self.base}/json/state",
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        res.raise_for_status()
        return res.json()


def parse_rgb(value: str) -> list[int]:
    parts = value.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("RGB must be in r,g,b format")
    rgb = [int(x.strip()) for x in parts]
    if any(x < 0 or x > 255 for x in rgb):
        raise argparse.ArgumentTypeError("RGB values must be between 0 and 255")
    return rgb


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control WLED via HTTP JSON API")
    parser.add_argument("--host", required=True, help="WLED hostname or IP (e.g. 192.168.1.50)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Print current WLED state")
    subparsers.add_parser("on", help="Turn LEDs on")
    subparsers.add_parser("off", help="Turn LEDs off")

    p_preset = subparsers.add_parser("preset", help="Load a saved WLED preset")
    p_preset.add_argument("--id", type=int, required=True, help="Preset ID")

    p_color = subparsers.add_parser("color", help="Set solid color + optional brightness")
    p_color.add_argument("--rgb", type=parse_rgb, required=True, help="r,g,b (0-255)")
    p_color.add_argument("--brightness", type=int, default=180, help="1-255")

    p_bri = subparsers.add_parser("brightness", help="Set master brightness")
    p_bri.add_argument("--value", type=int, required=True, help="1-255")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = WLEDClient(args.host)

    try:
        if args.command == "status":
            state = client.get_state()
            print(json.dumps(state, indent=2))
            return 0

        if args.command == "on":
            state = client.post_state({"on": True})
            print(json.dumps({"ok": True, "on": state.get("on")}, indent=2))
            return 0

        if args.command == "off":
            state = client.post_state({"on": False})
            print(json.dumps({"ok": True, "on": state.get("on")}, indent=2))
            return 0

        if args.command == "preset":
            state = client.post_state({"ps": args.id})
            print(json.dumps({"ok": True, "preset": args.id, "on": state.get("on")}, indent=2))
            return 0

        if args.command == "color":
            bri = max(1, min(255, args.brightness))
            state = client.post_state(
                {
                    "on": True,
                    "bri": bri,
                    "seg": [{"id": 0, "col": [args.rgb, [0, 0, 0], [0, 0, 0]]}],
                }
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "rgb": args.rgb,
                        "brightness": bri,
                        "on": state.get("on"),
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "brightness":
            value = max(1, min(255, args.value))
            state = client.post_state({"bri": value, "on": True})
            print(json.dumps({"ok": True, "brightness": value, "on": state.get("on")}, indent=2))
            return 0

    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
