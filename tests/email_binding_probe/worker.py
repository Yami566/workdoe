"""Standalone local Email binding probe; no Workdoe application imports."""

import json
import os
import traceback
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint


def reply(value, status=200):
    return Response(
        json.dumps(value), status=status, headers={"Content-Type": "application/json"}
    )


def failure(stage, error):
    return reply(
        {
            "stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "frames": [
                {
                    "file": os.path.basename(frame.filename),
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(error.__traceback__)
            ],
        },
        500,
    )


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(str(request.url))
        if self.env.PROBE_MODE != "local-only" or url.hostname != "127.0.0.1":
            return reply({"stage": "refused"}, 404)
        if request.method == "GET" and url.path == "/health":
            return reply({"stage": "healthy"})
        if request.method != "POST" or url.path != "/probe":
            return reply({"stage": "refused"}, 404)
        try:
            email = self.env.EMAIL
        except AttributeError as error:
            return failure("binding-lookup", error)
        try:
            await email.send(
                {
                    "from": "sender@example.invalid",
                    "to": "mailbox@example.invalid",
                    "subject": "Local simulator probe",
                    "text": "Synthetic local-only content.",
                }
            )
        except Exception as error:  # noqa: BLE001 - diagnostic reports native JS send errors without a provider fallback.
            return failure("send", error)
        return reply({"stage": "send-accepted"})
