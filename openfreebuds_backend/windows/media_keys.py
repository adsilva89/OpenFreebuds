"""
Controle de mídia simples usando simulação de teclas e detecção de status
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

def is_music_playing():
    """
    Detecta se há música tocando usando PowerShell e Windows Media API
    Retorna True se alguma sessão de áudio está ativa
    """
    try:
        cmd = [
            'powershell', '-Command', 
            '''
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                
                [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
                class MMDeviceEnumerator { }
                
                [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IMMDeviceEnumerator {
                    int NotImpl1();
                    [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IntPtr ppDevice);
                }
                
                [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IMMDevice {
                    [PreserveSig] int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, out IntPtr ppInterface);
                }
                
                [Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IAudioSessionManager2 {
                    int NotImpl1();
                    int NotImpl2();
                    [PreserveSig] int GetSessionEnumerator(out IntPtr ppSessionEnum);
                }
                
                [Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IAudioSessionEnumerator {
                    [PreserveSig] int GetCount(out int SessionCount);
                    [PreserveSig] int GetSession(int SessionCount, out IntPtr ppSession);
                }
                
                [Guid("F4B1A599-7266-4319-A8CA-E70ACB11E8CD"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IAudioSessionControl {
                    [PreserveSig] int GetState(out int pRetVal);
                }
                
                public class AudioChecker {
                    public static bool IsAudioPlaying() {
                        try {
                            var enumerator = new MMDeviceEnumerator() as IMMDeviceEnumerator;
                            IntPtr device;
                            enumerator.GetDefaultAudioEndpoint(0, 0, out device);
                            
                            var deviceObj = Marshal.GetObjectForIUnknown(device) as IMMDevice;
                            var iid = new Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F");
                            IntPtr sessionManager;
                            deviceObj.Activate(ref iid, 0, IntPtr.Zero, out sessionManager);
                            
                            var sessionMgr = Marshal.GetObjectForIUnknown(sessionManager) as IAudioSessionManager2;
                            IntPtr sessionEnum;
                            sessionMgr.GetSessionEnumerator(out sessionEnum);
                            
                            var sessionEnumerator = Marshal.GetObjectForIUnknown(sessionEnum) as IAudioSessionEnumerator;
                            int sessionCount;
                            sessionEnumerator.GetCount(out sessionCount);
                            
                            for (int i = 0; i < sessionCount; i++) {
                                IntPtr session;
                                sessionEnumerator.GetSession(i, out session);
                                var sessionControl = Marshal.GetObjectForIUnknown(session) as IAudioSessionControl;
                                
                                int state;
                                sessionControl.GetState(out state);
                                if (state == 1) { // AudioSessionStateActive
                                    return true;
                                }
                            }
                            return false;
                        } catch {
                            return false;
                        }
                    }
                }
"@
            
            [AudioChecker]::IsAudioPlaying()
            '''
        ]
        
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            is_playing = result.stdout.strip().lower() == "true"
            log.debug(f"Status de reprodução detectado: {is_playing}")
            return is_playing
        else:
            log.warning(f"Erro ao detectar status de reprodução: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log.warning("Timeout ao detectar status de reprodução")
        return False
    except Exception as e:
        log.warning(f"Erro inesperado ao detectar status de reprodução: {e}")
        return False
