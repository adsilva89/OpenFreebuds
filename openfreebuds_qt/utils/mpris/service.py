import asyncio
from contextlib import suppress
from typing import Optional

from openfreebuds import IOpenFreebuds, OfbEventKind
from openfreebuds.utils.logger import create_logger
from openfreebuds_qt.config import OfbQtConfigParser
from openfreebuds_qt.utils import OfbCoreEvent

import platform

# Detectar plataforma e usar método apropriado
if platform.system() == "Windows":
    # Windows: usar teclas de mídia
    MPRISPProxy = None
    try:
        from openfreebuds_backend.windows.media_keys import pause_media
        MEDIA_KEYS_AVAILABLE = True
    except ImportError:
        MEDIA_KEYS_AVAILABLE = False
else:
    # Linux: usar MPRIS
    MEDIA_KEYS_AVAILABLE = False
    try:
        from openfreebuds_backend.linux.dbus.mpris import MPRISPProxy
    except ImportError:
        MPRISPProxy = None

log = create_logger("OfbQtMPRISHelperService")


class OfbQtMPRISHelperService:
    instance = None

    def __init__(self, ofb: IOpenFreebuds):
        self.ofb = ofb
        self.config = OfbQtConfigParser.get_instance()

        self._task: Optional[asyncio.Task] = None
        self.paused_players: list[MPRISPProxy] = []
        self.last_in_ear: bool = True
        self.first_connection: bool = True  # Flag para detectar primeira conexão

    async def _trigger(self):
        in_ear = await self.ofb.get_property("state", "in_ear", "false") == "true"
        enabled = await self.ofb.get_property("config", "auto_pause", "false") == "true"

        if in_ear != self.last_in_ear and enabled:
            if self.last_in_ear is True and in_ear is False:
                # Fone removido - pausar mídia (apenas se não for primeira conexão)
                if not self.first_connection:
                    log.info("Fone removido - pausando mídia")
                    if MEDIA_KEYS_AVAILABLE:
                        # Windows: usar teclas de mídia
                        pause_media()
                        self.paused_players = ["media_key_paused"]  # Marcar que pausamos via tecla
                    elif MPRISPProxy is not None:
                        # Linux: usar MPRIS
                        self.paused_players = []
                        for service in await MPRISPProxy.get_all():
                            if await service.playback_status() == "Playing":
                                log.info(f"Pause {await service.identity()}")
                                await service.pause()
                                self.paused_players.append(service)
                else:
                    log.info("Primeira conexão detectada - não pausando mídia")
                    
            elif self.last_in_ear is False and in_ear is True:
                # Fone colocado - retomar mídia (apenas se tínhamos pausado antes)
                if self.paused_players and not self.first_connection:
                    log.info("Fone colocado - retomando mídia")
                    if MEDIA_KEYS_AVAILABLE:
                        # Windows: usar teclas de mídia para retomar
                        pause_media()  # Play/Pause toggle
                    elif MPRISPProxy is not None:
                        # Linux: usar MPRIS
                        for service in self.paused_players:
                            log.info(f"Resume {await service.identity()}")
                            await service.play()
                    self.paused_players = []
                else:
                    log.info("Fone colocado (primeira vez ou sem mídia pausada)")
                    
            # Marcar que já não é mais a primeira conexão após qualquer mudança
            if self.first_connection:
                self.first_connection = False
                log.info("Primeira conexão concluída - controle automático ativado")
                
            self.last_in_ear = in_ear

    @staticmethod
    def get_instance(ofb: IOpenFreebuds):
        if OfbQtMPRISHelperService.instance is None:
            OfbQtMPRISHelperService.instance = OfbQtMPRISHelperService(ofb)
        return OfbQtMPRISHelperService.instance

    async def stop(self):
        if self._task is not None:
            with suppress(Exception):
                self._task.cancel()
                await self._task
            self._task = None

    async def start(self):
        await self.stop()
        if not self.config.get("mpris", "enabled", False):
            return

        # Verificar se temos algum método de controle disponível
        if MPRISPProxy is None and not MEDIA_KEYS_AVAILABLE:
            log.warning("Nenhum método de controle de mídia disponível")
            return
            
        log.info("Iniciando controle automático de mídia")
        self._task = asyncio.create_task(self._main())

    async def _main(self):
        log.info("Started")
        member_id = await self.ofb.subscribe(kind_filters=[OfbEventKind.PROPERTY_CHANGED])

        while True:
            try:
                event = OfbCoreEvent(*await self.ofb.wait_for_event(member_id))
                if event.is_changed("state", "in_ear"):
                    await self._trigger()
            except Exception:
                log.exception("Failure")
