"""Control for inherited entrypoint wrapping; local probe only."""

from worker import Default as BaseProbe


class Default(BaseProbe):
    pass
