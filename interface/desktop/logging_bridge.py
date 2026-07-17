"""Pont entre le module logging standard et l'interface Qt (signal de log)."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class QtLogEmitter(QObject):
    """QObject exposant un signal Qt emis a chaque message de log."""

    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Handler logging qui relaie chaque message via un signal Qt.

    Permet d'afficher dans un panneau de l'interface les logs deja
    produits par le moteur (logging.getLogger dans core/, download/,
    processing/, database/), sans que ces modules n'aient a connaitre
    l'existence de l'interface.
    """

    def __init__(self, emitter: QtLogEmitter) -> None:
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        self._emitter.message.emit(self.format(record))
