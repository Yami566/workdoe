from __future__ import annotations

import asyncio
from types import SimpleNamespace


class BodyStream:
    def __init__(self, chunks, *, stall=False):
        self.chunks = iter(chunks)
        self.stall = stall
        self.opened = False
        self.reads = 0
        self.canceled = False
        self.released = False

    def getReader(self):
        self.opened = True
        return self

    async def read(self):
        self.reads += 1
        if self.stall:
            await asyncio.Event().wait()
        chunk = next(self.chunks, None)
        if isinstance(chunk, OSError):
            raise chunk
        if chunk is None:
            return SimpleNamespace(done=True)
        return SimpleNamespace(done=False, value=SimpleNamespace(byteLength=len(chunk), to_py=lambda: chunk))

    async def cancel(self):
        self.canceled = True

    def releaseLock(self):
        self.released = True
