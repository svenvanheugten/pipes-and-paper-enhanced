import asyncio
from time import sleep
from typing import Union, List
from dataclasses import dataclass
from enum import Enum
import functools
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from urllib.parse import unquote, urlsplit

import websockets.legacy.server

from src.connection import (SCREEN_DEVICE_PER_MODEL, get_remarkable_model,
                            get_screen_listener)
from src.screen_api import EventCodes, EventTypes, get_screen_input

# Only files below this directory are ever served.
PROJECT_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.pardir))


def websocket_payload(payload_type, message: List[Union[Enum, tuple]]):
    payload = {"type": payload_type}
    if isinstance(message, dict):
        payload["message"] = message
    elif not len(message):
        ...
    elif isinstance(message[0], Enum):
        payload["message"] = {
            m.name: m.value
            for m in message
        }
    return json.dumps(payload)


class Websocket(Thread):
    def __init__(self, ssh_hostname: str, port: int = 6789, address: str = "localhost") -> None:
        self.port = port
        self.address = address
        self.ssh_hostname = ssh_hostname
        super().__init__(daemon=True)

    def run(self):

        model = None
        while not model:
            try:
                model = get_remarkable_model(self.ssh_hostname)
            except Exception:
                print(
                    f"Can cannot connect to ReMarkable on {self.ssh_hostname}. Retrying..."
                )
                sleep(0.5)
        device = SCREEN_DEVICE_PER_MODEL[model]
        partial_handler = functools.partial(
            self.handler, model=model, device=device, ssh_hostname=self.ssh_hostname
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            websockets.legacy.server.serve(partial_handler, self.address, self.port)
        )
        print(
            f"Websocket ready and running on http://{self.address}:{self.port}")
        asyncio.get_event_loop().run_forever()

    async def handler(self, websocket, path, model, device, ssh_hostname):
        x = 0
        y = 0
        pressure = 0

        listener = await get_screen_listener(device, ssh_hostname)
        try:
            # Keep looping as long as the process is alive.
            # Terminated websocket connection is handled with a throw.
            while not listener.returncode:
                screen_input = await get_screen_input(model, listener)

                if not screen_input:
                    continue
                # It's sending coordinates
                elif screen_input.type == EventTypes.ABSOLUTE:
                    if screen_input.code == EventCodes.X:
                        x = screen_input.value
                    elif screen_input.code == EventCodes.Y:
                        y = screen_input.value
                    elif screen_input.code == EventCodes.PRESSURE:
                        pressure = screen_input.value
                    await websocket.send(websocket_payload("coordinates", {"x": x, "y": y, "pressure": pressure}))
                # It's sending tool used
                elif screen_input.type == EventTypes.KEY and screen_input.code in (EventCodes.ERASER, EventCodes.TIP):
                    await websocket.send(websocket_payload("tool", [screen_input.code]))
            print("Disconnected from ReMarkable.")
        finally:
            listener.kill()


class HttpHandler(SimpleHTTPRequestHandler):
    def resolve(self, path):
        """Turn a request path into a file path inside PROJECT_ROOT, or None."""
        candidate = os.path.realpath(
            os.path.join(PROJECT_ROOT, path.lstrip("/")))
        if candidate != PROJECT_ROOT and not candidate.startswith(PROJECT_ROOT + os.sep):
            print("REQUEST OUTSIDE OF THE PROJECT DIRECTORY: ", self.path)
            return None
        return candidate

    def do_GET(self):
        # The query string is not part of the file path.
        path = unquote(urlsplit(self.path).path)

        type = "text/html"
        # Switch on path
        if path == "/":
            path = "/index.html"
        elif path.startswith("/static/js/"):
            type = "text/javascript"
        elif path.startswith("/static/img/"):
            type = "image/svg+xml"
        else:
            print("UNRECONGIZED REQUEST: ", self.path)
            path = None

        file_path = self.resolve(path) if path else None

        content = None
        if file_path:
            try:
                with open(file_path, "rb") as file:
                    content = file.read()
            except OSError:
                print("CAN NOT READ: ", file_path)

        if content is None:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-type", type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)  # Send


def run_http_server(port: int, server_class=HTTPServer, handler_class=HttpHandler,
                    address: str = "localhost"):
    server_address = (address, port)
    httpd = server_class(server_address, handler_class)
    print(f"Serving http server on http://localhost:{port}")
    httpd.serve_forever()
