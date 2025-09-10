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
        from openfreebuds_backend.windows.media_keys import pause_media, is_music_playing
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
        self._monitor_task: Optional[asyncio.Task] = None
        self.paused_players: list[MPRISPProxy] = []
        self.last_in_ear: bool = True
        self.music_playing_cache: bool = False  # Cache do status de música
        self.last_music_check: float = 0  # Timestamp da última verificação

    async def _trigger(self):
        in_ear = await self.ofb.get_property("state", "in_ear", "false") == "true"
        enabled = await self.ofb.get_property("config", "auto_pause", "false") == "true"

        if in_ear != self.last_in_ear and enabled:
            if self.last_in_ear is True and in_ear is False:
                # Fone removido - pausar mídia se estiver tocando
                if MEDIA_KEYS_AVAILABLE:
                    # Windows: usar cache do status de música
                    if self.music_playing_cache:
                        log.info("Fone removido - música tocando (cache), pausando")
                        pause_media()
                        self.paused_players = ["media_key_paused"]
                    else:
                        log.info("Fone removido - nenhuma música tocando (cache), nada a pausar")
                elif MPRISPProxy is not None:
                    # Linux: usar MPRIS
                    self.paused_players = []
                    for service in await MPRISPProxy.get_all():
                        if await service.playback_status() == "Playing":
                            log.info(f"Pause {await service.identity()}")
                            await service.pause()
                            self.paused_players.append(service)
                    
            elif self.last_in_ear is False and in_ear is True:
                # Fone colocado - retomar mídia se tínhamos pausado antes
                if self.paused_players:
                    if MEDIA_KEYS_AVAILABLE:
                        # Windows: usar cache do status de música
                        if not self.music_playing_cache:
                            log.info("Fone colocado - música pausada (cache), retomando")
                            pause_media()  # Play/Pause toggle
                        else:
                            log.info("Fone colocado - música já tocando (cache), não retomando")
                    elif MPRISPProxy is not None:
                        # Linux: usar MPRIS
                        for service in self.paused_players:
                            log.info(f"Resume {await service.identity()}")
                            await service.play()
                    self.paused_players = []
                
            self.last_in_ear = in_ear

    async def _monitor_music_status(self):
        """Monitor contínuo do status de música em background"""
        log.info("Iniciando monitor de status de música em background")
        
        while True:
            try:
                if MEDIA_KEYS_AVAILABLE:
                    # Atualizar cache do status de música a cada 2 segundos
                    import time
                    current_time = time.time()
                    
                    # Só verificar se passou tempo suficiente desde a última verificação
                    if current_time - self.last_music_check >= 2.0:
                        old_status = self.music_playing_cache
                        self.music_playing_cache = is_music_playing()
                        self.last_music_check = current_time
                        
                        # Log apenas quando o status muda
                        if old_status != self.music_playing_cache:
                            log.debug(f"Status de música mudou: {old_status} -> {self.music_playing_cache}")
                
                await asyncio.sleep(2)  # Verificar a cada 2 segundos
                
            except Exception as e:
                log.error(f"Erro no monitor de música: {e}")
                await asyncio.sleep(5)  # Esperar mais tempo em caso de erro

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
            
        if self._monitor_task is not None:
            with suppress(Exception):
                self._monitor_task.cancel()
                await self._monitor_task
            self._monitor_task = None

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
        
        # Iniciar monitor de música em background se estivermos no Windows
        if MEDIA_KEYS_AVAILABLE:
            self._monitor_task = asyncio.create_task(self._monitor_music_status())

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
