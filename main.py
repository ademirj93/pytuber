import pygame
import ctypes
import sys
import sounddevice as sd
import numpy as np
import random
import tkinter as tk
from tkinter import filedialog
from tkinter import colorchooser
from tkinter import messagebox
import time
import json
import os
import math
import shutil
import copy
import threading
import subprocess

try:
    import pyvirtualcam
    HAS_VIRTUALCAM = True
except ImportError:
    HAS_VIRTUALCAM = False

from updater import (
    APP_VERSION,
    resource_path,
    check_for_updates_async,
    download_update_async,
    launch_installer_and_exit,
    GLOBAL_UPDATE_INFO,
    UpdateStatus,
)

# --- Configurações Iniciais ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
GREEN_BACKGROUND = (0, 255, 0)
FPS = 60
SOUND_THRESHOLD = 0.1
CONFIG_FILE = 'config.json'

# --- Design System (Dark Mode Moderno) ---
class Theme:
    BG = (18, 18, 22)                 # #121216
    PANEL = (28, 28, 34)              # #1C1C22
    CARD_INNER = (24, 24, 30)         # #18181E
    BORDER = (42, 42, 50)             # #2A2A32
    BORDER_LIGHT = (60, 60, 72)       # #3C3C48
    BTN_NEUTRAL = (38, 38, 46)        # #26262E
    BTN_HOVER = (50, 50, 61)          # #32323D
    BTN_ACTIVE = (58, 58, 71)         # #3A3A47
    TEXT_PRIMARY = (243, 244, 246)    # #F3F4F6
    TEXT_SECONDARY = (156, 163, 175)  # #9CA3AF
    TEXT_MUTED = (107, 114, 128)      # #6B7280
    ACCENT = (99, 102, 241)           # #6366F1 (Indigo)
    ACCENT_HOVER = (79, 70, 229)      # #4F46E5
    ACCENT_GREEN = (16, 185, 129)     # #10B981 (Emerald)
    ACCENT_GREEN_HOVER = (5, 150, 105)
    ACCENT_GREEN_SOFT = (16, 185, 129, 35)
    DANGER = (239, 68, 68)            # #EF4444
    DANGER_BG = (55, 25, 25)
    WARNING = (245, 158, 11)          # #F59E0B
    WARNING_BG = (55, 45, 20)

# Cache de fontes para alta performance
FONT_CACHE = {}

def get_font(size, bold=False):
    if not pygame.font.get_init():
        pygame.font.init()
    key = (size, bold)
    if key not in FONT_CACHE:
        for name in ['segoeui', 'arial', 'calibri']:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                if f:
                    FONT_CACHE[key] = f
                    return f
            except Exception:
                pass
        FONT_CACHE[key] = pygame.font.SysFont(None, size, bold=bold)
    return FONT_CACHE[key]

# Cache de miniaturas de sprites
THUMBNAILS = {}

def get_thumbnail(path, size=(32, 32)):
    if not path or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        cache_key = (path, size, mtime)
        if cache_key in THUMBNAILS:
            return THUMBNAILS[cache_key]
        img = pygame.image.load(path).convert_alpha()
        w, h = img.get_size()
        scale = min(size[0] / max(1, w), size[1] / max(1, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        scaled_img = pygame.transform.smoothscale(img, (nw, nh))
        thumb_surf = pygame.Surface(size, pygame.SRCALPHA)
        thumb_surf.blit(scaled_img, ((size[0] - nw) // 2, (size[1] - nh) // 2))
        THUMBNAILS[cache_key] = thumb_surf
        return thumb_surf
    except Exception:
        return None

# --- Componentes Visuais Reutilizáveis ---

def draw_card(surface, rect, border_color=Theme.BORDER, bg_color=Theme.PANEL, radius=12, width=1):
    """Desenha um painel/card moderno com borda sutil e cantos arredondados."""
    pygame.draw.rect(surface, bg_color, rect, border_radius=radius)
    if border_color and width > 0:
        pygame.draw.rect(surface, border_color, rect, width=width, border_radius=radius)

def draw_toggle_switch(surface, rect, is_active, hover=False):
    """Desenha um toggle switch moderno estilo pill."""
    bg = Theme.ACCENT if is_active else Theme.BTN_NEUTRAL
    border = Theme.BORDER_LIGHT if hover else Theme.BORDER
    pygame.draw.rect(surface, bg, rect, border_radius=rect.height // 2)
    pygame.draw.rect(surface, border, rect, width=1, border_radius=rect.height // 2)
    
    pad = 3
    knob_diam = rect.height - pad * 2
    knob_y = rect.y + pad
    knob_x = (rect.right - pad - knob_diam) if is_active else (rect.x + pad)
    knob_rect = pygame.Rect(knob_x, knob_y, knob_diam, knob_diam)
    pygame.draw.ellipse(surface, (255, 255, 255), knob_rect)

def draw_icon_refresh(surface, center, radius, color):
    """Desenha um ícone vetorial de recarregar (↻)."""
    cx, cy = center
    arc_rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    pygame.draw.arc(surface, color, arc_rect, 0.6, 2 * math.pi - 0.4, 2)
    arrow_size = max(3, radius // 3)
    p1 = (cx + radius + 1, cy - 2)
    p2 = (cx + radius - arrow_size * 2, cy - 2)
    p3 = (cx + radius - arrow_size // 2, cy - arrow_size * 2)
    pygame.draw.polygon(surface, color, [p1, p2, p3])

def draw_icon_lock(surface, center, is_locked, color):
    """Desenha um ícone vetorial de cadeado moderno."""
    cx, cy = center
    body = pygame.Rect(cx - 7, cy - 3, 14, 11)
    pygame.draw.rect(surface, color, body, border_radius=2)
    shackle = pygame.Rect(cx - 4, cy - 9, 8, 8)
    if is_locked:
        pygame.draw.arc(surface, color, shackle, 0, math.pi, 2)
    else:
        pygame.draw.arc(surface, color, (cx - 4, cy - 11, 8, 8), math.pi * 0.3, math.pi * 1.3, 2)

def draw_badge(surface, x, y, text, text_color, bg_color, border_color=None, radius=6):
    """Desenha uma tag/badge arredondada."""
    font = get_font(12, bold=True)
    t_surf = font.render(text, True, text_color)
    w, h = t_surf.get_width() + 14, t_surf.get_height() + 6
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, bg_color, rect, border_radius=radius)
    if border_color:
        pygame.draw.rect(surface, border_color, rect, width=1, border_radius=radius)
    surface.blit(t_surf, (x + 7, y + 3))
    return rect

def draw_bootstrap_pencil(surface, center, size=14, color=Theme.TEXT_PRIMARY):
    """Desenha o ícone de lápis estilo Bootstrap Icons (bi-pencil-fill)."""
    cx, cy = center
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    body = [
        (3, size - 6),
        (size - 6, 3),
        (size - 3, 6),
        (6, size - 3)
    ]
    pygame.draw.polygon(surf, color, body)
    tip = [
        (3, size - 6),
        (6, size - 3),
        (1, size - 1)
    ]
    pygame.draw.polygon(surf, color, tip)
    cap = [
        (size - 6, 3),
        (size - 4, 1),
        (size - 1, 4),
        (size - 3, 6)
    ]
    pygame.draw.polygon(surf, color, cap)
    surface.blit(surf, (cx - size // 2, cy - size // 2))

def draw_bootstrap_trash(surface, center, size=14, color=Theme.DANGER):
    """Desenha o ícone de lixeira estilo Bootstrap Icons (bi-trash-fill)."""
    cx, cy = center
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (size // 2 - 2, 0, 4, 2), border_radius=1)
    pygame.draw.rect(surf, color, (1, 2, size - 2, 2), border_radius=1)
    body_rect = pygame.Rect(3, 4, size - 6, size - 5)
    pygame.draw.rect(surf, color, body_rect, border_bottom_left_radius=2, border_bottom_right_radius=2)
    slit_col = (20, 20, 24)
    pygame.draw.line(surf, slit_col, (size // 2 - 2, 6), (size // 2 - 2, size - 3), 1)
    pygame.draw.line(surf, slit_col, (size // 2 + 1, 6), (size // 2 + 1, size - 3), 1)
    surface.blit(surf, (cx - size // 2, cy - size // 2))

def draw_anchor_point(surface, center, color=(56, 189, 248), radius=10, label=None):
    """Desenha o Anchor Point (ponto de ancoragem) central no personagem base."""
    cx, cy = int(center[0]), int(center[1])
    pygame.draw.circle(surface, (0, 0, 0, 180), (cx, cy), radius + 2, width=3)
    pygame.draw.line(surface, (0, 0, 0, 180), (cx - radius - 5, cy), (cx + radius + 5, cy), 3)
    pygame.draw.line(surface, (0, 0, 0, 180), (cx, cy - radius - 5), (cx, cy + radius + 5), 3)
    pygame.draw.circle(surface, color, (cx, cy), radius, width=2)
    pygame.draw.line(surface, color, (cx - radius - 4, cy), (cx + radius + 4, cy), 1)
    pygame.draw.line(surface, color, (cx, cy - radius - 4), (cx, cy + radius + 4), 1)
    pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 3)
    if label:
        f = get_font(11, bold=True)
        lbl_surf = f.render(label, True, color)
        bg_rect = pygame.Rect(cx + radius + 6, cy - 9, lbl_surf.get_width() + 8, 18)
        draw_card(surface, bg_rect, border_color=color, bg_color=(18, 18, 22), radius=4)
        surface.blit(lbl_surf, (cx + radius + 10, cy - 8))

def get_wardrobe_item_rects(item_y):
    """Calcula os retângulos exatos e confortáveis dos botões de um item do guarda-roupa."""
    i_rect = pygame.Rect(20, item_y, 440, 44)
    sw_active = pygame.Rect(i_rect.x + 8, i_rect.y + 11, 40, 22)
    btn_lk = pygame.Rect(i_rect.x + 190, i_rect.y + 7, 30, 30)
    btn_ly = pygame.Rect(btn_lk.right + 6, i_rect.y + 7, 38, 30)
    btn_up = pygame.Rect(btn_ly.right + 6, i_rect.y + 7, 28, 30)
    btn_dn = pygame.Rect(btn_up.right + 4, i_rect.y + 7, 28, 30)
    btn_ed = pygame.Rect(btn_dn.right + 8, i_rect.y + 7, 32, 30)
    btn_rm = pygame.Rect(btn_ed.right + 6, i_rect.y + 7, 32, 30)
    return {
        'card': i_rect,
        'active': sw_active,
        'lock': btn_lk,
        'layer': btn_ly,
        'up': btn_up,
        'down': btn_dn,
        'edit': btn_ed,
        'delete': btn_rm
    }

# --- Configurações de Arquivo ---

def load_config():
    """Tenta carregar as configurações de um arquivo salvo."""
    defaults = {
        "paths": {"char": None, "eyes_open": None, "eyes_closed": None, "mouth_open": None},
        "offsets": {"char": [0, 0], "eyes": [0, 0], "mouth": [0, 0]},
        "audio_device": None,
        "sound_threshold": 0.1,
        "bg_color": [0, 255, 0],
        "transparent_window": False,
        "borderless_window": False,
        "animations_enabled": True,
        "fps_limit": 60,
        "wardrobe": [],
        "char_scale": 1.0,
        "hard_edges": False,
        "virtual_camera": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for k, v in defaults.items():
                    if k == 'offsets':
                        config.setdefault('offsets', copy.deepcopy(v))
                        for part in v:
                            config['offsets'].setdefault(part, v[part])
                    elif k == 'paths':
                        config.setdefault('paths', copy.deepcopy(v))
                    else:
                        config.setdefault(k, v)
                return config
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Erro ao ler o arquivo de configuração, usando padrões: {e}")
            return defaults
    return defaults

def save_config(config):
    """Salva as configurações em um arquivo."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")

def import_image_to_assets(source_path, subfolder):
    """Copia a imagem selecionada para a pasta assets e retorna o novo caminho."""
    if not source_path or not os.path.exists(source_path):
        return source_path
        
    assets_dir = os.path.join("assets", subfolder)
    os.makedirs(assets_dir, exist_ok=True)
    
    filename = os.path.basename(source_path)
    dest_path = os.path.join(assets_dir, filename)
    
    if os.path.abspath(source_path) != os.path.abspath(dest_path):
        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            print(f"Erro ao copiar imagem para assets: {e}")
            return source_path
            
    return dest_path

# --- Estado do Personagem ---
is_speaking = False
is_blinking = False
last_blink_time = 0
next_blink_interval = random.uniform(2, 6)
current_volume = 0.0
audio_stream = None

def audio_callback(indata, frames, time_info, status):
    """Callback para processar o áudio do microfone."""
    global is_speaking, current_volume
    volume_norm = float(np.linalg.norm(indata) * 10)
    current_volume = volume_norm
    if volume_norm > SOUND_THRESHOLD:
        is_speaking = True
    else:
        is_speaking = False

def start_audio_stream(device_index=None):
    """Inicia a captura de áudio com o dispositivo especificado."""
    global audio_stream
    if audio_stream is not None:
        try:
            audio_stream.stop()
            audio_stream.close()
        except Exception as e:
            print(f"Erro ao fechar stream de áudio anterior: {e}")
    try:
        audio_stream = sd.InputStream(device=device_index, callback=audio_callback)
        audio_stream.start()
    except Exception as e:
        print(f"Erro ao abrir stream de áudio: {e}")

def get_input_devices():
    """Verifica e retorna uma lista de dispositivos de entrada de áudio."""
    try:
        devices = sd.query_devices()
        input_devices = []
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                try:
                    api_name = sd.query_hostapis(d['hostapi'])['name']
                    d['display_name'] = f"{d['name']} [{api_name}]"
                except Exception:
                    d['display_name'] = d['name']
                input_devices.append((i, d))
        return input_devices
    except Exception as e:
        print(f"Erro ao listar dispositivos de áudio: {e}")
        return []

def set_window_transparency(color, enable):
    """Aplica transparência à janela no Windows baseada na cor de fundo."""
    if sys.platform == 'win32':
        try:
            hwnd = pygame.display.get_wm_info()["window"]
            WS_EX_LAYERED = 0x00080000
            GWL_EXSTYLE = -20
            LWA_COLORKEY = 0x00000001
            
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enable:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
                color_ref = color[0] | (color[1] << 8) | (color[2] << 16)
                ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_ref, 0, LWA_COLORKEY)
            else:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        except Exception as e:
            print(f"Erro ao definir transparência da janela: {e}")

def check_global_hotkeys():
    """Verifica atalhos globais no Windows usando ctypes."""
    if sys.platform == 'win32':
        ctrl_pressed = ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000 != 0
        b_pressed = ctypes.windll.user32.GetAsyncKeyState(0x42) & 0x8000 != 0
        m_pressed = ctypes.windll.user32.GetAsyncKeyState(0x4D) & 0x8000 != 0
        p_pressed = ctypes.windll.user32.GetAsyncKeyState(0x50) & 0x8000 != 0
        return (ctrl_pressed and b_pressed), (ctrl_pressed and m_pressed), (ctrl_pressed and p_pressed)
    return False, False, False

def get_default_layer(category):
    """Retorna a camada padrão baseada na categoria do item."""
    if category in ["calças", "camisas", "casacos"]:
        return 'trás'
    elif category == "maquiagem":
        return 'meio'
    return 'frente'

def edit_wardrobe_item_dialog(item=None):
    """Abre um formulário moderno para adicionar ou editar um item do guarda-roupa."""
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("Configurar Acessório • Guarda-Roupa")
    dialog.attributes('-topmost', True)
    dialog.geometry("460x520")
    dialog.configure(bg='#1C1C22')
    dialog.resizable(False, False)
    
    result = None
    
    # Header do diálogo
    hdr_frame = tk.Frame(dialog, bg='#18181E', height=45)
    hdr_frame.pack(fill='x', side='top')
    hdr_title = "Editar Acessório" if item else "Novo Acessório"
    tk.Label(hdr_frame, text=hdr_title, font=('Segoe UI', 12, 'bold'), bg='#18181E', fg='#F3F4F6').pack(side='left', padx=16, pady=10)
    
    body = tk.Frame(dialog, bg='#1C1C22')
    body.pack(fill='both', expand=True, padx=20, pady=12)
    
    # 1. Nome
    tk.Label(body, text="Nome do Item:", font=('Segoe UI', 9, 'bold'), bg='#1C1C22', fg='#9CA3AF').pack(anchor='w', pady=(4, 2))
    name_var = tk.StringVar(value=item['name'] if item else "")
    ent_name = tk.Entry(body, textvariable=name_var, bg='#26262E', fg='#F3F4F6', insertbackground='white', relief='flat', font=('Segoe UI', 10), bd=5)
    ent_name.pack(fill='x', pady=(0, 8))
    
    # 2. Categoria
    tk.Label(body, text="Categoria:", font=('Segoe UI', 9, 'bold'), bg='#1C1C22', fg='#9CA3AF').pack(anchor='w', pady=(4, 2))
    categories = ["chapéus", "acessórios", "maquiagem", "calças", "casacos", "camisas", "objetos_de_cena", "cor_dos_olhos"]
    cat_var = tk.StringVar(value=item['category'] if item else categories[0])
    opt_cat = tk.OptionMenu(body, cat_var, *categories)
    opt_cat.config(bg='#26262E', fg='#F3F4F6', activebackground='#32323D', activeforeground='#F3F4F6', relief='flat', font=('Segoe UI', 9), bd=0, highlightthickness=0)
    opt_cat['menu'].config(bg='#26262E', fg='#F3F4F6', activebackground='#6366F1', font=('Segoe UI', 9))
    opt_cat.pack(fill='x', pady=(0, 8))
    
    # 3. Camada
    tk.Label(body, text="Camada de Renderização:", font=('Segoe UI', 9, 'bold'), bg='#1C1C22', fg='#9CA3AF').pack(anchor='w', pady=(4, 2))
    cat_val = item.get('category') if item else categories[0]
    default_layer = get_default_layer(cat_val)
    layer_var = tk.StringVar(value=item.get('layer', default_layer) if item else default_layer)
    opt_layer = tk.OptionMenu(body, layer_var, "frente", "meio", "trás")
    opt_layer.config(bg='#26262E', fg='#F3F4F6', activebackground='#32323D', activeforeground='#F3F4F6', relief='flat', font=('Segoe UI', 9), bd=0, highlightthickness=0)
    opt_layer['menu'].config(bg='#26262E', fg='#F3F4F6', activebackground='#6366F1', font=('Segoe UI', 9))
    opt_layer.pack(fill='x', pady=(0, 8))

    # 4. Escala / Tamanho Inicial
    init_scale = item.get('scale', 1.0) if item else 1.0
    scale_label_var = tk.StringVar(value=f"Tamanho (Escala): {init_scale:.2f}x")
    tk.Label(body, textvariable=scale_label_var, font=('Segoe UI', 9, 'bold'), bg='#1C1C22', fg='#9CA3AF').pack(anchor='w', pady=(4, 2))
    
    scale_var = tk.DoubleVar(value=init_scale)
    
    def on_scale_change(val):
        try:
            scale_label_var.set(f"Tamanho (Escala): {float(val):.2f}x")
        except Exception:
            pass
            
    scale_slider = tk.Scale(body, from_=0.10, to=3.00, resolution=0.05, orient='horizontal', variable=scale_var, command=on_scale_change, bg='#1C1C22', fg='#F3F4F6', highlightthickness=0, troughcolor='#26262E', activebackground='#10B981', bd=0, showvalue=False)
    scale_slider.pack(fill='x', pady=(0, 8))

    # 5. Imagem PNG
    tk.Label(body, text="Arquivo de Imagem (PNG):", font=('Segoe UI', 9, 'bold'), bg='#1C1C22', fg='#9CA3AF').pack(anchor='w', pady=(4, 2))
    path_var = tk.StringVar(value=item['path'] if item else "")
    
    file_frame = tk.Frame(body, bg='#1C1C22')
    file_frame.pack(fill='x', pady=(0, 10))
    
    def choose_file():
        p = filedialog.askopenfilename(title="Selecione a Imagem PNG", filetypes=[("Imagens PNG", "*.png")])
        if p:
            path_var.set(p)
            path_lbl.config(text=os.path.basename(p))
            
    btn_file = tk.Button(file_frame, text="Escolher PNG...", command=choose_file, bg='#26262E', fg='#F3F4F6', activebackground='#32323D', activeforeground='#F3F4F6', relief='flat', font=('Segoe UI', 9), bd=4)
    btn_file.pack(side='left')
    
    disp_path = os.path.basename(path_var.get()) if path_var.get() else "Nenhuma imagem selecionada"
    path_lbl = tk.Label(file_frame, text=disp_path, font=('Segoe UI', 9), bg='#1C1C22', fg='#38BDF8', wraplength=280)
    path_lbl.pack(side='left', padx=10)

    # 6. Botões Salvar e Cancelar
    btn_frame = tk.Frame(dialog, bg='#18181E', height=50)
    btn_frame.pack(fill='x', side='bottom')
    
    def cancel():
        dialog.destroy()
        
    def save():
        nonlocal result
        if not name_var.get() or not path_var.get():
            return
        final_path = import_image_to_assets(path_var.get(), cat_var.get())
        result = {
            'name': name_var.get(),
            'category': cat_var.get(),
            'layer': layer_var.get(),
            'path': final_path,
            'offset': item.get('offset', [0, 0]) if item else [0, 0],
            'scale': round(scale_var.get(), 2),
            'active': item.get('active', True) if item else True,
            'id': item['id'] if item else str(time.time()),
            'locked': item.get('locked', False) if item else False
        }
        dialog.destroy()
        
    btn_save = tk.Button(btn_frame, text="Salvar Acessório", command=save, bg='#10B981', fg='white', activebackground='#059669', activeforeground='white', relief='flat', font=('Segoe UI', 10, 'bold'), bd=5, padx=12)
    btn_save.pack(side='right', padx=16, pady=10)
    
    btn_cancel = tk.Button(btn_frame, text="Cancelar", command=cancel, bg='#26262E', fg='#9CA3AF', activebackground='#32323D', activeforeground='#F3F4F6', relief='flat', font=('Segoe UI', 10), bd=5, padx=10)
    btn_cancel.pack(side='right', padx=6, pady=10)
    
    dialog.wait_window()
    root.destroy()
    return result

def remove_soft_edges(img):
    """Transforma bordas semi-transparentes em sólidas para evitar contornos feios no ColorKey."""
    if img.get_flags() & pygame.SRCALPHA:
        alpha_array = pygame.surfarray.pixels_alpha(img)
        alpha_array[alpha_array < 127] = 0
        alpha_array[alpha_array >= 127] = 255
        del alpha_array
    return img

def load_wardrobe_images(config, dest_dict):
    """Carrega na memória as imagens ativas do guarda-roupa."""
    for item in config.get('wardrobe', []):
        if item.get('path') and os.path.exists(item['path']):
            try:
                img = pygame.image.load(item['path']).convert_alpha()
                dest_dict[item['id']] = img
            except Exception as e:
                print(f"Erro imagem guarda-roupa: {e}")

def load_character_images_scaled(paths, max_w, max_h, manual_scale=1.0):
    """Carrega e ajusta a escala das imagens baseadas no tamanho da tela."""
    images = {}
    char_path = paths.get("char")
    
    if not char_path or not os.path.exists(char_path):
        return images
        
    char_img = pygame.image.load(char_path).convert_alpha()
    orig_w, orig_h = char_img.get_size()
    
    scale = 1.0
    if orig_w > max_w or orig_h > max_h:
        scale = min(max_w / orig_w, max_h / orig_h)
        
    final_scale = scale * manual_scale
        
    if final_scale != 1.0:
        char_img = pygame.transform.smoothscale(char_img, (max(1, int(orig_w * final_scale)), max(1, int(orig_h * final_scale))))
        
    images["char"] = char_img
    
    for key in ["eyes_open", "eyes_closed", "mouth_open"]:
        path = paths.get(key)
        if path and os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            if final_scale != 1.0:
                w, h = img.get_size()
                img = pygame.transform.smoothscale(img, (max(1, int(w * final_scale)), max(1, int(h * final_scale))))
            images[key] = img
        else:
            images[key] = None
            
    return images

def get_wardrobe_layout(config, wardrobe_scroll, collapsed_cats):
    """Calcula o layout em acordeão das categorias do guarda-roupa."""
    categories = ["chapéus", "acessórios", "maquiagem", "calças", "casacos", "camisas", "objetos_de_cena", "cor_dos_olhos"]
    layout = []
    
    draw_y = 80 - wardrobe_scroll
    for cat in categories:
        cat_items = [(i, item) for i, item in enumerate(config.get('wardrobe', [])) if item.get('category') == cat]
        
        layout.append({
            'type': 'header',
            'cat': cat,
            'rect': pygame.Rect(20, draw_y, 440, 42),
            'count': len(cat_items)
        })
        draw_y += 48
        
        if cat not in collapsed_cats:
            for idx_in_cat, (i, item) in enumerate(cat_items):
                layout.append({
                    'type': 'item',
                    'cat': cat,
                    'index': i,
                    'idx_in_cat': idx_in_cat,
                    'total_in_cat': len(cat_items),
                    'item': item,
                    'y': draw_y
                })
                draw_y += 52
    return layout

# --- Aplicação Principal ---

def main():
    global last_blink_time, next_blink_interval, is_blinking, SOUND_THRESHOLD

    pygame.init()
    pygame.font.init()

    # --- Configuração do Ícone da Janela ---
    try:
        icon_path = resource_path('icon.ico')
        if os.path.exists(icon_path):
            pygame.display.set_icon(pygame.image.load(icon_path))
    except Exception as e:
        print(f"Erro ao carregar o ícone: {e}")

    # --- Configuração da Janela ---
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"Pytuber Studio v{APP_VERSION}")
    clock = pygame.time.Clock()

    # Dispara a verificação assíncrona de atualizações sem bloquear a inicialização
    check_for_updates_async()

    # --- Variáveis de Estado ---
    current_state = "MENU"
    config = load_config()
    SOUND_THRESHOLD = config.get('sound_threshold', 0.1)
    paths = config['paths']
    offsets = config['offsets']
    images = {}
    current_profile_name = "Padrão"

    # Verificação de arquivos na inicialização
    missing_files = False
    for key, path in paths.items():
        if path and not os.path.exists(path):
            paths[key] = None
            missing_files = True
            
    if missing_files:
        save_config(config)
        
    notification_text = "Aviso: Imagens ausentes foram removidas!" if missing_files else ""
    notification_time = time.time() if missing_files else 0

    # Tenta pré-carregar imagens para o preview em tempo real
    if paths.get("char") and os.path.exists(paths["char"]):
        try:
            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
        except Exception as e:
            print(f"Erro ao carregar sprites iniciais: {e}")

    # Variáveis do modo de posicionamento
    editing_part_index = 0
    parts_list = ['char', 'eyes', 'mouth']
    
    # Superfície para Contorno Sólido e Preview
    composition_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    preview_canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

    # Sistema de Desfazer (Undo)
    undo_stack = []
    pre_drag_state = None
    last_continuous_action_time = 0
    
    def save_state_for_undo():
        state = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})
        undo_stack.append(state)
        if len(undo_stack) > 50:
            undo_stack.pop(0)

    wardrobe_images = {}
    load_wardrobe_images(config, wardrobe_images)

    def get_file(title):
        """Abre o explorador de arquivos para escolher uma imagem."""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        p = filedialog.askopenfilename(title=title, filetypes=[("Imagens PNG", "*.png")])
        root.destroy()
        return p

    # --- Setup de Áudio ---
    input_devices = get_input_devices()
    selected_device_idx = config.get('audio_device')
    if selected_device_idx is not None and not any(i == selected_device_idx for i, d in input_devices):
        selected_device_idx = None
        
    if selected_device_idx is None and input_devices:
        try:
            selected_device_idx = sd.default.device[0]
        except Exception:
            selected_device_idx = input_devices[0][0]

    current_device_list_index = 0
    for i, (idx, dev) in enumerate(input_devices):
        if idx == selected_device_idx:
            current_device_list_index = i
            break
            
    if input_devices:
        start_audio_stream(selected_device_idx)

    dropdown_open = False
    device_scroll_offset = 0

    # Função unificada de desenho do avatar
    def draw_avatar(base_char_center, anim_offset=(0, 0), force_e=False, force_m=False, target_surf=None):
        if target_surf is None:
            target_surf = screen
            
        anim_char_center = (base_char_center[0] + anim_offset[0], base_char_center[1] + anim_offset[1])
        is_hard_edges = config.get('hard_edges', False)
        
        render_dest = composition_surface if is_hard_edges else target_surf
        if is_hard_edges:
            render_dest.fill((0, 0, 0, 0))
            
        eyes_are_open = not (is_blinking or force_e)

        def draw_layer_items(layer_target, surf=None, transparent_pass=False):
            if surf is None:
                surf = render_dest
            for w_item in config.get('wardrobe', []):
                cat = w_item.get('category')
                item_layer = w_item.get('layer', get_default_layer(cat))
                
                is_transparent_cat = cat in ["objetos_de_cena", "cor_dos_olhos"]
                
                if is_hard_edges:
                    if transparent_pass and not is_transparent_cat:
                        continue
                    if not transparent_pass and is_transparent_cat:
                        continue
                else:
                    if transparent_pass:
                        continue
                        
                if cat == "cor_dos_olhos" and not eyes_are_open:
                    continue

                if w_item.get('active') and item_layer == layer_target and w_item['id'] in wardrobe_images:
                    img = wardrobe_images[w_item['id']]
                    scale = w_item.get('scale', 1.0)
                    if scale != 1.0:
                        w, h = img.get_size()
                        img = pygame.transform.smoothscale(img, (max(1, int(w * scale)), max(1, int(h * scale))))
                    center_to_use = base_char_center if cat == "objetos_de_cena" else anim_char_center
                    item_c = (center_to_use[0] + w_item['offset'][0], center_to_use[1] + w_item['offset'][1])
                    surf.blit(img, img.get_rect(center=item_c))
                    
        draw_layer_items('trás')
        
        if "char" in images and images["char"]:
            render_dest.blit(images['char'], images['char'].get_rect(center=anim_char_center))
            
        draw_layer_items('meio')
            
        eyes_c = (anim_char_center[0] + offsets['eyes'][0], anim_char_center[1] + offsets['eyes'][1])
        if not eyes_are_open and "eyes_closed" in images and images["eyes_closed"]:
            render_dest.blit(images["eyes_closed"], images["eyes_closed"].get_rect(center=eyes_c))
        elif eyes_are_open and "eyes_open" in images and images["eyes_open"]:
            render_dest.blit(images["eyes_open"], images["eyes_open"].get_rect(center=eyes_c))
            
        mouth_c = (anim_char_center[0] + offsets['mouth'][0], anim_char_center[1] + offsets['mouth'][1])
        if (is_speaking or force_m) and "mouth_open" in images and images["mouth_open"]:
            render_dest.blit(images["mouth_open"], images["mouth_open"].get_rect(center=mouth_c))
            
        draw_layer_items('frente')
        
        if is_hard_edges:
            target_surf_final = remove_soft_edges(render_dest)
            draw_layer_items('trás', target_surf, transparent_pass=True)
            target_surf.blit(target_surf_final, (0, 0))
            draw_layer_items('meio', target_surf, transparent_pass=True)
            draw_layer_items('frente', target_surf, transparent_pass=True)

    # Variáveis de interação
    dragging_part = None
    dragging_slider = False
    wardrobe_dragging_item_id = None
    wardrobe_selected_item_id = None
    wardrobe_scroll = 0
    wardrobe_collapsed_cats = set()
    dragging_wardrobe_slider = False
    wardrobe_panel_width = 480
    vcam_install_status = {'in_progress': False, 'message': None}
    show_update_modal = False
    update_modal_seen = False
    btn_update_pill = None
    
    last_cycle_profile_pressed = False
    current_profile_index = -1
    profile_notif_text = ""
    profile_notif_time = 0
    vcam = None

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        current_time = time.time()
        hover_clickable = False

        if vcam_install_status['message']:
            notification_text = vcam_install_status['message']
            notification_time = time.time()
            vcam_install_status['message'] = None

        # Exibe o modal de atualização automaticamente 1 vez ao detectar nova versão
        if GLOBAL_UPDATE_INFO.status == UpdateStatus.AVAILABLE and not update_modal_seen and current_state == "MENU":
            show_update_modal = True
            update_modal_seen = True

        # --- Lógica de Piscar e Animação ---
        if current_time - last_blink_time > next_blink_interval:
            is_blinking = True
            last_blink_time = current_time
            next_blink_interval = random.uniform(2, 6)
        if is_blinking and current_time - last_blink_time > 0.12:
            is_blinking = False

        breath_offset = 0
        sway_offset = 0
        if config.get('animations_enabled', True):
            breath_offset = math.sin(current_time * 2.5) * 3.0
            if is_speaking:
                sway_amplitude = min(12.0, max(2.0, current_volume * 10.0))
                sway_offset = math.sin(current_time * 18.0) * sway_amplitude

        anim_offset = (int(sway_offset), int(breath_offset))

        # --- Definição dos Retângulos da Interface (MENU) ---
        # Header (y: 12 - 56)
        header_rect = pygame.Rect(20, 12, SCREEN_WIDTH - 40, 44)
        btn_load_profile = pygame.Rect(header_rect.right - 195, 16, 92, 34)
        btn_save_profile = pygame.Rect(header_rect.right - 95, 16, 92, 34)

        # Coluna Esquerda: Preview e Controles Principais (x: 20, largura: 430)
        col_left_x = 20
        col_left_w = 430
        preview_card_rect = pygame.Rect(col_left_x, 68, col_left_w, 420)
        preview_viewport_rect = pygame.Rect(col_left_x + 16, 122, col_left_w - 32, 268)
        status_badge_rect = pygame.Rect(col_left_x + 16, 400, 140, 28)

        controls_card_rect = pygame.Rect(col_left_x, 500, col_left_w, 206)
        btn_start = pygame.Rect(col_left_x + 16, 514, col_left_w - 32, 50)
        btn_virtualcam_card = pygame.Rect(col_left_x + 16, 574, col_left_w - 32, 42)
        btn_virtualcam_switch = pygame.Rect(btn_virtualcam_card.right - 54, btn_virtualcam_card.y + 10, 42, 22)

        btn_positioning = pygame.Rect(col_left_x + 16, 626, (col_left_w - 40) // 2, 38)
        btn_wardrobe = pygame.Rect(btn_positioning.right + 8, 626, (col_left_w - 40) // 2, 38)

        # Coluna Direita: Cards Agrupados (x: 470, largura: 790)
        col_right_x = 470
        col_right_w = 790

        # Card 1: Camadas / Sprites (y: 68 a 308)
        card_sprites_rect = pygame.Rect(col_right_x, 68, col_right_w, 240)
        sprite_keys = ["char", "eyes_open", "eyes_closed", "mouth_open"]
        sprite_labels = ["Personagem Base", "Olhos Abertos", "Olhos Fechados", "Boca Aberta"]
        sprite_rows = []
        for idx in range(4):
            ry = card_sprites_rect.y + 44 + idx * 46
            r_rect = pygame.Rect(card_sprites_rect.x + 16, ry, card_sprites_rect.width - 32, 40)
            btn_choose = pygame.Rect(r_rect.right - 96, r_rect.y + 6, 88, 28)
            sprite_rows.append((r_rect, btn_choose, sprite_keys[idx], sprite_labels[idx]))

        # Card 2: Áudio & Microfone (y: 318 a 478)
        card_audio_rect = pygame.Rect(col_right_x, 318, col_right_w, 160)
        btn_device = pygame.Rect(card_audio_rect.x + 16, card_audio_rect.y + 44, card_audio_rect.width - 76, 38)
        btn_refresh_devices = pygame.Rect(btn_device.right + 8, card_audio_rect.y + 44, 38, 38)
        slider_rect = pygame.Rect(card_audio_rect.x + 16, card_audio_rect.y + 118, card_audio_rect.width - 32, 20)

        # Card 3: Ajustes de Renderização (y: 488 a 706)
        card_render_rect = pygame.Rect(col_right_x, 488, col_right_w, 218)
        sw_w = (card_render_rect.width - 40) // 2
        btn_transparent = pygame.Rect(card_render_rect.x + 16, card_render_rect.y + 44, sw_w, 42)
        btn_borderless = pygame.Rect(card_render_rect.x + 16, card_render_rect.y + 92, sw_w, 42)
        btn_hard_edges = pygame.Rect(btn_transparent.right + 8, card_render_rect.y + 44, sw_w, 42)
        btn_animations = pygame.Rect(btn_borderless.right + 8, card_render_rect.y + 92, sw_w, 42)

        sw_transp_rect = pygame.Rect(btn_transparent.right - 52, btn_transparent.y + 10, 42, 22)
        sw_border_rect = pygame.Rect(btn_borderless.right - 52, btn_borderless.y + 10, 42, 22)
        sw_hard_rect = pygame.Rect(btn_hard_edges.right - 52, btn_hard_edges.y + 10, 42, 22)
        sw_anim_rect = pygame.Rect(btn_animations.right - 52, btn_animations.y + 10, 42, 22)

        btn_bg_color = pygame.Rect(card_render_rect.x + 16, card_render_rect.y + 144, sw_w, 48)
        fps_card_rect = pygame.Rect(btn_bg_color.right + 8, card_render_rect.y + 144, sw_w, 48)

        # Segmented Control FPS [30 | 60 | 120]
        fps_opts = [30, 60, 120]
        fps_seg_rect = pygame.Rect(fps_card_rect.right - 180, fps_card_rect.y + 9, 168, 30)

        # Dropdown de Dispositivos (quando aberto)
        max_visible_devices = 6
        device_item_h = 36
        visible_dev_count = min(len(input_devices), max_visible_devices)
        dropdown_rect = pygame.Rect(btn_device.x, btn_device.bottom + 4, btn_device.width, visible_dev_count * device_item_h + 8)

        # Controles da Tela POSITIONING
        pos_top_bar = pygame.Rect((SCREEN_WIDTH - 760) // 2, 16, 760, 48)
        pos_tab_w = 110
        pos_tab_start_x = pos_top_bar.x + 180
        pos_tab_rects = [pygame.Rect(pos_tab_start_x + t_i * (pos_tab_w + 6), pos_top_bar.y + 8, pos_tab_w, 32) for t_i in range(3)]
        btn_positioning_save = pygame.Rect(pos_top_bar.right - 146, pos_top_bar.y + 8, 134, 32)

        # Controles da Tela WARDROBE
        btn_add_w = pygame.Rect(20, 18, 160, 36)
        btn_back_w = pygame.Rect(190, 18, 120, 36)

        # --- Tratamento de Eventos ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                
                if current_state in ["POSITIONING", "WARDROBE"]:
                    pre_drag_state = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})

                if current_state == "MENU":
                    # Interações do Modal de Atualização (se visível)
                    if show_update_modal:
                        modal_w, modal_h = 560, 370
                        modal_rect = pygame.Rect((SCREEN_WIDTH - modal_w) // 2, (SCREEN_HEIGHT - modal_h) // 2, modal_w, modal_h)
                        btn_modal_close = pygame.Rect(modal_rect.right - 36, modal_rect.y + 14, 22, 22)
                        btn_modal_cancel = pygame.Rect(modal_rect.right - 310, modal_rect.bottom - 52, 120, 36)
                        btn_modal_action = pygame.Rect(modal_rect.right - 176, modal_rect.bottom - 52, 152, 36)
                        btn_inst = pygame.Rect(modal_rect.right - 210, modal_rect.bottom - 52, 186, 36)
                        btn_close_err = pygame.Rect(modal_rect.right - 120, modal_rect.bottom - 52, 96, 36)

                        if btn_modal_close.collidepoint(pos):
                            show_update_modal = False
                            continue
                        elif GLOBAL_UPDATE_INFO.status == UpdateStatus.AVAILABLE:
                            if btn_modal_cancel.collidepoint(pos):
                                show_update_modal = False
                                continue
                            elif btn_modal_action.collidepoint(pos):
                                download_update_async()
                                continue
                        elif GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADED:
                            if btn_inst.collidepoint(pos):
                                launch_installer_and_exit()
                                continue
                        elif GLOBAL_UPDATE_INFO.status == UpdateStatus.ERROR:
                            if btn_close_err.collidepoint(pos):
                                show_update_modal = False
                                continue
                        elif not modal_rect.collidepoint(pos):
                            show_update_modal = False
                            continue
                        continue

                    # Clique no Pill de Atualização no Header
                    if btn_update_pill and btn_update_pill.collidepoint(pos):
                        if GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADED:
                            launch_installer_and_exit()
                        else:
                            show_update_modal = True
                        continue

                    # Lógica do Dropdown quando aberto
                    if dropdown_open:
                        if dropdown_rect.collidepoint(pos) and input_devices:
                            rel_y = pos[1] - (dropdown_rect.y + 4)
                            clicked_idx = device_scroll_offset + (rel_y // device_item_h)
                            if 0 <= clicked_idx < len(input_devices):
                                current_device_list_index = clicked_idx
                                selected_device_idx = input_devices[clicked_idx][0]
                                config['audio_device'] = selected_device_idx
                                save_config(config)
                                start_audio_stream(selected_device_idx)
                                dropdown_open = False
                                continue
                        dropdown_open = False
                        if btn_device.collidepoint(pos):
                            continue

                    # Interações do Header
                    if btn_load_profile.collidepoint(pos):
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        p = filedialog.askopenfilename(title="Carregar Perfil", filetypes=[("Arquivos JSON", "*.json")])
                        root.destroy()
                        if p:
                            try:
                                with open(p, 'r') as f:
                                    config.update(json.load(f))
                                undo_stack.clear()
                                save_config(config)
                                paths = config['paths']
                                offsets = config['offsets']
                                SOUND_THRESHOLD = config.get('sound_threshold', 0.1)
                                wardrobe_images.clear()
                                load_wardrobe_images(config, wardrobe_images)
                                current_profile_name = os.path.basename(p)
                                notification_text = "Perfil carregado com sucesso!"
                                notification_time = time.time()
                                if paths.get("char") and os.path.exists(paths["char"]):
                                    images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                            except Exception as e:
                                print(f"Erro ao carregar perfil: {e}")
                                notification_text = "Erro ao carregar perfil!"
                                notification_time = time.time()

                    elif btn_save_profile.collidepoint(pos):
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        p = filedialog.asksaveasfilename(title="Salvar Perfil", defaultextension=".json", filetypes=[("Arquivos JSON", "*.json")])
                        root.destroy()
                        if p:
                            try:
                                with open(p, 'w') as f:
                                    json.dump(config, f, indent=4)
                                current_profile_name = os.path.basename(p)
                                notification_text = "Perfil salvo com sucesso!"
                                notification_time = time.time()
                            except Exception as e:
                                print(f"Erro ao salvar perfil: {e}")
                                notification_text = "Erro ao salvar perfil!"
                                notification_time = time.time()

                    # Iniciar Avatar
                    elif btn_start.collidepoint(pos) and all(paths.values()):
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                            current_state = "RUNNING"
                            if config.get('borderless_window', False):
                                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
                            else:
                                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                            set_window_transparency(config['bg_color'], config.get('transparent_window', False))
                            
                            if config.get('virtual_camera', False) and HAS_VIRTUALCAM:
                                try:
                                    vcam = pyvirtualcam.Camera(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, fps=config.get('fps_limit', 60), fmt=pyvirtualcam.PixelFormat.RGB)
                                except Exception as e:
                                    print(f"Erro ao iniciar câmera virtual: {e}")
                                    vcam = None
                                    notification_text = "Erro Câm. Virtual! Ative o OBS Virtual Cam"
                                    notification_time = time.time()
                                    config['virtual_camera'] = False
                        except Exception as e:
                            print(f"Erro ao carregar imagem: {e}")
                            notification_text = "Erro: Arquivo de imagem inválido!"
                            notification_time = time.time()

                    # Câmera Virtual
                    elif btn_virtualcam_card.collidepoint(pos):
                        if HAS_VIRTUALCAM:
                            config['virtual_camera'] = not config.get('virtual_camera', False)
                            save_config(config)
                            notification_text = "Câmera Virtual Ativada!" if config['virtual_camera'] else "Câmera Virtual Desativada"
                            notification_time = time.time()
                        elif sys.version_info >= (3, 15):
                            root = tk.Tk()
                            root.withdraw()
                            root.attributes('-topmost', True)
                            messagebox.showinfo(
                                "Câmera Virtual • Python 3.15",
                                "O pacote 'pyvirtualcam' é compilado em C++ e atualmente suporta até o Python 3.14 (ainda não possui distribuições compatíveis no PyPI para o Python 3.15).\n\n"
                                "💡 Como transmitir ao OBS e Discord com alta performance:\n"
                                "1. Ative 'Sem Bordas' ou 'Transparente' nas opções ao lado.\n"
                                "2. No OBS Studio, adicione uma fonte de 'Captura de Jogo' (Game Capture) apontando para a janela do Pytuber e marque a opção 'Permitir Transparência'.\n"
                                "3. Para usar no Discord, Zoom ou Meet, clique em 'Iniciar Câmera Virtual' dentro do próprio OBS Studio!"
                            )
                            root.destroy()
                            notification_text = "pyvirtualcam requer Python <= 3.14. Use OBS Captura de Jogo!"
                            notification_time = time.time()
                        else:
                            if vcam_install_status['in_progress']:
                                notification_text = "Instalação da Câmera Virtual já em andamento..."
                                notification_time = time.time()
                            else:
                                root = tk.Tk()
                                root.withdraw()
                                root.attributes('-topmost', True)
                                ans = messagebox.askyesno(
                                    "Instalar Câmera Virtual",
                                    "O pacote 'pyvirtualcam' é necessário para transmitir o avatar para o OBS Studio, Discord ou Meet como uma câmera virtual.\n\nDeseja autorizar e realizar a instalação automática agora via pip?"
                                )
                                root.destroy()
                                if ans:
                                    vcam_install_status['in_progress'] = True
                                    notification_text = "Instalando pyvirtualcam... Por favor, aguarde."
                                    notification_time = time.time()

                                    def _install_vcam():
                                        global HAS_VIRTUALCAM, pyvirtualcam
                                        try:
                                            res = subprocess.run(
                                                [sys.executable, "-m", "pip", "install", "pyvirtualcam"],
                                                capture_output=True,
                                                text=True,
                                                timeout=180
                                            )
                                            if res.returncode == 0:
                                                import importlib
                                                try:
                                                    pyvirtualcam = importlib.import_module("pyvirtualcam")
                                                    HAS_VIRTUALCAM = True
                                                    config['virtual_camera'] = True
                                                    save_config(config)
                                                    vcam_install_status['message'] = "pyvirtualcam instalado! Câmera Virtual ativada."
                                                except Exception as load_err:
                                                    vcam_install_status['message'] = f"Instalado, mas erro ao carregar: {load_err}"
                                            else:
                                                if "No matching distribution" in res.stderr:
                                                    err_msg = "Indisponível no PyPI para esta versão do Python"
                                                else:
                                                    err_msg = res.stderr.strip()[:60] if res.stderr else "Erro desconhecido"
                                                vcam_install_status['message'] = f"Erro na instalação: {err_msg}"
                                        except Exception as ex:
                                            vcam_install_status['message'] = f"Falha na instalação: {str(ex)[:60]}"
                                        finally:
                                            vcam_install_status['in_progress'] = False

                                    threading.Thread(target=_install_vcam, daemon=True).start()
                                else:
                                    notification_text = "Instalação da Câmera Virtual não autorizada."
                                    notification_time = time.time()

                    # Botões Secundários: Posições e Guarda-Roupa
                    elif btn_positioning.collidepoint(pos):
                        if all(paths.values()):
                            try:
                                images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                                current_state = "POSITIONING"
                            except Exception as e:
                                print(f"Erro ao carregar imagem: {e}")
                                notification_text = "Erro: Arquivo de imagem inválido!"
                                notification_time = time.time()
                        else:
                            notification_text = "Selecione todos os sprites antes de posicionar!"
                            notification_time = time.time()

                    elif btn_wardrobe.collidepoint(pos):
                        current_state = "WARDROBE"
                        load_wardrobe_images(config, wardrobe_images)

                    # Seleção de Sprites
                    else:
                        clicked_sprite = False
                        for r_rect, btn_choose, skey, slabel in sprite_rows:
                            if r_rect.collidepoint(pos):
                                new_path = get_file(f"Selecione {slabel}")
                                if new_path:
                                    config['paths'][skey] = import_image_to_assets(new_path, "base")
                                    save_config(config)
                                    if paths.get("char") and os.path.exists(paths["char"]):
                                        try:
                                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                                        except Exception:
                                            pass
                                clicked_sprite = True
                                break

                        if not clicked_sprite:
                            # Áudio: Dropdown e Refresh
                            if btn_device.collidepoint(pos) and input_devices:
                                dropdown_open = not dropdown_open
                            elif btn_refresh_devices.collidepoint(pos):
                                input_devices = get_input_devices()
                                dropdown_open = False
                                current_selection_id = config.get('audio_device')
                                if not any(d[0] == current_selection_id for d in input_devices):
                                    current_selection_id = input_devices[0][0] if input_devices else None
                                    config['audio_device'] = current_selection_id
                                    save_config(config)
                                    start_audio_stream(current_selection_id)
                                selected_device_idx = current_selection_id
                                for i, (idx, dev) in enumerate(input_devices):
                                    if idx == selected_device_idx:
                                        current_device_list_index = i
                                        break

                            # Slider de Sensibilidade
                            elif slider_rect.inflate(0, 16).collidepoint(pos):
                                dragging_slider = True
                                rel_x = max(0, min(pos[0] - slider_rect.x, slider_rect.width))
                                SOUND_THRESHOLD = 0.01 + (rel_x / slider_rect.width) * 0.49
                                config['sound_threshold'] = round(SOUND_THRESHOLD, 3)

                            # Switches de Renderização
                            elif btn_transparent.collidepoint(pos):
                                config['transparent_window'] = not config.get('transparent_window', False)
                                save_config(config)
                            elif btn_borderless.collidepoint(pos):
                                config['borderless_window'] = not config.get('borderless_window', False)
                                save_config(config)
                            elif btn_hard_edges.collidepoint(pos):
                                config['hard_edges'] = not config.get('hard_edges', False)
                                save_config(config)
                            elif btn_animations.collidepoint(pos):
                                config['animations_enabled'] = not config.get('animations_enabled', True)
                                save_config(config)

                            # Cor de Fundo
                            elif btn_bg_color.collidepoint(pos):
                                root = tk.Tk()
                                root.withdraw()
                                root.attributes('-topmost', True)
                                color = colorchooser.askcolor(title="Escolha a cor de fundo", initialcolor=tuple(config['bg_color']))
                                root.destroy()
                                if color[0]:
                                    config['bg_color'] = [int(c) for c in color[0]]
                                    save_config(config)

                            # Segmented Control FPS
                            elif fps_seg_rect.collidepoint(pos):
                                seg_w = fps_seg_rect.width / len(fps_opts)
                                seg_idx = int((pos[0] - fps_seg_rect.x) // seg_w)
                                if 0 <= seg_idx < len(fps_opts):
                                    config['fps_limit'] = fps_opts[seg_idx]
                                    save_config(config)

                elif current_state == "POSITIONING":
                    if btn_positioning_save.collidepoint(pos):
                        config['offsets'] = offsets
                        save_config(config)
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                        except Exception:
                            pass
                        current_state = "MENU"
                        notification_text = "Posições salvas com sucesso!"
                        notification_time = time.time()
                    else:
                        # Tab pills no topo para escolher peça
                        clicked_tab = False
                        for t_idx, t_box in enumerate(pos_tab_rects):
                            if t_box.collidepoint(pos):
                                editing_part_index = t_idx
                                clicked_tab = True
                                break
                        if not clicked_tab:
                            char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
                            mouth_rect_hit = images['mouth_open'].get_rect(center=(char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])) if 'mouth_open' in images and images['mouth_open'] else None
                            eyes_rect_hit = images['eyes_open'].get_rect(center=(char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])) if 'eyes_open' in images and images['eyes_open'] else None
                            c_rect_hit = images['char'].get_rect(center=char_center) if 'char' in images and images['char'] else None
                            
                            if mouth_rect_hit and mouth_rect_hit.collidepoint(pos):
                                dragging_part = 'mouth'
                                editing_part_index = 2
                            elif eyes_rect_hit and eyes_rect_hit.collidepoint(pos):
                                dragging_part = 'eyes'
                                editing_part_index = 1
                            elif c_rect_hit and c_rect_hit.collidepoint(pos):
                                dragging_part = 'char'
                                editing_part_index = 0

                elif current_state == "WARDROBE":
                    if btn_add_w.collidepoint(pos):
                        new_item = edit_wardrobe_item_dialog()
                        if new_item:
                            if pre_drag_state:
                                undo_stack.append(pre_drag_state)
                                if len(undo_stack) > 50: undo_stack.pop(0)
                                pre_drag_state = None
                            config['wardrobe'].append(new_item)
                            save_config(config)
                            load_wardrobe_images(config, wardrobe_images)
                    elif btn_back_w.collidepoint(pos):
                        current_state = "MENU"
                    else:
                        layout = get_wardrobe_layout(config, wardrobe_scroll, wardrobe_collapsed_cats)
                        clicked_list = False
                        for node in layout:
                            if node['type'] == 'header':
                                if node['rect'].collidepoint(pos) and 70 <= node['rect'].y <= SCREEN_HEIGHT:
                                    if node['cat'] in wardrobe_collapsed_cats:
                                        wardrobe_collapsed_cats.remove(node['cat'])
                                    else:
                                        wardrobe_collapsed_cats.add(node['cat'])
                                    clicked_list = True
                                    break
                            elif node['type'] == 'item':
                                item_y = node['y']
                                if item_y < 70 or item_y > SCREEN_HEIGHT: continue
                                i = node['index']
                                item = node['item']
                                rects = get_wardrobe_item_rects(item_y)
                                
                                # Toggle Ativo
                                if rects['active'].collidepoint(pos):
                                    item['active'] = not item.get('active', True)
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Trava
                                elif rects['lock'].collidepoint(pos):
                                    item['locked'] = not item.get('locked', False)
                                    if item['locked'] and wardrobe_dragging_item_id == item['id']:
                                        wardrobe_dragging_item_id = None
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Camada (F/M/T)
                                elif rects['layer'].collidepoint(pos):
                                    cat = item.get('category')
                                    current_layer = item.get('layer', get_default_layer(cat))
                                    item['layer'] = 'meio' if current_layer == 'frente' else ('trás' if current_layer == 'meio' else 'frente')
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Reordenar Subir
                                elif rects['up'].collidepoint(pos) and node['idx_in_cat'] > 0:
                                    for prev_i in range(i - 1, -1, -1):
                                        if config['wardrobe'][prev_i]['category'] == node['cat']:
                                            config['wardrobe'][i], config['wardrobe'][prev_i] = config['wardrobe'][prev_i], config['wardrobe'][i]
                                            break
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Reordenar Descer
                                elif rects['down'].collidepoint(pos) and node['idx_in_cat'] < node['total_in_cat'] - 1:
                                    for next_i in range(i + 1, len(config['wardrobe'])):
                                        if config['wardrobe'][next_i]['category'] == node['cat']:
                                            config['wardrobe'][i], config['wardrobe'][next_i] = config['wardrobe'][next_i], config['wardrobe'][i]
                                            break
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Editar
                                elif rects['edit'].collidepoint(pos):
                                    edited = edit_wardrobe_item_dialog(item)
                                    if edited:
                                        if pre_drag_state:
                                            undo_stack.append(pre_drag_state)
                                            if len(undo_stack) > 50: undo_stack.pop(0)
                                            pre_drag_state = None
                                        config['wardrobe'][i] = edited
                                        save_config(config)
                                        load_wardrobe_images(config, wardrobe_images)
                                    clicked_list = True
                                    break
                                # Excluir
                                elif rects['delete'].collidepoint(pos):
                                    del config['wardrobe'][i]
                                    if wardrobe_selected_item_id == item.get('id'):
                                        wardrobe_selected_item_id = None
                                    save_config(config)
                                    clicked_list = True
                                    break
                                # Selecionar ao clicar no card
                                elif rects['card'].collidepoint(pos):
                                    wardrobe_selected_item_id = item['id']
                                    clicked_list = True
                                    break

                        if not clicked_list:
                            # Controles da Barra Superior de Escala do Item Selecionado
                            clicked_scale_ctrl = False
                            if wardrobe_selected_item_id:
                                w_bar = pygame.Rect(wardrobe_panel_width + 20, 16, SCREEN_WIDTH - wardrobe_panel_width - 40, 52)
                                btn_sc_reset = pygame.Rect(w_bar.right - 58, w_bar.y + 11, 44, 30)
                                btn_sc_plus = pygame.Rect(btn_sc_reset.left - 38, w_bar.y + 11, 32, 30)
                                slider_sc_w = 110
                                slider_sc_rect = pygame.Rect(btn_sc_plus.left - slider_sc_w - 10, w_bar.y + 22, slider_sc_w, 8)
                                btn_sc_minus = pygame.Rect(slider_sc_rect.left - 42, w_bar.y + 11, 32, 30)

                                if w_bar.collidepoint(pos):
                                    clicked_scale_ctrl = True
                                    for item in config.get('wardrobe', []):
                                        if item['id'] == wardrobe_selected_item_id:
                                            cur_sc = item.get('scale', 1.0)
                                            if btn_sc_minus.collidepoint(pos):
                                                item['scale'] = max(0.1, min(3.0, round(cur_sc - 0.05, 2)))
                                                save_config(config)
                                            elif btn_sc_plus.collidepoint(pos):
                                                item['scale'] = max(0.1, min(3.0, round(cur_sc + 0.05, 2)))
                                                save_config(config)
                                            elif btn_sc_reset.collidepoint(pos):
                                                item['scale'] = 1.0
                                                save_config(config)
                                            elif slider_sc_rect.inflate(10, 16).collidepoint(pos):
                                                dragging_wardrobe_slider = True
                                                rel_x = max(0, min(pos[0] - slider_sc_rect.x, slider_sc_rect.width))
                                                item['scale'] = max(0.1, min(3.0, round(0.1 + (rel_x / slider_sc_rect.width) * 2.9, 2)))
                                                save_config(config)
                                            break

                            if not clicked_scale_ctrl:
                                preview_center_x = wardrobe_panel_width + (SCREEN_WIDTH - wardrobe_panel_width) // 2
                                char_center = (preview_center_x + config['offsets']['char'][0], SCREEN_HEIGHT // 2 + config['offsets']['char'][1])
                                
                                click_order = []
                                for w_item in reversed(config.get('wardrobe', [])):
                                    cat = w_item.get('category')
                                    if w_item.get('layer', get_default_layer(cat)) == 'frente':
                                        click_order.append(w_item)
                                for w_item in reversed(config.get('wardrobe', [])):
                                    cat = w_item.get('category')
                                    if w_item.get('layer', get_default_layer(cat)) == 'meio':
                                        click_order.append(w_item)
                                for w_item in reversed(config.get('wardrobe', [])):
                                    cat = w_item.get('category')
                                    if w_item.get('layer', get_default_layer(cat)) == 'trás':
                                        click_order.append(w_item)

                                clicked_avatar_item = False
                                for item in click_order:
                                    if wardrobe_dragging_item_id: break
                                    if item.get('active') and item['id'] in wardrobe_images:
                                        img_w, img_h = wardrobe_images[item['id']].get_size()
                                        scale = item.get('scale', 1.0)
                                        item_rect = pygame.Rect(0, 0, max(1, int(img_w * scale)), max(1, int(img_h * scale)))
                                        item_center = (char_center[0] + item['offset'][0], char_center[1] + item['offset'][1])
                                        item_rect.center = item_center
                                        if item_rect.collidepoint(pos):
                                            wardrobe_selected_item_id = item['id']
                                            clicked_avatar_item = True
                                            if not item.get('locked', False):
                                                wardrobe_dragging_item_id = item['id']
                                            break
                                
                                if not clicked_avatar_item and pos[0] >= wardrobe_panel_width:
                                    # Clique no espaço vazio do preview deseleciona o item
                                    wardrobe_selected_item_id = None

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if pre_drag_state:
                    current_state_snap = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})
                    if current_state_snap != pre_drag_state:
                        undo_stack.append(pre_drag_state)
                        if len(undo_stack) > 50: undo_stack.pop(0)
                    pre_drag_state = None
                    
                if dragging_slider:
                    dragging_slider = False
                    config['sound_threshold'] = round(SOUND_THRESHOLD, 3)
                    save_config(config)
                
                if dragging_wardrobe_slider:
                    dragging_wardrobe_slider = False
                    save_config(config)
                
                if wardrobe_dragging_item_id:
                    save_config(config)
                dragging_part = None
                wardrobe_dragging_item_id = None

            elif event.type == pygame.MOUSEMOTION:
                if dragging_slider:
                    rel_x = max(0, min(event.pos[0] - slider_rect.x, slider_rect.width))
                    SOUND_THRESHOLD = 0.01 + (rel_x / slider_rect.width) * 0.49
                    config['sound_threshold'] = round(SOUND_THRESHOLD, 3)
                elif current_state == "POSITIONING" and dragging_part:
                    offsets[dragging_part][0] += event.rel[0]
                    offsets[dragging_part][1] += event.rel[1]
                elif current_state == "WARDROBE":
                    if wardrobe_dragging_item_id:
                        for item in config['wardrobe']:
                            if item['id'] == wardrobe_dragging_item_id:
                                item['offset'][0] += event.rel[0]
                                item['offset'][1] += event.rel[1]
                                break
                    elif dragging_wardrobe_slider and wardrobe_selected_item_id:
                        w_bar = pygame.Rect(wardrobe_panel_width + 20, 16, SCREEN_WIDTH - wardrobe_panel_width - 40, 52)
                        btn_sc_reset = pygame.Rect(w_bar.right - 58, w_bar.y + 11, 44, 30)
                        btn_sc_plus = pygame.Rect(btn_sc_reset.left - 38, w_bar.y + 11, 32, 30)
                        slider_sc_w = 110
                        slider_sc_rect = pygame.Rect(btn_sc_plus.left - slider_sc_w - 10, w_bar.y + 22, slider_sc_w, 8)
                        rel_x = max(0, min(event.pos[0] - slider_sc_rect.x, slider_sc_rect.width))
                        new_sc = round(0.1 + (rel_x / slider_sc_rect.width) * 2.9, 2)
                        for item in config.get('wardrobe', []):
                            if item['id'] == wardrobe_selected_item_id and not item.get('locked', False):
                                item['scale'] = max(0.1, min(3.0, new_sc))
                                break

            elif event.type == pygame.MOUSEWHEEL:
                if current_state == "MENU" and dropdown_open:
                    device_scroll_offset = max(0, min(device_scroll_offset - event.y, max(0, len(input_devices) - max_visible_devices)))
                elif current_state == "POSITIONING":
                    if time.time() - last_continuous_action_time > 0.5:
                        save_state_for_undo()
                    last_continuous_action_time = time.time()
                    
                    manual_scale = config.get('char_scale', 1.0)
                    new_scale = max(0.1, min(5.0, manual_scale + (event.y * 0.01)))
                    if new_scale != manual_scale:
                        factor = new_scale / manual_scale
                        config['char_scale'] = new_scale
                        for part in ['char', 'eyes', 'mouth']:
                            config['offsets'][part][0] *= factor
                            config['offsets'][part][1] *= factor
                        for item in config.get('wardrobe', []):
                            item['offset'][0] *= factor
                            item['offset'][1] *= factor
                            item['scale'] = item.get('scale', 1.0) * factor
                        save_config(config)
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, new_scale))
                        except Exception as e:
                            print(f"Erro ao redimensionar personagem: {e}")

                elif current_state == "WARDROBE":
                    if event.pos[0] < wardrobe_panel_width:
                        wardrobe_scroll = max(0, wardrobe_scroll - event.y * 20)
                    elif wardrobe_selected_item_id:
                        for item in config['wardrobe']:
                            if item['id'] == wardrobe_selected_item_id and not item.get('locked', False):
                                item['scale'] = max(0.1, min(5.0, item.get('scale', 1.0) + event.y * 0.02))
                                save_config(config)
                                break

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if undo_stack:
                        last_state = undo_stack.pop()
                        config['offsets'] = copy.deepcopy(last_state['offsets'])
                        config['wardrobe'] = copy.deepcopy(last_state['wardrobe'])
                        config['char_scale'] = last_state['char_scale']
                        offsets = config['offsets']
                        save_config(config)
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                            wardrobe_images.clear()
                            load_wardrobe_images(config, wardrobe_images)
                        except Exception: pass
                        notification_text = "Ação desfeita!"
                        notification_time = time.time()

                elif event.key == pygame.K_ESCAPE:
                    if current_state == "RUNNING":
                        current_state = "MENU"
                        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                        set_window_transparency(config['bg_color'], False)
                        if vcam:
                            vcam.close()
                            vcam = None
                    elif current_state in ["POSITIONING", "WARDROBE"]:
                        current_state = "MENU"
                
                elif current_state == "POSITIONING":
                    selected_part = parts_list[editing_part_index]
                    step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                    if event.key == pygame.K_UP: offsets[selected_part][1] -= step
                    elif event.key == pygame.K_DOWN: offsets[selected_part][1] += step
                    elif event.key == pygame.K_LEFT: offsets[selected_part][0] -= step
                    elif event.key == pygame.K_RIGHT: offsets[selected_part][0] += step
                    elif event.key == pygame.K_TAB:
                        editing_part_index = (editing_part_index + 1) % len(parts_list)

                elif current_state == "WARDROBE" and wardrobe_selected_item_id:
                    step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                    for item in config.get('wardrobe', []):
                        if item['id'] == wardrobe_selected_item_id and not item.get('locked', False):
                            if event.key == pygame.K_UP: item['offset'][1] -= step
                            elif event.key == pygame.K_DOWN: item['offset'][1] += step
                            elif event.key == pygame.K_LEFT: item['offset'][0] -= step
                            elif event.key == pygame.K_RIGHT: item['offset'][0] += step
                            elif event.key in [pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS]:
                                item['scale'] = max(0.1, min(3.0, round(item.get('scale', 1.0) + 0.05, 2)))
                            elif event.key in [pygame.K_MINUS, pygame.K_KP_MINUS]:
                                item['scale'] = max(0.1, min(3.0, round(item.get('scale', 1.0) - 0.05, 2)))
                            save_config(config)
                            break

        # --- RENDERIZAÇÃO DA INTERFACE ---

        if current_state == "MENU":
            screen.fill(Theme.BG)

            # 1. HEADER SUPERIOR
            draw_card(screen, header_rect, radius=8)
            
            # Logo / Título
            font_title = get_font(18, bold=True)
            t_logo = font_title.render("Pytuber", True, Theme.TEXT_PRIMARY)
            screen.blit(t_logo, (header_rect.x + 14, header_rect.y + 11))
            
            tag_rect = draw_badge(screen, header_rect.x + 14 + t_logo.get_width() + 10, header_rect.y + 10, f"v{APP_VERSION} • STUDIO", Theme.TEXT_SECONDARY, Theme.BTN_NEUTRAL)

            # Badge / Pill de Atualização no Header
            btn_update_pill = None
            if GLOBAL_UPDATE_INFO.status == UpdateStatus.AVAILABLE:
                pill_x = tag_rect.right + 10
                btn_update_pill = draw_badge(screen, pill_x, header_rect.y + 10, f"⬆ Atualização v{GLOBAL_UPDATE_INFO.latest_version}", (255, 255, 255), Theme.ACCENT_GREEN, radius=6)
                if btn_update_pill.collidepoint(mouse_pos):
                    hover_clickable = True
            elif GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADING:
                pill_x = tag_rect.right + 10
                btn_update_pill = draw_badge(screen, pill_x, header_rect.y + 10, f"Baixando: {int(GLOBAL_UPDATE_INFO.progress * 100)}%", Theme.TEXT_PRIMARY, Theme.BTN_NEUTRAL, border_color=Theme.ACCENT, radius=6)
            elif GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADED:
                pill_x = tag_rect.right + 10
                btn_update_pill = draw_badge(screen, pill_x, header_rect.y + 10, "✓ Instalar Atualização", (255, 255, 255), Theme.ACCENT, radius=6)
                if btn_update_pill.collidepoint(mouse_pos):
                    hover_clickable = True

            # Informação do Perfil Ativo
            font_info = get_font(13)
            p_text = f"Perfil: {current_profile_name}"
            p_surf = font_info.render(p_text, True, Theme.TEXT_SECONDARY)
            screen.blit(p_surf, (btn_load_profile.x - p_surf.get_width() - 16, header_rect.y + 14))

            # Botões Salvar e Carregar Perfil
            h_load = btn_load_profile.collidepoint(mouse_pos)
            h_save = btn_save_profile.collidepoint(mouse_pos)
            draw_card(screen, btn_load_profile, border_color=Theme.BORDER_LIGHT if h_load else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_load else Theme.BTN_NEUTRAL, radius=6)
            draw_card(screen, btn_save_profile, border_color=Theme.BORDER_LIGHT if h_save else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_save else Theme.BTN_NEUTRAL, radius=6)
            
            t_load = font_info.render("Carregar", True, Theme.TEXT_PRIMARY)
            t_save = font_info.render("Salvar", True, Theme.TEXT_PRIMARY)
            screen.blit(t_load, t_load.get_rect(center=btn_load_profile.center))
            screen.blit(t_save, t_save.get_rect(center=btn_save_profile.center))

            if h_load or h_save: hover_clickable = True

            # 2. COLUNA ESQUERDA (Preview & Controles Principais)
            draw_card(screen, preview_card_rect, radius=12)
            
            # Título do Card de Preview
            font_card_title = get_font(14, bold=True)
            screen.blit(font_card_title.render("Preview ao Vivo", True, Theme.TEXT_PRIMARY), (preview_card_rect.x + 16, preview_card_rect.y + 14))
            screen.blit(get_font(12).render("Reativo ao Microfone", True, Theme.TEXT_MUTED), (preview_card_rect.x + 16, preview_card_rect.y + 32))

            # Viewport de Preview do Personagem
            draw_card(screen, preview_viewport_rect, border_color=Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
            
            # Renderização do Avatar no Preview
            if images.get("char"):
                preview_canvas.fill((0, 0, 0, 0))
                p_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
                draw_avatar(p_center, anim_offset, target_surf=preview_canvas)
                # Escala suave para caber perfeitamente no viewport
                scale_ratio = min(preview_viewport_rect.width / SCREEN_WIDTH, preview_viewport_rect.height / SCREEN_HEIGHT) * 1.5
                scaled_w = int(SCREEN_WIDTH * scale_ratio)
                scaled_h = int(SCREEN_HEIGHT * scale_ratio)
                scaled_avatar = pygame.transform.smoothscale(preview_canvas, (scaled_w, scaled_h))
                
                # Recorte no viewport
                screen.set_clip(preview_viewport_rect)
                screen.blit(scaled_avatar, scaled_avatar.get_rect(center=preview_viewport_rect.center))
                screen.set_clip(None)
            else:
                # Placeholder minimalista caso não haja sprites
                font_empty = get_font(13)
                t_e1 = font_empty.render("Nenhum personagem montado", True, Theme.TEXT_MUTED)
                t_e2 = get_font(12).render("Selecione os 4 sprites ao lado", True, Theme.TEXT_MUTED)
                screen.blit(t_e1, t_e1.get_rect(center=(preview_viewport_rect.centerx, preview_viewport_rect.centery - 10)))
                screen.blit(t_e2, t_e2.get_rect(center=(preview_viewport_rect.centerx, preview_viewport_rect.centery + 12)))

            # Badge de Status (● Falando / ● Silêncio)
            if is_speaking:
                b_bg = (16, 50, 35)
                b_border = Theme.ACCENT_GREEN
                b_text = "● Falando"
                b_color = Theme.ACCENT_GREEN
            else:
                b_bg = Theme.BTN_NEUTRAL
                b_border = Theme.BORDER
                b_text = "● Silêncio"
                b_color = Theme.TEXT_SECONDARY
            
            draw_card(screen, status_badge_rect, border_color=b_border, bg_color=b_bg, radius=6)
            t_badge = get_font(12, bold=True).render(b_text, True, b_color)
            screen.blit(t_badge, t_badge.get_rect(center=status_badge_rect.center))

            # Indicador numérico de volume
            vol_pct = int(min(1.0, current_volume / (SOUND_THRESHOLD * 3.0 + 0.001)) * 100)
            vol_info = get_font(12).render(f"Volume: {vol_pct}%", True, Theme.TEXT_MUTED)
            screen.blit(vol_info, (preview_card_rect.right - vol_info.get_width() - 16, 406))

            # Painel de Controles Inferiores (INICIAR, Câmera Virtual, Posições/Guarda-Roupa)
            draw_card(screen, controls_card_rect, radius=12)

            # Botão Principal INICIAR
            can_start = all(paths.values())
            h_start = btn_start.collidepoint(mouse_pos)
            if can_start:
                start_bg = Theme.ACCENT_GREEN_HOVER if h_start else Theme.ACCENT_GREEN
                start_text = "INICIAR AVATAR"
                start_txt_color = (255, 255, 255)
            else:
                start_bg = Theme.BTN_NEUTRAL
                start_text = "SELECIONE OS 4 SPRITES"
                start_txt_color = Theme.TEXT_MUTED

            draw_card(screen, btn_start, border_color=None, bg_color=start_bg, radius=8)
            t_s = get_font(14, bold=True).render(start_text, True, start_txt_color)
            if can_start:
                play_x = btn_start.centerx - t_s.get_width() // 2 - 12
                play_y = btn_start.centery
                pygame.draw.polygon(screen, start_txt_color, [(play_x, play_y - 6), (play_x + 9, play_y), (play_x, play_y + 6)])
                screen.blit(t_s, (btn_start.centerx - t_s.get_width() // 2 + 8, btn_start.centery - t_s.get_height() // 2))
            else:
                screen.blit(t_s, t_s.get_rect(center=btn_start.center))
            if h_start and can_start: hover_clickable = True

            # Row Câmera Virtual (OBS)
            h_vcam = btn_virtualcam_card.collidepoint(mouse_pos)
            draw_card(screen, btn_virtualcam_card, border_color=Theme.BORDER_LIGHT if h_vcam else Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
            vcam_label = get_font(13, bold=True).render("Câmera Virtual (OBS)", True, Theme.TEXT_PRIMARY)
            screen.blit(vcam_label, (btn_virtualcam_card.x + 12, btn_virtualcam_card.y + 12))
            
            if not HAS_VIRTUALCAM:
                if vcam_install_status['in_progress']:
                    draw_badge(screen, btn_virtualcam_card.x + vcam_label.get_width() + 16, btn_virtualcam_card.y + 9, "Instalando...", Theme.ACCENT, (34, 34, 52), radius=4)
                elif sys.version_info >= (3, 15):
                    draw_badge(screen, btn_virtualcam_card.x + vcam_label.get_width() + 16, btn_virtualcam_card.y + 9, "Use OBS", Theme.TEXT_SECONDARY, Theme.BTN_NEUTRAL, radius=4)
                else:
                    draw_badge(screen, btn_virtualcam_card.x + vcam_label.get_width() + 16, btn_virtualcam_card.y + 9, "Requer Lib", Theme.WARNING, Theme.WARNING_BG, radius=4)

            draw_toggle_switch(screen, btn_virtualcam_switch, config.get('virtual_camera', False) and HAS_VIRTUALCAM, hover=h_vcam)
            if h_vcam: hover_clickable = True

            # Botões Secundários: Posições e Guarda-Roupa
            h_pos = btn_positioning.collidepoint(mouse_pos)
            h_ward = btn_wardrobe.collidepoint(mouse_pos)
            draw_card(screen, btn_positioning, border_color=Theme.BORDER_LIGHT if h_pos else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_pos else Theme.BTN_NEUTRAL, radius=6)
            draw_card(screen, btn_wardrobe, border_color=Theme.BORDER_LIGHT if h_ward else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_ward else Theme.BTN_NEUTRAL, radius=6)
            
            t_pos = get_font(13).render("Posições", True, Theme.TEXT_PRIMARY)
            t_ward = get_font(13).render("Guarda-Roupa", True, Theme.TEXT_PRIMARY)
            screen.blit(t_pos, t_pos.get_rect(center=btn_positioning.center))
            screen.blit(t_ward, t_ward.get_rect(center=btn_wardrobe.center))
            if h_pos or h_ward: hover_clickable = True

            # 3. COLUNA DIREITA (Cards de Sprites, Áudio e Ajustes)
            
            # CARD 1: Sprites do Personagem
            draw_card(screen, card_sprites_rect, radius=12)
            screen.blit(font_card_title.render("Sprites do Personagem", True, Theme.TEXT_PRIMARY), (card_sprites_rect.x + 16, card_sprites_rect.y + 14))
            draw_badge(screen, card_sprites_rect.x + 200, card_sprites_rect.y + 12, "4 Peças Principais", Theme.TEXT_SECONDARY, Theme.BTN_NEUTRAL)

            for r_rect, btn_choose, skey, slabel in sprite_rows:
                h_row = r_rect.collidepoint(mouse_pos)
                draw_card(screen, r_rect, border_color=Theme.BORDER_LIGHT if h_row else Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
                
                # Miniatura (Thumbnail 32x32px)
                thumb_rect = pygame.Rect(r_rect.x + 4, r_rect.y + 4, 32, 32)
                draw_card(screen, thumb_rect, border_color=Theme.BORDER, bg_color=Theme.BTN_NEUTRAL, radius=4)
                thumb_img = get_thumbnail(paths.get(skey), size=(32, 32))
                if thumb_img:
                    screen.blit(thumb_img, thumb_rect)
                else:
                    # Ícone de placeholder
                    pygame.draw.rect(screen, Theme.BORDER, thumb_rect.inflate(-12, -12), border_radius=2)

                # Título e Nome do Arquivo
                t_name = get_font(13, bold=True).render(slabel, True, Theme.TEXT_PRIMARY)
                screen.blit(t_name, (thumb_rect.right + 12, r_rect.y + 5))
                
                fname = os.path.basename(paths[skey]) if paths.get(skey) else "Pendente (não configurado)"
                f_color = Theme.TEXT_SECONDARY if paths.get(skey) else Theme.TEXT_MUTED
                t_f = get_font(11).render(fname[:45] + ("..." if len(fname) > 45 else ""), True, f_color)
                screen.blit(t_f, (thumb_rect.right + 12, r_rect.y + 22))

                # Botão Selecionar / Alterar
                h_btn = btn_choose.collidepoint(mouse_pos)
                b_text = "Alterar" if paths.get(skey) else "Escolher"
                draw_card(screen, btn_choose, border_color=Theme.BORDER_LIGHT if h_btn else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_btn else Theme.BTN_NEUTRAL, radius=6)
                t_b = get_font(12).render(b_text, True, Theme.TEXT_PRIMARY)
                screen.blit(t_b, t_b.get_rect(center=btn_choose.center))
                if h_row: hover_clickable = True

            # CARD 2: Áudio & Microfone
            draw_card(screen, card_audio_rect, radius=12)
            screen.blit(font_card_title.render("Áudio & Microfone", True, Theme.TEXT_PRIMARY), (card_audio_rect.x + 16, card_audio_rect.y + 14))

            # Seletor de Microfone (Dropdown trigger)
            h_dev = btn_device.collidepoint(mouse_pos)
            draw_card(screen, btn_device, border_color=Theme.BORDER_LIGHT if h_dev else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_dev else Theme.CARD_INNER, radius=8)
            
            dev_name = "Nenhum microfone detectado"
            if input_devices and 0 <= current_device_list_index < len(input_devices):
                dev_name = input_devices[current_device_list_index][1].get('display_name', 'Microfone')
            dev_name_crop = dev_name[:65] + ("..." if len(dev_name) > 65 else "")
            
            # Ícone vetorial de microfone
            mic_x = btn_device.x + 18
            mic_y = btn_device.centery
            pygame.draw.rect(screen, Theme.TEXT_SECONDARY, (mic_x - 3, mic_y - 7, 6, 9), border_radius=3)
            pygame.draw.arc(screen, Theme.TEXT_SECONDARY, (mic_x - 6, mic_y - 4, 12, 10), math.pi, 2 * math.pi, 2)
            pygame.draw.line(screen, Theme.TEXT_SECONDARY, (mic_x, mic_y + 6), (mic_x, mic_y + 9), 2)
            
            t_dev = get_font(13).render(dev_name_crop, True, Theme.TEXT_PRIMARY)
            screen.blit(t_dev, (mic_x + 14, btn_device.y + 10))
            
            arrow_icon = "▲" if dropdown_open else "▼"
            t_arrow = get_font(11).render(arrow_icon, True, Theme.TEXT_SECONDARY)
            screen.blit(t_arrow, (btn_device.right - 20, btn_device.y + 12))

            # Botão Atualizar Microfones (com ícone ↻)
            h_ref = btn_refresh_devices.collidepoint(mouse_pos)
            draw_card(screen, btn_refresh_devices, border_color=Theme.BORDER_LIGHT if h_ref else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_ref else Theme.CARD_INNER, radius=8)
            draw_icon_refresh(screen, btn_refresh_devices.center, 8, Theme.TEXT_PRIMARY)
            if h_dev or h_ref: hover_clickable = True

            # Medidor de Volume Integrado ao Slider de Sensibilidade
            lbl_sens = get_font(12).render("Sensibilidade & Nível de Entrada", True, Theme.TEXT_SECONDARY)
            screen.blit(lbl_sens, (slider_rect.x, slider_rect.y - 22))

            val_sens = get_font(12, bold=True).render(f"Limiar: {SOUND_THRESHOLD:.3f}", True, Theme.ACCENT if dragging_slider else Theme.TEXT_SECONDARY)
            screen.blit(val_sens, (slider_rect.right - val_sens.get_width(), slider_rect.y - 22))

            # Barra do Slider
            draw_card(screen, slider_rect, border_color=Theme.BORDER, bg_color=Theme.CARD_INNER, radius=slider_rect.height // 2)

            # Preenchimento dinâmico do áudio com gradiente suave
            visual_vol = min(1.0, current_volume / (SOUND_THRESHOLD * 4.0 + 0.001))
            meter_w = int(visual_vol * slider_rect.width)
            if meter_w > 0:
                meter_surf = pygame.Surface((meter_w, slider_rect.height), pygame.SRCALPHA)
                m_color = Theme.ACCENT_GREEN if visual_vol < 0.6 else (Theme.WARNING if visual_vol < 0.85 else Theme.DANGER)
                pygame.draw.rect(meter_surf, m_color, (0, 0, meter_w, slider_rect.height), border_radius=slider_rect.height // 2)
                screen.blit(meter_surf, (slider_rect.x, slider_rect.y))

            # Marcador / Knob do Limiar
            knob_x = slider_rect.x + int(((SOUND_THRESHOLD - 0.01) / 0.49) * slider_rect.width)
            knob_rect = pygame.Rect(knob_x - 8, slider_rect.y - 4, 16, slider_rect.height + 8)
            pygame.draw.rect(screen, (255, 255, 255), knob_rect, border_radius=4)
            pygame.draw.rect(screen, Theme.ACCENT if dragging_slider else Theme.BORDER_LIGHT, knob_rect, width=1, border_radius=4)

            # Linha vertical indicadora
            pygame.draw.line(screen, (255, 255, 255), (knob_x, slider_rect.y - 6), (knob_x, slider_rect.bottom + 6), 1)

            if slider_rect.inflate(0, 16).collidepoint(mouse_pos): hover_clickable = True

            # CARD 3: Ajustes de Renderização & Janela
            draw_card(screen, card_render_rect, radius=12)
            screen.blit(font_card_title.render("Ajustes de Renderização", True, Theme.TEXT_PRIMARY), (card_render_rect.x + 16, card_render_rect.y + 14))

            # Toggles Switches Modernos
            switches_data = [
                (btn_transparent, sw_transp_rect, "Janela Transparente", "Chroma Key para OBS", config.get('transparent_window', False)),
                (btn_borderless, sw_border_rect, "Sem Bordas", "Overlay sem moldura", config.get('borderless_window', False)),
                (btn_hard_edges, sw_hard_rect, "Contorno Sólido", "Sem semi-transparência", config.get('hard_edges', False)),
                (btn_animations, sw_anim_rect, "Animações", "Respiração e balanço", config.get('animations_enabled', True))
            ]

            for s_card, s_switch, title_str, sub_str, is_act in switches_data:
                h_sw = s_card.collidepoint(mouse_pos)
                draw_card(screen, s_card, border_color=Theme.BORDER_LIGHT if h_sw else Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
                screen.blit(get_font(13, bold=True).render(title_str, True, Theme.TEXT_PRIMARY), (s_card.x + 12, s_card.y + 6))
                screen.blit(get_font(11).render(sub_str, True, Theme.TEXT_MUTED), (s_card.x + 12, s_card.y + 23))
                draw_toggle_switch(screen, s_switch, is_act, hover=h_sw)
                if h_sw: hover_clickable = True

            # Botão Cor do Fundo com Swatch
            h_bgc = btn_bg_color.collidepoint(mouse_pos)
            draw_card(screen, btn_bg_color, border_color=Theme.BORDER_LIGHT if h_bgc else Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
            
            # Swatch de cor circular
            swatch_rect = pygame.Rect(btn_bg_color.x + 12, btn_bg_color.y + 12, 24, 24)
            pygame.draw.ellipse(screen, config['bg_color'], swatch_rect)
            pygame.draw.ellipse(screen, (255, 255, 255), swatch_rect, width=1)
            
            screen.blit(get_font(13, bold=True).render("Cor do Fundo", True, Theme.TEXT_PRIMARY), (swatch_rect.right + 12, btn_bg_color.y + 7))
            screen.blit(get_font(11).render("Clique para selecionar cor", True, Theme.TEXT_MUTED), (swatch_rect.right + 12, btn_bg_color.y + 25))
            if h_bgc: hover_clickable = True

            # Segmented Control para FPS: [ 30 | 60 | 120 ]
            draw_card(screen, fps_card_rect, border_color=Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
            screen.blit(get_font(13, bold=True).render("Taxa de FPS", True, Theme.TEXT_PRIMARY), (fps_card_rect.x + 12, fps_card_rect.y + 14))

            # Segmented control pill
            draw_card(screen, fps_seg_rect, border_color=Theme.BORDER, bg_color=Theme.BTN_NEUTRAL, radius=6)
            seg_w = fps_seg_rect.width / len(fps_opts)
            cur_fps = config.get('fps_limit', 60)
            
            for f_idx, f_val in enumerate(fps_opts):
                opt_rect = pygame.Rect(fps_seg_rect.x + int(f_idx * seg_w), fps_seg_rect.y, int(seg_w), fps_seg_rect.height)
                is_sel = (f_val == cur_fps)
                if is_sel:
                    pygame.draw.rect(screen, Theme.ACCENT, opt_rect, border_radius=6)
                h_opt = opt_rect.collidepoint(mouse_pos)
                if h_opt and not is_sel:
                    pygame.draw.rect(screen, Theme.BTN_HOVER, opt_rect, border_radius=6)
                    hover_clickable = True
                f_txt = get_font(12, bold=is_sel).render(str(f_val), True, (255, 255, 255) if is_sel else Theme.TEXT_SECONDARY)
                screen.blit(f_txt, f_txt.get_rect(center=opt_rect.center))

            # 4. DROPDOWN DE DISPOSITIVOS FLUTUANTE (Camada Superior)
            if dropdown_open and input_devices:
                draw_card(screen, dropdown_rect, border_color=Theme.BORDER_LIGHT, bg_color=Theme.PANEL, radius=8)
                for d_i in range(visible_dev_count):
                    real_idx = device_scroll_offset + d_i
                    if real_idx >= len(input_devices): break
                    d_rect = pygame.Rect(dropdown_rect.x + 4, dropdown_rect.y + 4 + d_i * device_item_h, dropdown_rect.width - 8, device_item_h)
                    is_cur = (real_idx == current_device_list_index)
                    h_item = d_rect.collidepoint(mouse_pos)
                    
                    if is_cur:
                        pygame.draw.rect(screen, (38, 42, 58), d_rect, border_radius=6)
                    elif h_item:
                        pygame.draw.rect(screen, Theme.BTN_HOVER, d_rect, border_radius=6)
                    
                    dev_lbl = input_devices[real_idx][1].get('display_name', 'Mic')[:75]
                    d_txt = get_font(12, bold=is_cur).render(dev_lbl, True, Theme.ACCENT if is_cur else Theme.TEXT_PRIMARY)
                    screen.blit(d_txt, (d_rect.x + 10, d_rect.y + 9))
                    if h_item: hover_clickable = True

            # 5. NOTIFICAÇÃO FLUTUANTE (Toast)
            if notification_text and current_time - notification_time < 3.5:
                is_err = any(w in notification_text.lower() for w in ["erro", "ausente", "removida", "inválido", "instale"])
                notif_bg = Theme.DANGER_BG if is_err else (16, 50, 35)
                notif_border = Theme.DANGER if is_err else Theme.ACCENT_GREEN
                notif_color = (255, 120, 120) if is_err else Theme.ACCENT_GREEN
                
                n_surf = get_font(13, bold=True).render(notification_text, True, notif_color)
                toast_rect = pygame.Rect(0, 0, n_surf.get_width() + 32, 38)
                toast_rect.center = (SCREEN_WIDTH // 2, 34)
                
                draw_card(screen, toast_rect, border_color=notif_border, bg_color=notif_bg, radius=19)
                screen.blit(n_surf, n_surf.get_rect(center=toast_rect.center))

            # 6. MODAL DE ATUALIZAÇÃO DO PYTUBER
            if show_update_modal and current_state == "MENU":
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 190))
                screen.blit(overlay, (0, 0))

                modal_w, modal_h = 560, 370
                modal_rect = pygame.Rect((SCREEN_WIDTH - modal_w) // 2, (SCREEN_HEIGHT - modal_h) // 2, modal_w, modal_h)
                draw_card(screen, modal_rect, border_color=Theme.BORDER_LIGHT, bg_color=Theme.PANEL, radius=12)

                # Header do Modal
                title_font = get_font(16, bold=True)
                screen.blit(title_font.render("Atualização Disponível!", True, Theme.TEXT_PRIMARY), (modal_rect.x + 24, modal_rect.y + 18))
                
                v_badge_txt = f"v{GLOBAL_UPDATE_INFO.latest_version}"
                draw_badge(screen, modal_rect.x + 230, modal_rect.y + 16, v_badge_txt, (255, 255, 255), Theme.ACCENT_GREEN, radius=4)

                # Botão Fechar [✕]
                btn_modal_close = pygame.Rect(modal_rect.right - 36, modal_rect.y + 14, 22, 22)
                h_close = btn_modal_close.collidepoint(mouse_pos)
                if h_close:
                    pygame.draw.rect(screen, Theme.BTN_HOVER, btn_modal_close, border_radius=4)
                    hover_clickable = True
                screen.blit(get_font(12, bold=True).render("✕", True, Theme.TEXT_SECONDARY), (btn_modal_close.x + 6, btn_modal_close.y + 4))

                # Subtítulo
                sub_txt = f"Versão atual: v{APP_VERSION}  •  Nova versão: v{GLOBAL_UPDATE_INFO.latest_version}"
                screen.blit(get_font(12).render(sub_txt, True, Theme.TEXT_SECONDARY), (modal_rect.x + 24, modal_rect.y + 44))

                # Caixa de Changelog
                changelog_rect = pygame.Rect(modal_rect.x + 24, modal_rect.y + 68, modal_rect.width - 48, 220)
                draw_card(screen, changelog_rect, border_color=Theme.BORDER, bg_color=Theme.CARD_INNER, radius=8)
                
                screen.blit(get_font(12, bold=True).render("Novidades e Notas da Versão:", True, Theme.ACCENT), (changelog_rect.x + 14, changelog_rect.y + 12))
                
                # Renderiza linhas do changelog
                raw_lines = (GLOBAL_UPDATE_INFO.changelog or "Melhorias de estabilidade e novas funcionalidades.").split('\n')
                y_offset = changelog_rect.y + 36
                for line in raw_lines[:9]:
                    if not line.strip(): continue
                    c_txt = get_font(11).render(line[:68], True, Theme.TEXT_PRIMARY)
                    screen.blit(c_txt, (changelog_rect.x + 14, y_offset))
                    y_offset += 18
                    if y_offset > changelog_rect.bottom - 22:
                        break

                # Ações de acordo com o status
                btn_modal_cancel = pygame.Rect(modal_rect.right - 310, modal_rect.bottom - 52, 120, 36)
                btn_modal_action = pygame.Rect(modal_rect.right - 176, modal_rect.bottom - 52, 152, 36)
                
                if GLOBAL_UPDATE_INFO.status == UpdateStatus.AVAILABLE:
                    h_cancel = btn_modal_cancel.collidepoint(mouse_pos)
                    draw_card(screen, btn_modal_cancel, border_color=Theme.BORDER_LIGHT if h_cancel else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_cancel else Theme.BTN_NEUTRAL, radius=6)
                    t_can = get_font(12).render("Mais Tarde", True, Theme.TEXT_SECONDARY)
                    screen.blit(t_can, t_can.get_rect(center=btn_modal_cancel.center))

                    h_upd = btn_modal_action.collidepoint(mouse_pos)
                    draw_card(screen, btn_modal_action, border_color=None, bg_color=Theme.ACCENT_GREEN_HOVER if h_upd else Theme.ACCENT_GREEN, radius=6)
                    t_upd = get_font(12, bold=True).render("Atualizar Agora", True, (255, 255, 255))
                    screen.blit(t_upd, t_upd.get_rect(center=btn_modal_action.center))
                    if h_cancel or h_upd: hover_clickable = True

                elif GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADING:
                    bar_rect = pygame.Rect(modal_rect.x + 24, modal_rect.bottom - 46, modal_rect.width - 48, 10)
                    pygame.draw.rect(screen, Theme.CARD_INNER, bar_rect, border_radius=5)
                    prog_w = int(bar_rect.width * GLOBAL_UPDATE_INFO.progress)
                    if prog_w > 0:
                        pygame.draw.rect(screen, Theme.ACCENT_GREEN, (bar_rect.x, bar_rect.y, prog_w, bar_rect.height), border_radius=5)
                    
                    prog_label = f"Baixando instalador: {int(GLOBAL_UPDATE_INFO.progress * 100)}% ({GLOBAL_UPDATE_INFO.downloaded_bytes // 1024} KB / {GLOBAL_UPDATE_INFO.total_bytes // 1024} KB)..."
                    screen.blit(get_font(11).render(prog_label, True, Theme.TEXT_SECONDARY), (bar_rect.x, bar_rect.y - 18))

                elif GLOBAL_UPDATE_INFO.status == UpdateStatus.DOWNLOADED:
                    btn_inst = pygame.Rect(modal_rect.right - 210, modal_rect.bottom - 52, 186, 36)
                    h_inst = btn_inst.collidepoint(mouse_pos)
                    draw_card(screen, btn_inst, border_color=None, bg_color=Theme.ACCENT_HOVER if h_inst else Theme.ACCENT, radius=6)
                    t_inst = get_font(12, bold=True).render("Reiniciar e Instalar", True, (255, 255, 255))
                    screen.blit(t_inst, t_inst.get_rect(center=btn_inst.center))
                    if h_inst: hover_clickable = True

                elif GLOBAL_UPDATE_INFO.status == UpdateStatus.ERROR:
                    err_txt = f"Falha: {GLOBAL_UPDATE_INFO.error_message[:45]}"
                    screen.blit(get_font(11).render(err_txt, True, Theme.DANGER), (modal_rect.x + 24, modal_rect.bottom - 44))
                    btn_close_err = pygame.Rect(modal_rect.right - 120, modal_rect.bottom - 52, 96, 36)
                    h_err = btn_close_err.collidepoint(mouse_pos)
                    draw_card(screen, btn_close_err, border_color=Theme.BORDER, bg_color=Theme.BTN_HOVER if h_err else Theme.BTN_NEUTRAL, radius=6)
                    t_err = get_font(12).render("Fechar", True, Theme.TEXT_PRIMARY)
                    screen.blit(t_err, t_err.get_rect(center=btn_close_err.center))
                    if h_err: hover_clickable = True

        elif current_state == "POSITIONING":
            # Modo de Posições Moderno
            screen.fill(Theme.BG)
            
            # Grade suave de referência
            for gx in range(0, SCREEN_WIDTH, 80):
                pygame.draw.line(screen, (24, 24, 30), (gx, 0), (gx, SCREEN_HEIGHT), 1)
            for gy in range(0, SCREEN_HEIGHT, 80):
                pygame.draw.line(screen, (24, 24, 30), (0, gy), (SCREEN_WIDTH, gy), 1)

            char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
            draw_avatar(char_center, force_m=True)

            # Anchor Point no centro do personagem base
            draw_anchor_point(screen, char_center, color=(56, 189, 248), radius=9, label="Âncora Base")

            # Destaque da parte selecionada e alinhamento com a âncora
            selected_part_name = parts_list[editing_part_index]
            highlight_rect = None
            if selected_part_name == 'char' and 'char' in images and images['char']:
                highlight_rect = images['char'].get_rect(center=char_center)
                draw_badge(screen, char_center[0] + 16, char_center[1] + 16, f"Offset Global: ({offsets['char'][0]}, {offsets['char'][1]})", Theme.TEXT_PRIMARY, Theme.CARD_INNER, border_color=(56, 189, 248), radius=4)
            elif selected_part_name == 'eyes' and 'eyes_open' in images and images['eyes_open']:
                part_c = (char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])
                highlight_rect = images['eyes_open'].get_rect(center=part_c)
                pygame.draw.line(screen, (56, 189, 248), char_center, part_c, 1)
                draw_anchor_point(screen, part_c, color=Theme.ACCENT, radius=6, label=f"Olhos: ΔX {offsets['eyes'][0]} | ΔY {offsets['eyes'][1]}")
            elif selected_part_name == 'mouth' and 'mouth_open' in images and images['mouth_open']:
                part_c = (char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])
                highlight_rect = images['mouth_open'].get_rect(center=part_c)
                pygame.draw.line(screen, (56, 189, 248), char_center, part_c, 1)
                draw_anchor_point(screen, part_c, color=Theme.ACCENT, radius=6, label=f"Boca: ΔX {offsets['mouth'][0]} | ΔY {offsets['mouth'][1]}")

            if highlight_rect:
                pygame.draw.rect(screen, Theme.ACCENT, highlight_rect.inflate(8, 8), width=2, border_radius=6)

            # Barra Superior Flutuante
            draw_card(screen, pos_top_bar, radius=10)
            screen.blit(get_font(14, bold=True).render("Ajuste de Posições", True, Theme.TEXT_PRIMARY), (pos_top_bar.x + 16, pos_top_bar.y + 14))

            # Tabs de Peças [ Personagem | Olhos | Boca ]
            tab_names = ["Personagem", "Olhos", "Boca"]
            for t_i, t_name in enumerate(tab_names):
                t_box = pos_tab_rects[t_i]
                is_sel = (t_i == editing_part_index)
                if is_sel:
                    pygame.draw.rect(screen, Theme.ACCENT, t_box, border_radius=6)
                else:
                    pygame.draw.rect(screen, Theme.BTN_NEUTRAL, t_box, border_radius=6)
                t_lbl = get_font(12, bold=is_sel).render(t_name, True, (255, 255, 255) if is_sel else Theme.TEXT_SECONDARY)
                screen.blit(t_lbl, t_lbl.get_rect(center=t_box.center))
                if t_box.collidepoint(mouse_pos): hover_clickable = True

            # Botão Salvar e Voltar
            h_ps = btn_positioning_save.collidepoint(mouse_pos)
            draw_card(screen, btn_positioning_save, border_color=None, bg_color=Theme.ACCENT_GREEN_HOVER if h_ps else Theme.ACCENT_GREEN, radius=6)
            t_ps = get_font(13, bold=True).render("✓ Salvar e Voltar", True, (255, 255, 255))
            screen.blit(t_ps, t_ps.get_rect(center=btn_positioning_save.center))
            if h_ps: hover_clickable = True

            # Card Inferior de Instruções
            bottom_bar = pygame.Rect((SCREEN_WIDTH - 760) // 2, SCREEN_HEIGHT - 54, 760, 38)
            draw_card(screen, bottom_bar, radius=8)
            hint_txt = f"Arraste as peças com o Mouse  •  Setas para ajuste fino  •  Scroll para Zoom ({config.get('char_scale', 1.0):.2f}x)  •  Ctrl+Z = Desfazer"
            t_hint = get_font(12).render(hint_txt, True, Theme.TEXT_SECONDARY)
            screen.blit(t_hint, t_hint.get_rect(center=bottom_bar.center))

        elif current_state == "WARDROBE":
            # Guarda-Roupa Moderno
            screen.fill(Theme.BG)
            
            # Painel Lateral
            panel_rect = pygame.Rect(0, 0, wardrobe_panel_width, SCREEN_HEIGHT)
            draw_card(screen, panel_rect, radius=0)

            # Botões do Painel
            h_aw = btn_add_w.collidepoint(mouse_pos)
            h_bw = btn_back_w.collidepoint(mouse_pos)
            draw_card(screen, btn_add_w, border_color=None, bg_color=Theme.ACCENT_HOVER if h_aw else Theme.ACCENT, radius=6)
            draw_card(screen, btn_back_w, border_color=Theme.BORDER_LIGHT if h_bw else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_bw else Theme.BTN_NEUTRAL, radius=6)
            
            screen.blit(get_font(13, bold=True).render("+ Adicionar Roupa", True, (255, 255, 255)), (btn_add_w.x + 16, btn_add_w.y + 9))
            screen.blit(get_font(13).render("← Voltar", True, Theme.TEXT_PRIMARY), (btn_back_w.x + 30, btn_back_w.y + 9))
            if h_aw or h_bw: hover_clickable = True

            # Lista em Acordeão
            layout = get_wardrobe_layout(config, wardrobe_scroll, wardrobe_collapsed_cats)
            for node in layout:
                if node['type'] == 'header':
                    if 68 <= node['rect'].y <= SCREEN_HEIGHT:
                        h_cat = node['rect'].collidepoint(mouse_pos)
                        draw_card(screen, node['rect'], border_color=Theme.BORDER_LIGHT if h_cat else Theme.BORDER, bg_color=Theme.CARD_INNER, radius=6)
                        indicator = "+" if node['cat'] in wardrobe_collapsed_cats else "-"
                        cat_title = node['cat'].replace('_', ' ').title()
                        screen.blit(get_font(13, bold=True).render(f"{indicator}  {cat_title}", True, Theme.TEXT_PRIMARY), (node['rect'].x + 14, node['rect'].y + 11))
                        draw_badge(screen, node['rect'].right - 50, node['rect'].y + 8, str(node['count']), Theme.TEXT_SECONDARY, Theme.BTN_NEUTRAL)
                        if h_cat: hover_clickable = True

                elif node['type'] == 'item':
                    item_y = node['y']
                    if item_y < 68 or item_y > SCREEN_HEIGHT: continue
                    item = node['item']
                    cat = node['cat']
                    idx_in_cat = node['idx_in_cat']
                    total_in_cat = node['total_in_cat']
                    is_selected = (item.get('id') == wardrobe_selected_item_id)

                    rects = get_wardrobe_item_rects(item_y)
                    i_rect = rects['card']
                    
                    # Highlight suave se selecionado
                    bg_col = (34, 34, 44) if is_selected else Theme.BTN_NEUTRAL
                    bdr_col = Theme.ACCENT if is_selected else Theme.BORDER
                    draw_card(screen, i_rect, border_color=bdr_col, bg_color=bg_col, radius=6)

                    # Toggle Ativo
                    sw_active = rects['active']
                    h_act = sw_active.collidepoint(mouse_pos)
                    draw_toggle_switch(screen, sw_active, item.get('active', True), hover=h_act)
                    if h_act: hover_clickable = True

                    # Nome do Item
                    nm = item.get('name', '')[:13]
                    screen.blit(get_font(13, bold=True).render(nm, True, Theme.TEXT_PRIMARY if item.get('active', True) else Theme.TEXT_MUTED), (sw_active.right + 10, i_rect.y + 12))

                    # Botão Trava (Lock)
                    btn_lk = rects['lock']
                    is_lk = item.get('locked', False)
                    h_lk = btn_lk.collidepoint(mouse_pos)
                    draw_card(screen, btn_lk, border_color=Theme.BORDER_LIGHT if h_lk else Theme.BORDER, bg_color=Theme.DANGER_BG if is_lk else (Theme.BTN_HOVER if h_lk else Theme.CARD_INNER), radius=4)
                    draw_icon_lock(screen, btn_lk.center, is_lk, Theme.DANGER if is_lk else Theme.TEXT_SECONDARY)
                    if h_lk: hover_clickable = True

                    # Botão Camada (F / M / T)
                    current_layer = item.get('layer', get_default_layer(cat))
                    btn_ly = rects['layer']
                    h_ly = btn_ly.collidepoint(mouse_pos)
                    ly_code = "F" if current_layer == 'frente' else ("M" if current_layer == 'meio' else "T")
                    ly_bg = (55, 45, 20) if current_layer == 'frente' else ((45, 25, 55) if current_layer == 'meio' else (20, 40, 55))
                    draw_card(screen, btn_ly, border_color=Theme.BORDER_LIGHT if h_ly else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_ly else ly_bg, radius=4)
                    t_ly = get_font(12, bold=True).render(ly_code, True, Theme.TEXT_PRIMARY)
                    screen.blit(t_ly, t_ly.get_rect(center=btn_ly.center))
                    if h_ly: hover_clickable = True

                    # Reordenar (▲ / ▼)
                    btn_up = rects['up']
                    btn_dn = rects['down']
                    h_up = btn_up.collidepoint(mouse_pos)
                    h_dn = btn_dn.collidepoint(mouse_pos)
                    draw_card(screen, btn_up, border_color=Theme.BORDER_LIGHT if h_up else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_up else Theme.CARD_INNER, radius=4)
                    draw_card(screen, btn_dn, border_color=Theme.BORDER_LIGHT if h_dn else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_dn else Theme.CARD_INNER, radius=4)
                    screen.blit(get_font(10).render("▲", True, Theme.TEXT_SECONDARY if idx_in_cat > 0 else Theme.TEXT_MUTED), (btn_up.x + 9, btn_up.y + 7))
                    screen.blit(get_font(10).render("▼", True, Theme.TEXT_SECONDARY if idx_in_cat < total_in_cat - 1 else Theme.TEXT_MUTED), (btn_dn.x + 9, btn_dn.y + 7))
                    if h_up or h_dn: hover_clickable = True

                    # Editar (Bootstrap Pencil) e Excluir (Bootstrap Trash)
                    btn_ed = rects['edit']
                    btn_rm = rects['delete']
                    h_ed = btn_ed.collidepoint(mouse_pos)
                    h_rm = btn_rm.collidepoint(mouse_pos)
                    draw_card(screen, btn_ed, border_color=Theme.BORDER_LIGHT if h_ed else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_ed else Theme.CARD_INNER, radius=4)
                    draw_card(screen, btn_rm, border_color=Theme.DANGER if h_rm else Theme.BORDER, bg_color=Theme.DANGER_BG if h_rm else (45, 20, 20), radius=4)
                    draw_bootstrap_pencil(screen, btn_ed.center, size=14, color=Theme.TEXT_PRIMARY if not h_ed else (255, 255, 255))
                    draw_bootstrap_trash(screen, btn_rm.center, size=14, color=Theme.DANGER if not h_rm else (255, 100, 100))
                    if h_ed or h_rm or i_rect.collidepoint(mouse_pos): hover_clickable = True

            # Preview no Guarda-Roupa
            preview_center_x = wardrobe_panel_width + (SCREEN_WIDTH - wardrobe_panel_width) // 2
            char_center = (preview_center_x + config['offsets']['char'][0], SCREEN_HEIGHT // 2 + config['offsets']['char'][1])
            draw_avatar(char_center, force_m=True)

            # Anchor Point no centro do personagem base
            draw_anchor_point(screen, char_center, color=(56, 189, 248), radius=9, label="Âncora Base")

            # Barra Superior Flutuante e Indicador do item selecionado
            if wardrobe_selected_item_id:
                for item in config.get('wardrobe', []):
                    if item['id'] == wardrobe_selected_item_id and item.get('active') and item['id'] in wardrobe_images:
                        item_center = (char_center[0] + item['offset'][0], char_center[1] + item['offset'][1])
                        img_w, img_h = wardrobe_images[item['id']].get_size()
                        scale = item.get('scale', 1.0)
                        hl_rect = pygame.Rect(0, 0, max(1, int(img_w * scale)), max(1, int(img_h * scale)))
                        hl_rect.center = item_center
                        pygame.draw.rect(screen, Theme.ACCENT, hl_rect, width=2, border_radius=4)
                        
                        # Linha guia conectando a âncora ao acessório
                        pygame.draw.line(screen, (56, 189, 248, 160), char_center, item_center, 1)
                        draw_anchor_point(screen, item_center, color=Theme.ACCENT, radius=6, label=f"Δ ({item['offset'][0]}, {item['offset'][1]})")

                        # Barra Superior Flutuante com Controles de Escala completos
                        w_bar = pygame.Rect(wardrobe_panel_width + 20, 16, SCREEN_WIDTH - wardrobe_panel_width - 40, 52)
                        draw_card(screen, w_bar, radius=8)
                        screen.blit(get_font(13, bold=True).render(f"Acessório: {item['name']}", True, Theme.TEXT_PRIMARY), (w_bar.x + 16, w_bar.y + 11))
                        
                        offset_txt = f"X: {item['offset'][0]}px | Y: {item['offset'][1]}px  (Arraste ou use setas)"
                        screen.blit(get_font(11).render(offset_txt, True, Theme.TEXT_MUTED), (w_bar.x + 16, w_bar.y + 30))

                        # Botões e Slider de Escala à direita
                        btn_sc_reset = pygame.Rect(w_bar.right - 58, w_bar.y + 11, 44, 30)
                        btn_sc_plus = pygame.Rect(btn_sc_reset.left - 38, w_bar.y + 11, 32, 30)
                        slider_sc_w = 110
                        slider_sc_rect = pygame.Rect(btn_sc_plus.left - slider_sc_w - 10, w_bar.y + 22, slider_sc_w, 8)
                        btn_sc_minus = pygame.Rect(slider_sc_rect.left - 42, w_bar.y + 11, 32, 30)

                        h_minus = btn_sc_minus.collidepoint(mouse_pos)
                        h_plus = btn_sc_plus.collidepoint(mouse_pos)
                        h_rst = btn_sc_reset.collidepoint(mouse_pos)
                        h_sld = slider_sc_rect.inflate(10, 16).collidepoint(mouse_pos)

                        # Botão Menos
                        draw_card(screen, btn_sc_minus, border_color=Theme.BORDER_LIGHT if h_minus else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_minus else Theme.CARD_INNER, radius=4)
                        screen.blit(get_font(14, bold=True).render("-", True, Theme.TEXT_PRIMARY), get_font(14, bold=True).render("-", True, Theme.TEXT_PRIMARY).get_rect(center=btn_sc_minus.center))

                        # Barra de Slider
                        pygame.draw.rect(screen, Theme.CARD_INNER, slider_sc_rect, border_radius=4)
                        sc_norm = max(0.0, min(1.0, (scale - 0.1) / (3.0 - 0.1)))
                        sc_fill_w = int(slider_sc_rect.width * sc_norm)
                        if sc_fill_w > 0:
                            pygame.draw.rect(screen, Theme.ACCENT, (slider_sc_rect.x, slider_sc_rect.y, sc_fill_w, slider_sc_rect.height), border_radius=4)
                        handle_x = slider_sc_rect.x + sc_fill_w
                        pygame.draw.circle(screen, (255, 255, 255), (handle_x, slider_sc_rect.centery), 6)

                        # Botão Mais
                        draw_card(screen, btn_sc_plus, border_color=Theme.BORDER_LIGHT if h_plus else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_plus else Theme.CARD_INNER, radius=4)
                        screen.blit(get_font(14, bold=True).render("+", True, Theme.TEXT_PRIMARY), get_font(14, bold=True).render("+", True, Theme.TEXT_PRIMARY).get_rect(center=btn_sc_plus.center))

                        # Botão Reset
                        draw_card(screen, btn_sc_reset, border_color=Theme.BORDER_LIGHT if h_rst else Theme.BORDER, bg_color=Theme.BTN_HOVER if h_rst else Theme.CARD_INNER, radius=4)
                        screen.blit(get_font(11, bold=True).render("1.0x", True, Theme.TEXT_SECONDARY), get_font(11, bold=True).render("1.0x", True, Theme.TEXT_SECONDARY).get_rect(center=btn_sc_reset.center))

                        # Label de Escala
                        sc_lbl = get_font(12, bold=True).render(f"Escala: {scale:.2f}x", True, Theme.TEXT_PRIMARY)
                        screen.blit(sc_lbl, (btn_sc_minus.left - sc_lbl.get_width() - 12, w_bar.y + 17))

                        if h_minus or h_plus or h_rst or h_sld:
                            hover_clickable = True
                        break

        elif current_state == "RUNNING":
            # Modo RUNNING (Avatar ao vivo)
            force_eyes, force_mouth, cycle_profile_pressed = check_global_hotkeys()
            
            if cycle_profile_pressed and not last_cycle_profile_pressed:
                profiles = [f for f in os.listdir() if f.endswith('.json') and f != CONFIG_FILE]
                if profiles:
                    current_profile_index = (current_profile_index + 1) % len(profiles)
                    profile_to_load = profiles[current_profile_index]
                    try:
                        with open(profile_to_load, 'r') as f:
                            config.update(json.load(f))
                        save_config(config)
                        paths = config['paths']
                        offsets = config['offsets']
                        SOUND_THRESHOLD = config.get('sound_threshold', 0.1)
                        wardrobe_images.clear()
                        load_wardrobe_images(config, wardrobe_images)
                        images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                        
                        if vcam:
                            vcam.close()
                            vcam = None
                        if config.get('virtual_camera', False) and HAS_VIRTUALCAM:
                            try:
                                vcam = pyvirtualcam.Camera(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, fps=config.get('fps_limit', 60), fmt=pyvirtualcam.PixelFormat.RGB)
                            except Exception:
                                vcam = None

                        if config.get('audio_device') != selected_device_idx:
                            selected_device_idx = config.get('audio_device')
                            start_audio_stream(selected_device_idx)
                            
                        if config.get('borderless_window', False):
                            screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
                        else:
                            screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                        set_window_transparency(config['bg_color'], config.get('transparent_window', False))

                        profile_notif_text = f"Perfil: {profile_to_load}"
                        profile_notif_time = current_time
                    except Exception as e:
                        print(f"Erro ao ciclar perfil: {e}")
                        
            last_cycle_profile_pressed = cycle_profile_pressed
            
            screen.fill(config['bg_color'])
            base_char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
            draw_avatar(base_char_center, anim_offset, force_eyes, force_mouth)

            # Notificação de Perfil no RUNNING
            if profile_notif_text and current_time - profile_notif_time < 2.0:
                p_surf = get_font(13, bold=True).render(profile_notif_text, True, Theme.TEXT_PRIMARY)
                p_rect = pygame.Rect(16, 16, p_surf.get_width() + 20, 32)
                draw_card(screen, p_rect, radius=6)
                screen.blit(p_surf, (p_rect.x + 10, p_rect.y + 7))

            # Envia o Frame para a Câmera Virtual
            if vcam:
                try:
                    frame = pygame.surfarray.array3d(screen)
                    frame = np.swapaxes(frame, 0, 1)
                    vcam.send(frame)
                except Exception:
                    pass

        # Cursor interativo moderno
        if current_state in ["MENU", "POSITIONING", "WARDROBE"]:
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hover_clickable else pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                pass

        pygame.display.flip()
        clock.tick(config.get('fps_limit', 60))

    if vcam:
        vcam.close()
    pygame.quit()

if __name__ == '__main__':
    main()
