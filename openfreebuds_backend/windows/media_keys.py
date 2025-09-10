"""
Controle de mídia simples usando simulação de teclas
"""

import subprocess
import logging

log = logging.getLogger("MediaKeys")

def send_media_key(vk_code=0xB3):
    """
    Envia uma tecla de mídia usando Windows API
    
    Args:
        vk_code: Código virtual da tecla (0xB3 = VK_MEDIA_PLAY_PAUSE)
    """
    try:
        # Usar keybd_event via PowerShell para enviar tecla de mídia
        cmd = [
            'powershell', '-Command', 
            f'''
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, uint dwExtraInfo);
                }}
"@
            [Win32]::keybd_event({vk_code}, 0, 0, 0)
            Start-Sleep -Milliseconds 50
            [Win32]::keybd_event({vk_code}, 0, 2, 0)
            '''
        ]
        
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            log.info(f"Tecla de mídia (VK_{vk_code:02X}) enviada com sucesso")
            return True
        else:
            log.error(f"Erro ao enviar tecla de mídia: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log.error(f"Timeout ao enviar tecla de mídia")
        return False
    except Exception as e:
        log.error(f"Erro inesperado ao enviar tecla de mídia: {e}")
        return False

def pause_media():
    """Pausa/retoma mídia usando tecla Play/Pause"""
    return send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE

def stop_media():
    """Para mídia usando tecla Stop"""
    return send_media_key(0xB2)  # VK_MEDIA_STOP

def next_track():
    """Próxima faixa"""
    return send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK

def previous_track():
    """Faixa anterior"""
    return send_media_key(0xB1)  # VK_MEDIA_PREV_TRACK
