import pygame
import ctypes
import sys
import sounddevice as sd
import numpy as np
import random
import tkinter as tk
from tkinter import filedialog
from tkinter import colorchooser
import time
import json
import os
import math
import shutil
import copy

try:
    import pyvirtualcam
    HAS_VIRTUALCAM = True
except ImportError:
    HAS_VIRTUALCAM = False

def resource_path(relative_path):
    """Obtém o caminho absoluto para o recurso, funciona para dev e para o executável do PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Configurações Iniciais ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
GREEN_BACKGROUND = (0, 255, 0)
FPS = 60

# --- Níveis de Áudio ---
SOUND_THRESHOLD = 0.1  # Ajuste este valor conforme a sensibilidade do seu microfone

# --- Configurações de Arquivo ---
CONFIG_FILE = 'config.json'

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
                # Garante que as chaves principais existam
                config.setdefault('paths', defaults['paths'])
                config.setdefault('offsets', defaults['offsets'])
                config.setdefault('audio_device', defaults['audio_device'])
                config.setdefault('sound_threshold', defaults['sound_threshold'])
                config.setdefault('bg_color', defaults['bg_color'])
                config.setdefault('transparent_window', defaults['transparent_window'])
                config.setdefault('borderless_window', defaults['borderless_window'])
                config.setdefault('animations_enabled', defaults['animations_enabled'])
                config.setdefault('fps_limit', defaults['fps_limit'])
                config.setdefault('wardrobe', defaults['wardrobe'])
                config.setdefault('char_scale', defaults['char_scale'])
                config.setdefault('hard_edges', defaults['hard_edges'])
                config.setdefault('virtual_camera', defaults['virtual_camera'])
                # Garante que as sub-chaves existam
                for part in defaults['offsets']:
                    config['offsets'].setdefault(part, defaults['offsets'][part])
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
    
    # Só copia se a origem e o destino forem caminhos diferentes
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
next_blink_interval = random.uniform(2, 6) # Piscar a cada 2-6 segundos
current_volume = 0.0
audio_stream = None

def audio_callback(indata, frames, time, status):
    """
    Callback para processar o áudio do microfone.
    Verifica se o volume do som ultrapassa um limiar.
    """
    global is_speaking, current_volume
    if status:
        print(f"Status de áudio: {status}")
    volume_norm = np.linalg.norm(indata) * 10
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
                except:
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
            # Constantes da API do Windows
            WS_EX_LAYERED = 0x00080000
            GWL_EXSTYLE = -20
            LWA_COLORKEY = 0x00000001
            
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enable:
                # Adiciona o atributo de janela em camadas
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
                # A API espera cor no formato 0x00bbggrr
                color_ref = color[0] | (color[1] << 8) | (color[2] << 16)
                ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_ref, 0, LWA_COLORKEY)
            else:
                # Remove o atributo de janela em camadas
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        except Exception as e:
            print(f"Erro ao definir transparência da janela: {e}")

def check_global_hotkeys():
    """Verifica atalhos globais no Windows usando ctypes (funciona sem foco na janela)."""
    if sys.platform == 'win32':
        # Códigos VK: 0x11 = CTRL, 0x42 = B, 0x4D = M
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
    """Abre um formulário Tkinter para adicionar ou editar um item do guarda-roupa."""
    root = tk.Tk()
    root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("Item do Guarda-Roupa")
    dialog.attributes('-topmost', True)
    dialog.geometry("400x380")
    
    result = None
    
    tk.Label(dialog, text="Nome:").pack(pady=5)
    name_var = tk.StringVar(value=item['name'] if item else "")
    tk.Entry(dialog, textvariable=name_var).pack()
    
    tk.Label(dialog, text="Categoria:").pack(pady=5)
    categories = ["chapéus", "acessórios", "maquiagem", "calças", "casacos", "camisas", "objetos_de_cena", "cor_dos_olhos"]
    cat_var = tk.StringVar(value=item['category'] if item else categories[0])
    tk.OptionMenu(dialog, cat_var, *categories).pack()
    
    tk.Label(dialog, text="Camada (Frente/Meio/Trás):").pack(pady=5)
    cat_val = item.get('category') if item else categories[0]
    default_layer = get_default_layer(cat_val)
    layer_var = tk.StringVar(value=item.get('layer', default_layer) if item else default_layer)
    tk.OptionMenu(dialog, layer_var, "frente", "meio", "trás").pack()
    
    tk.Label(dialog, text="Imagem (PNG):").pack(pady=5)
    path_var = tk.StringVar(value=item['path'] if item else "")
    path_label = tk.Label(dialog, textvariable=path_var, wraplength=350, fg="blue")
    path_label.pack()
    
    def choose_file():
        p = filedialog.askopenfilename(filetypes=[("Imagens PNG", "*.png")])
        if p: path_var.set(p)
        
    tk.Button(dialog, text="Selecionar Imagem", command=choose_file).pack(pady=5)
    
    def save():
        nonlocal result
        if not name_var.get() or not path_var.get(): return
        
        final_path = import_image_to_assets(path_var.get(), cat_var.get())
        
        result = {
            'name': name_var.get(),
            'category': cat_var.get(),
            'layer': layer_var.get(),
            'path': final_path,
            'offset': item.get('offset', [0, 0]) if item else [0, 0],
            'scale': item.get('scale', 1.0) if item else 1.0,
            'active': item.get('active', True) if item else True,
            'id': item['id'] if item else str(time.time())
        }
        dialog.destroy()
        
    tk.Button(dialog, text="Salvar", command=save, bg="lightgreen").pack(pady=15)
    dialog.wait_window()
    root.destroy()
    return result

def remove_soft_edges(img):
    """Transforma bordas semi-transparentes em sólidas para evitar contornos feios no ColorKey."""
    if img.get_flags() & pygame.SRCALPHA:
        alpha_array = pygame.surfarray.pixels_alpha(img)
        alpha_array[alpha_array < 127] = 0
        alpha_array[alpha_array >= 127] = 255
        del alpha_array # Libera a superfície
    return img

def load_wardrobe_images(config, dest_dict):
    """Carrega na memória as imagens ativas do guarda-roupa."""
    for item in config.get('wardrobe', []):
        if item['path'] and os.path.exists(item['path']):
            try:
                img = pygame.image.load(item['path']).convert_alpha()
                dest_dict[item['id']] = img
            except Exception as e:
                print(f"Erro imagem guarda-roupa: {e}")

def load_character_images_scaled(paths, max_w, max_h, manual_scale=1.0):
    """Carrega e ajusta a escala das imagens baseadas no tamanho da tela, evitando imagens gigantes."""
    images = {}
    char_path = paths.get("char")
    
    if not char_path or not os.path.exists(char_path):
        raise Exception("Imagem base (char) não encontrada.")
        
    char_img = pygame.image.load(char_path).convert_alpha()
    orig_w, orig_h = char_img.get_size()
    
    scale = 1.0
    # Calcula a escala se a imagem for maior que os limites
    if orig_w > max_w or orig_h > max_h:
        scale = min(max_w / orig_w, max_h / orig_h)
        
    final_scale = scale * manual_scale
        
    if final_scale != 1.0:
        char_img = pygame.transform.smoothscale(char_img, (max(1, int(orig_w * final_scale)), max(1, int(orig_h * final_scale))))
        
    images["char"] = char_img
    
    # Carrega as outras partes do rosto e aplica a MESMA escala
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
            'rect': pygame.Rect(20, draw_y, 420, 40),
            'count': len(cat_items)
        })
        draw_y += 45
        
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
                draw_y += 50
    return layout

def main():
    """Função principal que executa o loop do jogo."""
    global last_blink_time, next_blink_interval, is_blinking, SOUND_THRESHOLD

    pygame.init()

    # --- Configuração do Ícone da Janela ---
    try:
        icon_path = resource_path('icon.ico')
        if os.path.exists(icon_path):
            pygame.display.set_icon(pygame.image.load(icon_path))
    except Exception as e:
        print(f"Erro ao carregar o ícone: {e}")

    # --- Configuração da Janela ---
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pytuber V0.9")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    # --- Variáveis de Estado da Interface ---
    current_state = "MENU"
    config = load_config()
    SOUND_THRESHOLD = config.get('sound_threshold', 0.1)
    dropdown_open = False
    paths = config['paths']
    offsets = config['offsets']
    images = {}

    # Verificação de arquivos na inicialização
    missing_files = False
    for key, path in paths.items():
        if path and not os.path.exists(path):
            paths[key] = None
            missing_files = True
            
    if missing_files:
        save_config(config)
        
    notification_text = "Aviso: Imagens não encontradas foram removidas!" if missing_files else ""
    notification_time = time.time() if missing_files else 0

    # Variáveis do modo de posicionamento
    editing_part_index = 0
    parts_list = ['char', 'eyes', 'mouth']
    
    # Superfície para o Contorno Sólido
    composition_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

    # --- Sistema de Desfazer (Undo) ---
    undo_stack = []
    pre_drag_state = None
    last_continuous_action_time = 0
    
    def save_state_for_undo():
        state = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})
        undo_stack.append(state)
        if len(undo_stack) > 50:
            undo_stack.pop(0)

    # Botões da interface (posição x, posição y, largura, altura)
    btn_char = pygame.Rect(50, 50, 350, 40)
    btn_eyes_open = pygame.Rect(50, 110, 350, 40)
    btn_eyes_closed = pygame.Rect(50, 170, 350, 40)
    btn_mouth_open = pygame.Rect(50, 230, 350, 40)
    
    btn_device = pygame.Rect(50, 320, 600, 40)
    btn_refresh_devices = pygame.Rect(btn_device.right + 10, 320, 40, 40)
    slider_rect = pygame.Rect(50, 440, 500, 15)
    dragging_slider = False
    btn_start = pygame.Rect(50, 500, 170, 50)
    btn_positioning = pygame.Rect(230, 500, 170, 50)
    btn_load_profile = pygame.Rect(50, 560, 170, 50)
    btn_save_profile = pygame.Rect(230, 560, 170, 50)
    btn_bg_color = pygame.Rect(420, 500, 250, 50)
    btn_transparent = pygame.Rect(700, 500, 250, 50)
    btn_borderless = pygame.Rect(420, 560, 250, 50)
    btn_wardrobe = pygame.Rect(700, 560, 250, 50)
    btn_animations = pygame.Rect(420, 620, 250, 50)
    btn_fps = pygame.Rect(700, 620, 250, 50)
    btn_hard_edges = pygame.Rect(50, 620, 350, 50)
    btn_virtualcam = pygame.Rect(960, 500, 300, 50)
    btn_positioning_save = pygame.Rect(SCREEN_WIDTH - 270, SCREEN_HEIGHT - 70, 250, 50)
    
    # Calcula o tamanho dos botões dinamicamente baseado no texto (+30px de margem horizontal)
    add_w, add_h = font.size("Adicionar Roupa")
    btn_add_wardrobe = pygame.Rect(20, 20, add_w + 30, max(40, add_h + 20))
    back_w, back_h = font.size("Voltar ao Menu")
    btn_wardrobe_back = pygame.Rect(btn_add_wardrobe.right + 20, 20, back_w + 30, max(40, back_h + 20))
    wardrobe_panel_width = max(480, btn_wardrobe_back.right + 20)

    wardrobe_images = {}
    load_wardrobe_images(config, wardrobe_images)

    char_rect, eyes_rect, mouth_rect = None, None, None

    def get_file(title):
        """Abre o explorador de arquivos para escolher uma imagem."""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Garante que a janela fique por cima do pygame
        p = filedialog.askopenfilename(title=title, filetypes=[("Imagens PNG", "*.png")])
        root.destroy()
        return p

    # --- Áudio Setup ---
    input_devices = get_input_devices()
        
    selected_device_idx = config.get('audio_device')
    if selected_device_idx is not None and not any(i == selected_device_idx for i, d in input_devices):
        selected_device_idx = None
        
    if selected_device_idx is None and input_devices:
        try:
            selected_device_idx = sd.default.device[0]
        except:
            selected_device_idx = input_devices[0][0]

    current_device_list_index = 0
    for i, (idx, dev) in enumerate(input_devices):
        if idx == selected_device_idx:
            current_device_list_index = i
            break
            
    if input_devices:
        start_audio_stream(selected_device_idx)

    def draw_avatar(base_char_center, anim_offset=(0, 0), force_e=False, force_m=False):
        """Função unificada para desenhar o personagem e suas roupas respeitando as camadas."""
        anim_char_center = (base_char_center[0] + anim_offset[0], base_char_center[1] + anim_offset[1])
        
        is_hard_edges = config.get('hard_edges', False)
        
        if is_hard_edges:
            target_surf = composition_surface
            target_surf.fill((0, 0, 0, 0))
        else:
            target_surf = screen
            
        eyes_are_open = not (is_blinking or force_e)

        def draw_layer_items(layer_target, surf=None, transparent_pass=False):
            if surf is None:
                surf = target_surf
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
                    # Objetos de cena são estáticos, ignoram a animação
                    center_to_use = base_char_center if cat == "objetos_de_cena" else anim_char_center
                    item_c = (center_to_use[0] + w_item['offset'][0], center_to_use[1] + w_item['offset'][1])
                    surf.blit(img, img.get_rect(center=item_c))
                    
        # Camadas Fundo -> Frente
        draw_layer_items('trás')
        
        if "char" in images and images["char"]:
            target_surf.blit(images['char'], images['char'].get_rect(center=anim_char_center))
            
        draw_layer_items('meio')
            
        eyes_c = (anim_char_center[0] + offsets['eyes'][0], anim_char_center[1] + offsets['eyes'][1])
        if not eyes_are_open and "eyes_closed" in images and images["eyes_closed"]:
            target_surf.blit(images["eyes_closed"], images["eyes_closed"].get_rect(center=eyes_c))
        elif eyes_are_open and "eyes_open" in images and images["eyes_open"]:
            target_surf.blit(images["eyes_open"], images["eyes_open"].get_rect(center=eyes_c))
            
        mouth_c = (anim_char_center[0] + offsets['mouth'][0], anim_char_center[1] + offsets['mouth'][1])
        if (is_speaking or force_m) and "mouth_open" in images and images["mouth_open"]:
            target_surf.blit(images["mouth_open"], images["mouth_open"].get_rect(center=mouth_c))
            
        draw_layer_items('frente')
        
        if is_hard_edges:
            target_surf = remove_soft_edges(target_surf)
            draw_layer_items('trás', screen, transparent_pass=True)
            screen.blit(target_surf, (0, 0))
            draw_layer_items('meio', screen, transparent_pass=True)
            draw_layer_items('frente', screen, transparent_pass=True)

    dragging_part = None
    wardrobe_dragging_item_id = None
    wardrobe_selected_item_id = None
    wardrobe_scroll = 0
    wardrobe_collapsed_cats = set()
    dragging_wardrobe_slider = False
    
    last_cycle_profile_pressed = False
    current_profile_index = -1
    profile_notif_text = ""
    profile_notif_time = 0
    vcam = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Se o botão esquerdo do mouse for clicado
                
                # Captura o estado antes de qualquer arraste ou edição pelo mouse
                if current_state in ["POSITIONING", "WARDROBE"]:
                    pre_drag_state = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})
                    
                if current_state == "MENU":
                    pos = event.pos
                    
                    # Lógica do Dropdown de Dispositivos de Áudio
                    if dropdown_open:
                        clicked_item = False
                        if input_devices:
                            for j, (idx, dev) in enumerate(input_devices):
                                item_rect = pygame.Rect(btn_device.x, btn_device.y + btn_device.height + j * 40, btn_device.width, 40)
                                if item_rect.collidepoint(pos):
                                    current_device_list_index = j
                                    selected_device_idx = idx
                                    config['audio_device'] = selected_device_idx
                                    save_config(config)
                                    start_audio_stream(selected_device_idx)
                                    dropdown_open = False
                                    clicked_item = True
                                    break
                        if not clicked_item:
                            dropdown_open = False
                        continue # Ignora o restante dos botões até resolver o dropdown

                    # Lógica do Slider de Sensibilidade
                    if slider_rect.inflate(0, 20).collidepoint(pos):
                        dragging_slider = True
                        continue

                    if btn_char.collidepoint(pos):
                        new_path = get_file("Selecione a imagem base do Personagem")
                        if new_path:
                            config['paths']["char"] = import_image_to_assets(new_path, "base")
                            save_config(config)
                    elif btn_eyes_open.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Olhos Abertos")
                        if new_path:
                            config['paths']["eyes_open"] = import_image_to_assets(new_path, "base")
                            save_config(config)
                    elif btn_eyes_closed.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Olhos Fechados")
                        if new_path:
                            config['paths']["eyes_closed"] = import_image_to_assets(new_path, "base")
                            save_config(config)
                    elif btn_mouth_open.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Boca Aberta")
                        if new_path:
                            config['paths']["mouth_open"] = import_image_to_assets(new_path, "base")
                            save_config(config)
                    elif btn_device.collidepoint(pos) and input_devices:
                        dropdown_open = True
                    elif btn_refresh_devices.collidepoint(pos):
                        print("Recarregando lista de dispositivos de áudio...")
                        input_devices = get_input_devices()
                        dropdown_open = False
                        
                        # Garante que a seleção atual (ou da config) ainda é válida
                        current_selection_id = config.get('audio_device')
                        is_selection_valid = any(d[0] == current_selection_id for d in input_devices)

                        if not is_selection_valid:
                            print("Dispositivo selecionado anteriormente não está mais disponível. Resetando para o padrão.")
                            current_selection_id = None # Invalida a seleção
                            if input_devices:
                                try:
                                    current_selection_id = sd.default.device[0]
                                except:
                                    current_selection_id = input_devices[0][0]
                            
                            config['audio_device'] = current_selection_id
                            save_config(config)
                            start_audio_stream(current_selection_id)
                        
                        selected_device_idx = current_selection_id
                        current_device_list_index = 0
                        for i, (idx, dev) in enumerate(input_devices):
                            if idx == selected_device_idx:
                                current_device_list_index = i
                                break
                    elif btn_start.collidepoint(pos) and all(paths.values()):
                        # Tenta carregar as imagens assim que iniciar
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))
                            
                            # Muda para a tela principal (RUNNING)
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
                                    notification_text = "Erro Câm. Virtual! (Inicie o OBS Studio e ative a Câmera)"
                                    notification_time = time.time()
                                    config['virtual_camera'] = False
                            
                        except Exception as e:
                            print(f"Erro ao carregar imagem: {e}")
                            notification_text = "Erro: Arquivo de imagem inválido ou não encontrado!"
                            notification_time = time.time()
                            # Limpa os caminhos que deram problema
                            for key in paths:
                                if paths[key] and not os.path.exists(paths[key]):
                                    paths[key] = None
                            save_config(config)
                    elif btn_positioning.collidepoint(pos) and all(paths.values()):
                        try:
                            images.update(load_character_images_scaled(paths, SCREEN_WIDTH * 0.9, SCREEN_HEIGHT * 0.9, config.get('char_scale', 1.0)))

                            current_state = "POSITIONING"
                        except Exception as e:
                            print(f"Erro ao carregar imagem: {e}")
                            notification_text = "Erro: Arquivo de imagem inválido ou não encontrado!"
                            notification_time = time.time()
                            for key in paths:
                                if paths[key] and not os.path.exists(paths[key]):
                                    paths[key] = None
                            save_config(config)
                    elif btn_bg_color.collidepoint(pos):
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        color = colorchooser.askcolor(title="Escolha a cor de fundo", initialcolor=tuple(config['bg_color']))
                        root.destroy()
                        if color[0]:
                            config['bg_color'] = [int(c) for c in color[0]]
                            save_config(config)
                    elif btn_transparent.collidepoint(pos):
                        config['transparent_window'] = not config.get('transparent_window', False)
                        save_config(config)
                    elif btn_borderless.collidepoint(pos):
                        config['borderless_window'] = not config.get('borderless_window', False)
                        save_config(config)
                    elif btn_animations.collidepoint(pos):
                        config['animations_enabled'] = not config.get('animations_enabled', True)
                        save_config(config)
                    elif btn_fps.collidepoint(pos):
                        config['fps_limit'] = 30 if config.get('fps_limit', 60) == 60 else 60
                        save_config(config)
                    elif btn_hard_edges.collidepoint(pos):
                        config['hard_edges'] = not config.get('hard_edges', False)
                        save_config(config)
                    elif btn_virtualcam.collidepoint(pos):
                        if HAS_VIRTUALCAM:
                            config['virtual_camera'] = not config.get('virtual_camera', False)
                            save_config(config)
                        else:
                            notification_text = "Erro: No terminal digite: pip install pyvirtualcam"
                            notification_time = time.time()
                    elif btn_wardrobe.collidepoint(pos):
                        current_state = "WARDROBE"
                        load_wardrobe_images(config, wardrobe_images)
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
                                notification_text = "Perfil salvo com sucesso!"
                                notification_time = time.time()
                            except Exception as e:
                                print(f"Erro ao salvar perfil: {e}")
                                notification_text = "Erro ao salvar perfil!"
                                notification_time = time.time()
                    elif btn_load_profile.collidepoint(pos):
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
                                notification_text = "Perfil carregado com sucesso!"
                                notification_time = time.time()
                                
                                # Verifica integridade das imagens do perfil
                                missing_files = False
                                for key, path in paths.items():
                                    if path and not os.path.exists(path):
                                        paths[key] = None
                                        missing_files = True
                                if missing_files:
                                    save_config(config)
                                    notification_text = "Perfil carregado (Imagens ausentes!)"
                            except Exception as e:
                                print(f"Erro ao carregar perfil: {e}")
                                notification_text = "Erro ao carregar perfil! Arquivo inválido."
                                notification_time = time.time()

                
                elif current_state == "POSITIONING":
                    if btn_positioning_save.collidepoint(event.pos):
                        config['offsets'] = offsets
                        save_config(config)
                        current_state = "MENU"
                    else:
                        # Inicia o Arrastar e Soltar das partes (ordem reversa p/ pegar a frente primeiro)
                        char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
                        mouth_rect_hit = images['mouth_open'].get_rect(center=(char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])) if 'mouth_open' in images else None
                        eyes_rect_hit = images['eyes_open'].get_rect(center=(char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])) if 'eyes_open' in images else None
                        c_rect_hit = images['char'].get_rect(center=char_center) if 'char' in images else None
                        
                        if mouth_rect_hit and mouth_rect_hit.collidepoint(event.pos): dragging_part = 'mouth'
                        elif eyes_rect_hit and eyes_rect_hit.collidepoint(event.pos): dragging_part = 'eyes'
                        elif c_rect_hit and c_rect_hit.collidepoint(event.pos): dragging_part = 'char'
                        
                elif current_state == "WARDROBE":
                    if wardrobe_selected_item_id:
                        slider_rect_w = pygame.Rect(wardrobe_panel_width + 30, 90, 200, 15)
                        if slider_rect_w.inflate(0, 20).collidepoint(event.pos):
                            dragging_wardrobe_slider = True
                            rel_x = max(0, min(event.pos[0] - slider_rect_w.x, slider_rect_w.width))
                            new_scale = 0.1 + (rel_x / slider_rect_w.width) * 4.9
                            for item in config['wardrobe']:
                                if item['id'] == wardrobe_selected_item_id:
                                    item['scale'] = round(new_scale, 2)
                                    break
                            continue
                            
                    if btn_add_wardrobe.collidepoint(event.pos):
                        new_item = edit_wardrobe_item_dialog()
                        if new_item:
                            if pre_drag_state:
                                undo_stack.append(pre_drag_state)
                                if len(undo_stack) > 50: undo_stack.pop(0)
                                pre_drag_state = None
                            config['wardrobe'].append(new_item)
                            save_config(config)
                            load_wardrobe_images(config, wardrobe_images)
                    elif btn_wardrobe_back.collidepoint(event.pos):
                        current_state = "MENU"
                    else:
                        layout = get_wardrobe_layout(config, wardrobe_scroll, wardrobe_collapsed_cats)
                        clicked_list = False
                        for node in layout:
                            if node['type'] == 'header':
                                if node['rect'].collidepoint(event.pos) and 70 <= node['rect'].y <= SCREEN_HEIGHT:
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
                                
                                if pygame.Rect(20, item_y, 40, 40).collidepoint(event.pos):
                                    item['active'] = not item.get('active', True)
                                    save_config(config)
                                    clicked_list = True
                                    break
                                elif pygame.Rect(160, item_y, 40, 40).collidepoint(event.pos):
                                    item['locked'] = not item.get('locked', False)
                                    if item['locked'] and wardrobe_dragging_item_id == item['id']:
                                        wardrobe_dragging_item_id = None
                                    save_config(config)
                                    clicked_list = True
                                    break
                                elif pygame.Rect(210, item_y, 40, 40).collidepoint(event.pos):
                                    cat = item.get('category')
                                    current_layer = item.get('layer', get_default_layer(cat))
                                    if current_layer == 'frente':
                                        item['layer'] = 'meio'
                                    elif current_layer == 'meio':
                                        item['layer'] = 'trás'
                                    else:
                                        item['layer'] = 'frente'
                                    save_config(config)
                                    clicked_list = True
                                    break
                                elif pygame.Rect(360, item_y, 40, 40).collidepoint(event.pos):
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
                                elif pygame.Rect(410, item_y, 40, 40).collidepoint(event.pos):
                                    del config['wardrobe'][i]
                                    save_config(config)
                                    clicked_list = True
                                    break
                                elif pygame.Rect(260, item_y, 40, 40).collidepoint(event.pos) and node['idx_in_cat'] > 0:
                                    for prev_i in range(i - 1, -1, -1):
                                        if config['wardrobe'][prev_i]['category'] == node['cat']:
                                            config['wardrobe'][i], config['wardrobe'][prev_i] = config['wardrobe'][prev_i], config['wardrobe'][i]
                                            break
                                    save_config(config)
                                    clicked_list = True
                                    break
                                elif pygame.Rect(310, item_y, 40, 40).collidepoint(event.pos) and node['idx_in_cat'] < node['total_in_cat'] - 1:
                                    for next_i in range(i + 1, len(config['wardrobe'])):
                                        if config['wardrobe'][next_i]['category'] == node['cat']:
                                            config['wardrobe'][i], config['wardrobe'][next_i] = config['wardrobe'][next_i], config['wardrobe'][i]
                                            break
                                    save_config(config)
                                    clicked_list = True
                                    break
                                
                        # Se não clicou na lista, tenta arrastar os itens da visualização do personagem
                        if not clicked_list:
                            preview_center_x = wardrobe_panel_width + (SCREEN_WIDTH - wardrobe_panel_width) // 2
                            char_center = (preview_center_x + config['offsets']['char'][0], SCREEN_HEIGHT // 2 + config['offsets']['char'][1])
                            
                            click_order = []
                            # Adiciona os itens da frente na ordem inversa (do mais no topo para o fundo da camada)
                            for w_item in reversed(config.get('wardrobe', [])):
                                cat = w_item.get('category')
                                current_layer = w_item.get('layer', get_default_layer(cat))
                                if current_layer == 'frente':
                                    click_order.append(w_item)
                            # Depois adiciona os itens do meio na ordem inversa
                            for w_item in reversed(config.get('wardrobe', [])):
                                cat = w_item.get('category')
                                current_layer = w_item.get('layer', get_default_layer(cat))
                                if current_layer == 'meio':
                                    click_order.append(w_item)
                            # Depois adiciona os itens de trás na ordem inversa
                            for w_item in reversed(config.get('wardrobe', [])):
                                cat = w_item.get('category')
                                current_layer = w_item.get('layer', get_default_layer(cat))
                                if current_layer == 'trás':
                                    click_order.append(w_item)

                            for item in click_order:
                                if wardrobe_dragging_item_id: break
                                if item.get('active') and item['id'] in wardrobe_images:
                                    img_w, img_h = wardrobe_images[item['id']].get_size()
                                    scale = item.get('scale', 1.0)
                                    item_rect = pygame.Rect(0, 0, max(1, int(img_w * scale)), max(1, int(img_h * scale)))
                                    item_center = (char_center[0] + item['offset'][0], char_center[1] + item['offset'][1])
                                    item_rect.center = item_center
                                    if item_rect.collidepoint(event.pos):
                                        wardrobe_selected_item_id = item['id']
                                        if not item.get('locked', False):
                                            wardrobe_dragging_item_id = item['id']
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
                elif event.key == pygame.K_ESCAPE and current_state == "RUNNING":
                    current_state = "MENU"
                    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                    set_window_transparency(config['bg_color'], False)
                    if vcam:
                        vcam.close()
                        vcam = None
                
                elif current_state == "POSITIONING":
                    if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                        if time.time() - last_continuous_action_time > 0.5:
                            save_state_for_undo()
                        last_continuous_action_time = time.time()
                        
                    selected_part = parts_list[editing_part_index]
                    step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1

                    if event.key == pygame.K_UP: offsets[selected_part][1] -= step
                    elif event.key == pygame.K_DOWN: offsets[selected_part][1] += step
                    elif event.key == pygame.K_LEFT: offsets[selected_part][0] -= step
                    elif event.key == pygame.K_RIGHT: offsets[selected_part][0] += step
                    elif event.key == pygame.K_TAB:
                        editing_part_index = (editing_part_index + 1) % len(parts_list)
                        
                elif current_state == "WARDROBE" and wardrobe_selected_item_id:
                    # Permite ajuste fino com as setas para a roupa selecionada
                    if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                        item = next((i for i in config['wardrobe'] if i['id'] == wardrobe_selected_item_id), None)
                        if item and not item.get('locked', False):
                            if time.time() - last_continuous_action_time > 0.5:
                                save_state_for_undo()
                            last_continuous_action_time = time.time()
                            
                            step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                            if event.key == pygame.K_UP: item['offset'][1] -= step
                            elif event.key == pygame.K_DOWN: item['offset'][1] += step
                            elif event.key == pygame.K_LEFT: item['offset'][0] -= step
                            elif event.key == pygame.K_RIGHT: item['offset'][0] += step
                            save_config(config)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if pre_drag_state:
                    current_state_snap = copy.deepcopy({'offsets': config['offsets'], 'wardrobe': config['wardrobe'], 'char_scale': config.get('char_scale', 1.0)})
                    if current_state_snap != pre_drag_state:
                        undo_stack.append(pre_drag_state)
                        if len(undo_stack) > 50: undo_stack.pop(0)
                    pre_drag_state = None
                    
                if dragging_slider:
                    dragging_slider = False
                    config['sound_threshold'] = SOUND_THRESHOLD
                    save_config(config)
                
                if dragging_wardrobe_slider:
                    dragging_wardrobe_slider = False
                    save_config(config)
                
                # Salva o config ao soltar uma peça de roupa no lugar
                if wardrobe_dragging_item_id:
                    save_config(config)
                dragging_part = None
                wardrobe_dragging_item_id = None
                    
            elif event.type == pygame.MOUSEWHEEL:
                if current_state == "WARDROBE":
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    if mouse_x < wardrobe_panel_width:
                        wardrobe_scroll -= event.y * 20
                        wardrobe_scroll = max(0, wardrobe_scroll)
                    elif wardrobe_selected_item_id:
                        for item in config['wardrobe']:
                            if item['id'] == wardrobe_selected_item_id:
                                if not item.get('locked', False):
                                    if time.time() - last_continuous_action_time > 0.5:
                                        save_state_for_undo()
                                    last_continuous_action_time = time.time()
                                    
                                    scale = item.get('scale', 1.0)
                                    scale += event.y * 0.02
                                    item['scale'] = max(0.1, min(5.0, scale))
                                    save_config(config)
                                break
                elif current_state == "POSITIONING":
                    if time.time() - last_continuous_action_time > 0.5:
                        save_state_for_undo()
                    last_continuous_action_time = time.time()
                    
                    # Zoom no personagem inteiro de forma centralizada!
                    manual_scale = config.get('char_scale', 1.0)
                    new_scale = manual_scale + (event.y * 0.01)
                    new_scale = max(0.1, min(5.0, new_scale))
                    
                    if new_scale != manual_scale:
                        config['char_scale'] = new_scale
                        # Ajusta offsets e escalas para manter as posições relativas intactas
                        factor = new_scale / manual_scale
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
                    
            elif event.type == pygame.MOUSEMOTION:
                if dragging_slider:
                    rel_x = max(0, min(event.pos[0] - slider_rect.x, slider_rect.width))
                    # Mapeia o movimento do slider para um valor entre 0.01 e 0.50
                    SOUND_THRESHOLD = 0.01 + (rel_x / slider_rect.width) * 0.49
                elif dragging_wardrobe_slider and current_state == "WARDROBE" and wardrobe_selected_item_id:
                    slider_rect_w = pygame.Rect(wardrobe_panel_width + 30, 90, 200, 15)
                    rel_x = max(0, min(event.pos[0] - slider_rect_w.x, slider_rect_w.width))
                    new_scale = 0.1 + (rel_x / slider_rect_w.width) * 4.9
                    for item in config['wardrobe']:
                        if item['id'] == wardrobe_selected_item_id:
                            if not item.get('locked', False):
                                item['scale'] = round(new_scale, 2)
                            break
                elif current_state == "POSITIONING" and dragging_part:
                    offsets[dragging_part][0] += event.rel[0]
                    offsets[dragging_part][1] += event.rel[1]
                elif current_state == "WARDROBE" and wardrobe_dragging_item_id:
                    for item in config['wardrobe']:
                        if item['id'] == wardrobe_dragging_item_id:
                            item['offset'][0] += event.rel[0]
                            item['offset'][1] += event.rel[1]
                            break

        current_time = time.time()

        if current_state == "MENU":
            screen.fill((50, 50, 50)) # Fundo cinza para o menu
            
            # Desenha os botões de seleção
            for btn, key, label in [
                (btn_char, "char", "1. Personagem Base"),
                (btn_eyes_open, "eyes_open", "2. Olhos Abertos"),
                (btn_eyes_closed, "eyes_closed", "3. Olhos Fechados"),
                (btn_mouth_open, "mouth_open", "4. Boca Aberta"),
            ]:
                color = (100, 200, 100) if paths[key] else (200, 100, 100)
                pygame.draw.rect(screen, color, btn, border_radius=5)
                text_surf = font.render(label, True, (255, 255, 255))
                screen.blit(text_surf, (btn.x + 10, btn.y + 8))
                
                if paths[key]:
                    # Mostra o final do caminho se for muito longo para não cortar
                    path_display = "... " + paths[key][-50:] if len(paths[key]) > 50 else paths[key]
                    path_surf = font.render(path_display, True, (200, 200, 200))
                    screen.blit(path_surf, (btn.x + btn.width + 15, btn.y + 8))

            # --- Áudio e Dispositivos ---
            device_name = "Nenhum dispositivo encontrado"
            if input_devices:
                dev = input_devices[current_device_list_index][1]
                device_name = dev.get('display_name', dev['name'])
            
            if len(device_name) > 80:
                device_name = device_name[:77] + "..."
                
            # Calcula a largura dinamicamente para caber o maior nome da lista
            max_mic_w = font.size(f"Mic: {device_name}")[0]
            if input_devices:
                for _, d in input_devices:
                    d_name = d.get('display_name', d['name'])
                    if len(d_name) > 80: d_name = d_name[:77] + "..."
                    w, _ = font.size(f"Mic: {d_name}")
                    if w > max_mic_w: max_mic_w = w
                    
            btn_device.width = max(300, max_mic_w + 40)
            btn_refresh_devices.x = btn_device.right + 10

            pygame.draw.rect(screen, (100, 100, 200), btn_device, border_radius=5)
            device_text = font.render(f"Mic: {device_name}", True, (255, 255, 255))
            screen.blit(device_text, (btn_device.x + 10, btn_device.y + 8))
            
            # Ícone de seta para baixo indicando que é um select
            arrow_x = btn_device.x + btn_device.width - 25
            arrow_y = btn_device.y + 16
            pygame.draw.polygon(screen, (255, 255, 255), [(arrow_x, arrow_y), (arrow_x + 10, arrow_y), (arrow_x + 5, arrow_y + 8)])

            # Botão de recarregar dispositivos
            pygame.draw.rect(screen, (100, 150, 200), btn_refresh_devices, border_radius=5)
            refresh_font = pygame.font.SysFont(None, 35)
            # O caractere '↻' pode não renderizar em todas as fontes/sistemas
            refresh_text = refresh_font.render("R", True, (255, 255, 255))
            text_rect = refresh_text.get_rect(center=btn_refresh_devices.center)
            screen.blit(refresh_text, text_rect)

            # Barra de captação
            bar_x, bar_y, bar_w, bar_h = 50, 380, 500, 20
            pygame.draw.rect(screen, (30, 30, 30), (bar_x, bar_y, bar_w, bar_h))
            
            visual_vol = min(1.0, current_volume / (SOUND_THRESHOLD * 5.0 + 0.001))
            vol_w = int(visual_vol * bar_w)
            bar_color = (0, 255, 0) if visual_vol < 0.5 else (255, 255, 0) if visual_vol < 0.8 else (255, 0, 0)
                
            if vol_w > 0:
                pygame.draw.rect(screen, bar_color, (bar_x, bar_y, vol_w, bar_h))
            
            threshold_visual = min(1.0, SOUND_THRESHOLD / (SOUND_THRESHOLD * 5.0 + 0.001))
            threshold_x = bar_x + int(threshold_visual * bar_w)
            pygame.draw.line(screen, (255, 255, 255), (threshold_x, bar_y - 5), (threshold_x, bar_y + bar_h + 5), 2)
            
            # Slider de sensibilidade
            slider_text = font.render(f"Sensibilidade: {SOUND_THRESHOLD:.3f}", True, (255, 255, 255))
            screen.blit(slider_text, (slider_rect.x, slider_rect.y - 25))
            pygame.draw.rect(screen, (80, 80, 80), slider_rect, border_radius=8)
            
            knob_x = slider_rect.x + int(((SOUND_THRESHOLD - 0.01) / 0.49) * slider_rect.width)
            pygame.draw.circle(screen, (200, 200, 200), (knob_x, slider_rect.centery), 10)
            
            # Teste de Microfone Reduzido (Ícone e status) ao lado da barra
            face_cx, face_cy = 750, 420
            face_radius = 25
            pygame.draw.circle(screen, (220, 200, 150), (face_cx, face_cy), face_radius)
            # Olhos
            pygame.draw.circle(screen, (0, 0, 0), (face_cx - 8, face_cy - 6), 3)
            pygame.draw.circle(screen, (0, 0, 0), (face_cx + 8, face_cy - 6), 3)
            # Boca
            if is_speaking:
                pygame.draw.ellipse(screen, (50, 0, 0), (face_cx - 6, face_cy + 4, 12, 10))
            else:
                pygame.draw.line(screen, (50, 0, 0), (face_cx - 6, face_cy + 8), (face_cx + 6, face_cy + 8), 2)
                
            status_text = "FALANDO" if is_speaking else "SILÊNCIO"
            status_surf = font.render(status_text, True, (0, 255, 0) if is_speaking else (200, 200, 200))
            screen.blit(status_surf, (face_cx - status_surf.get_width() // 2, face_cy + 30))

            # Desenha o botão de Iniciar
            can_start = all(paths.values())
            start_color = (0, 200, 0) if can_start else (100, 100, 100)
            pygame.draw.rect(screen, start_color, btn_start, border_radius=5)
            start_text = font.render("INICIAR", True, (255, 255, 255) if can_start else (150, 150, 150))
            screen.blit(start_text, (btn_start.x + (btn_start.width - start_text.get_width()) // 2, btn_start.y + 12))
            
            # Desenha o botão de Posições
            pygame.draw.rect(screen, start_color, btn_positioning, border_radius=5)
            pos_text = font.render("Posições", True, (255, 255, 255) if can_start else (150, 150, 150))
            screen.blit(pos_text, (btn_positioning.x + (btn_positioning.width - pos_text.get_width()) // 2, btn_positioning.y + 12))

            # Desenha o botão de Cor de Fundo
            pygame.draw.rect(screen, config['bg_color'], btn_bg_color, border_radius=5)
            pygame.draw.rect(screen, (255, 255, 255), btn_bg_color, 2, border_radius=5)
            bg_text = font.render("Cor do Fundo", True, (0, 0, 0) if sum(config['bg_color']) > 380 else (255, 255, 255))
            screen.blit(bg_text, (btn_bg_color.x + (btn_bg_color.width - bg_text.get_width()) // 2, btn_bg_color.y + 12))

            # Desenha o botão de Fundo Transparente
            is_transparent = config.get('transparent_window', False)
            transp_color = (0, 200, 0) if is_transparent else (200, 100, 100)
            pygame.draw.rect(screen, transp_color, btn_transparent, border_radius=5)
            transp_text = font.render(f"Transparente: {'ON' if is_transparent else 'OFF'}", True, (255, 255, 255))
            screen.blit(transp_text, (btn_transparent.x + 20, btn_transparent.y + 12))

            # Desenha o botão Sem Bordas
            is_borderless = config.get('borderless_window', False)
            borderless_color = (0, 200, 0) if is_borderless else (200, 100, 100)
            pygame.draw.rect(screen, borderless_color, btn_borderless, border_radius=5)
            borderless_text = font.render(f"Sem Bordas: {'ON' if is_borderless else 'OFF'}", True, (255, 255, 255))
            screen.blit(borderless_text, (btn_borderless.x + 20, btn_borderless.y + 12))

            # Desenha o botão de Animações
            is_anim_enabled = config.get('animations_enabled', True)
            anim_color = (0, 200, 0) if is_anim_enabled else (200, 100, 100)
            pygame.draw.rect(screen, anim_color, btn_animations, border_radius=5)
            anim_text = font.render(f"Animações: {'ON' if is_anim_enabled else 'OFF'}", True, (255, 255, 255))
            screen.blit(anim_text, (btn_animations.x + 20, btn_animations.y + 12))

            # Desenha o botão de Limite de FPS
            current_fps = config.get('fps_limit', 60)
            fps_color = (0, 200, 0) if current_fps == 60 else (200, 150, 0)
            pygame.draw.rect(screen, fps_color, btn_fps, border_radius=5)
            fps_text = font.render(f"FPS: {current_fps}", True, (255, 255, 255))
            screen.blit(fps_text, (btn_fps.x + 20, btn_fps.y + 12))

            # Desenha o botão de Contorno Sólido
            is_hard_edges = config.get('hard_edges', False)
            hard_edges_color = (0, 200, 0) if is_hard_edges else (200, 100, 100)
            pygame.draw.rect(screen, hard_edges_color, btn_hard_edges, border_radius=5)
            hard_text = font.render(f"Contorno Sólido: {'ON' if is_hard_edges else 'OFF'}", True, (255, 255, 255))
            screen.blit(hard_text, (btn_hard_edges.x + 20, btn_hard_edges.y + 12))
            
            # Desenha o botão de Câmera Virtual
            is_vcam = config.get('virtual_camera', False)
            if not HAS_VIRTUALCAM:
                vcam_color = (100, 100, 100)
                vcam_text_str = "Virtual Cam (Requer Lib)"
            else:
                vcam_color = (0, 200, 0) if is_vcam else (200, 100, 100)
                vcam_text_str = f"Câmera Virtual: {'ON' if is_vcam else 'OFF'}"
            pygame.draw.rect(screen, vcam_color, btn_virtualcam, border_radius=5)
            vcam_text = font.render(vcam_text_str, True, (255, 255, 255))
            screen.blit(vcam_text, (btn_virtualcam.x + (btn_virtualcam.width - vcam_text.get_width()) // 2, btn_virtualcam.y + 12))

            # Desenha o botão de Guarda-Roupa
            pygame.draw.rect(screen, (150, 100, 200), btn_wardrobe, border_radius=5)
            pygame.draw.rect(screen, (255, 255, 255), btn_wardrobe, 2, border_radius=5)
            w_text = font.render("Guarda-Roupa", True, (255, 255, 255))
            screen.blit(w_text, (btn_wardrobe.x + (btn_wardrobe.width - w_text.get_width()) // 2, btn_wardrobe.y + 12))

            # Desenha os botões de Perfil
            pygame.draw.rect(screen, (50, 150, 200), btn_load_profile, border_radius=5)
            load_text = font.render("Carregar", True, (255, 255, 255))
            screen.blit(load_text, (btn_load_profile.x + (btn_load_profile.width - load_text.get_width()) // 2, btn_load_profile.y + 12))

            pygame.draw.rect(screen, (50, 150, 200), btn_save_profile, border_radius=5)
            save_text = font.render("Salvar", True, (255, 255, 255))
            screen.blit(save_text, (btn_save_profile.x + (btn_save_profile.width - save_text.get_width()) // 2, btn_save_profile.y + 12))

            # --- Menu Dropdown de Dispositivos (Desenhado por último para sobrepor o resto) ---
            if dropdown_open and input_devices:
                for j, (idx, dev) in enumerate(input_devices):
                    item_rect = pygame.Rect(btn_device.x, btn_device.y + btn_device.height + j * 40, btn_device.width, 40)
                    
                    # Efeito de hover (mouse em cima ilumina a cor)
                    hover = item_rect.collidepoint(pygame.mouse.get_pos())
                    color = (130, 130, 230) if hover else (100, 100, 200)
                    
                    pygame.draw.rect(screen, color, item_rect)
                    pygame.draw.rect(screen, (80, 80, 180), item_rect, 1) # Borda do item
                    
                    d_name = dev.get('display_name', dev['name'])
                    if len(d_name) > 80:
                        d_name = d_name[:77] + "..."
                    i_text = font.render(d_name, True, (255, 255, 255))
                    screen.blit(i_text, (item_rect.x + 10, item_rect.y + 8))
                    
            # --- Notificações no Menu ---
            if notification_text and current_time - notification_time < 4.0:
                is_error = "Erro" in notification_text or "ausentes" in notification_text or "removidas" in notification_text or "inválido" in notification_text
                color_text = (255, 80, 80) if is_error else (80, 255, 80)
                color_bg = (50, 20, 20) if is_error else (20, 50, 20)
                
                notif_surf = font.render(notification_text, True, color_text)
                notif_rect = notif_surf.get_rect(center=(SCREEN_WIDTH // 2, 30))
                bg_rect = notif_rect.inflate(30, 15)
                
                pygame.draw.rect(screen, color_bg, bg_rect, border_radius=5)
                pygame.draw.rect(screen, color_text, bg_rect, 2, border_radius=5)
                screen.blit(notif_surf, notif_rect)

        elif current_state == "POSITIONING":
            screen.fill((50, 50, 80)) # Fundo azul escuro para o modo de posição

            # --- Cálculos de Posição ---
            char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])

            # --- Desenho das Partes ---
            draw_avatar(char_center, force_m=True)
            
            # --- Desenho da Interface de Ajuda ---
            if not dragging_part:
                selected_part_name = parts_list[editing_part_index].upper()
                highlight_rect = None
                if selected_part_name == 'CHAR': highlight_rect = images['char'].get_rect(center=char_center) if 'char' in images else None
                elif selected_part_name == 'EYES': highlight_rect = images['eyes_open'].get_rect(center=(char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])) if 'eyes_open' in images else None
                elif selected_part_name == 'MOUTH': highlight_rect = images['mouth_open'].get_rect(center=(char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])) if 'mouth_open' in images else None
                if highlight_rect: pygame.draw.rect(screen, (255, 255, 0), highlight_rect, 2)
            else:
                selected_part_name = dragging_part.upper() + " (Arrastando)"

            # Textos de ajuda
            title_text = font.render("Modo de Posição", True, (255, 255, 255))
            part_text = font.render(f"Editando: {selected_part_name}", True, (255, 255, 0))
            controls_text1 = font.render("Arraste com o MOUSE, use as SETAS, ou SCROLL para Zoom", True, (255, 255, 255))
            controls_text2 = font.render("Pressione TAB para trocar a peça atual", True, (255, 255, 255))
            screen.blit(title_text, (20, 20))
            screen.blit(part_text, (20, 60))
            screen.blit(controls_text1, (20, SCREEN_HEIGHT - 80))
            screen.blit(controls_text2, (20, SCREEN_HEIGHT - 50))

            # Botão de salvar
            pygame.draw.rect(screen, (0, 200, 0), btn_positioning_save, border_radius=5)
            save_text = font.render("Salvar e Voltar", True, (255, 255, 255))
            screen.blit(save_text, (btn_positioning_save.x + (btn_positioning_save.width - save_text.get_width()) // 2, btn_positioning_save.y + 12))

            # --- Notificações ---
            if notification_text and current_time - notification_time < 4.0:
                # Renderiza o texto e um fundo em vermelho claro para destacar
                notif_surf = font.render(notification_text, True, (255, 80, 80))
                notif_rect = notif_surf.get_rect(center=(SCREEN_WIDTH // 2, 30))
                bg_rect = notif_rect.inflate(30, 15)
                
                pygame.draw.rect(screen, (50, 20, 20), bg_rect, border_radius=5)
                pygame.draw.rect(screen, (255, 80, 80), bg_rect, 2, border_radius=5)
                screen.blit(notif_surf, notif_rect)

        elif current_state == "WARDROBE":
            screen.fill((50, 50, 50))
            # Painel esquerdo
            pygame.draw.rect(screen, (40, 40, 40), (0, 0, wardrobe_panel_width, SCREEN_HEIGHT))
            
            # Botões do Painel
            pygame.draw.rect(screen, (100, 200, 100), btn_add_wardrobe, border_radius=5)
            add_surf = font.render("Adicionar Roupa", True, (0,0,0))
            screen.blit(add_surf, add_surf.get_rect(center=btn_add_wardrobe.center))
            
            pygame.draw.rect(screen, (200, 100, 100), btn_wardrobe_back, border_radius=5)
            back_surf = font.render("Voltar ao Menu", True, (255,255,255))
            screen.blit(back_surf, back_surf.get_rect(center=btn_wardrobe_back.center))
            
            # Renderiza lista de itens em acordeão
            layout = get_wardrobe_layout(config, wardrobe_scroll, wardrobe_collapsed_cats)
            for node in layout:
                if node['type'] == 'header':
                    if 70 <= node['rect'].y <= SCREEN_HEIGHT:
                        pygame.draw.rect(screen, (70, 70, 90), node['rect'], border_radius=5)
                        indicator = "+" if node['cat'] in wardrobe_collapsed_cats else "-"
                        count_txt = f" ({node['count']})"
                        cat_name = node['cat'].replace('_', ' ').title()
                        screen.blit(font.render(f"{indicator} {cat_name}{count_txt}", True, (255, 255, 255)), (30, node['rect'].y + 10))
                elif node['type'] == 'item':
                    item_y = node['y']
                    if item_y < 70 or item_y > SCREEN_HEIGHT: continue
                    
                    item = node['item']
                    cat = node['cat']
                    idx_in_cat = node['idx_in_cat']
                    total_in_cat = node['total_in_cat']
                    
                    # Toggle (Switch)
                    color_sw = (0, 200, 0) if item.get('active', True) else (100, 100, 100)
                    pygame.draw.rect(screen, color_sw, (20, item_y, 40, 40), border_radius=5)
                    
                    # Nome do item
                    name_text = font.render(item['name'][:9], True, (255, 255, 255))
                    screen.blit(name_text, (70, item_y + 10))
                    
                    # Botão Lock
                    is_locked = item.get('locked', False)
                    lock_color = (200, 50, 50) if is_locked else (80, 80, 80)
                    pygame.draw.rect(screen, lock_color, (160, item_y, 40, 40), border_radius=5)
                    pygame.draw.rect(screen, (255,255,255), (170, item_y+20, 20, 12), border_radius=2)
                    if is_locked:
                        pygame.draw.arc(screen, (255,255,255), (174, item_y+10, 12, 12), 0, math.pi, 2)
                    else:
                        pygame.draw.arc(screen, (255,255,255), (174, item_y+8, 12, 12), math.pi/2, math.pi, 2)
                    
                    # Botão Layer (F/M/T)
                    current_layer = item.get('layer', get_default_layer(cat))
                    if current_layer == 'frente':
                        layer_color, layer_text = (200, 150, 50), "F"
                    elif current_layer == 'meio':
                        layer_color, layer_text = (150, 50, 200), "M"
                    else:
                        layer_color, layer_text = (50, 150, 200), "T"
                        
                    pygame.draw.rect(screen, layer_color, (210, item_y, 40, 40), border_radius=5)
                    screen.blit(font.render(layer_text, True, (255, 255, 255)), (222, item_y + 10))

                    # Botão Subir (^)
                    if idx_in_cat > 0:
                        pygame.draw.rect(screen, (100, 150, 200), (260, item_y, 40, 40), border_radius=5)
                        screen.blit(font.render("^", True, (255, 255, 255)), (272, item_y + 10))
                        
                    # Botão Descer (v)
                    if idx_in_cat < total_in_cat - 1:
                        pygame.draw.rect(screen, (100, 150, 200), (310, item_y, 40, 40), border_radius=5)
                        screen.blit(font.render("v", True, (255, 255, 255)), (322, item_y + 10))

                    # Botão E (Editar)
                    pygame.draw.rect(screen, (200, 200, 100), (360, item_y, 40, 40), border_radius=5)
                    screen.blit(font.render("E", True, (0,0,0)), (372, item_y + 10))
                    
                    # Botão X (Excluir)
                    pygame.draw.rect(screen, (200, 50, 50), (410, item_y, 40, 40), border_radius=5)
                    screen.blit(font.render("X", True, (255,255,255)), (422, item_y + 10))
                
            # Painel de Pré-visualização
            instr = font.render("Arraste os itens ativos para posicionar no personagem", True, (200, 200, 200))
            screen.blit(instr, (wardrobe_panel_width + 30, 20))
            preview_center_x = wardrobe_panel_width + (SCREEN_WIDTH - wardrobe_panel_width) // 2
            char_center = (preview_center_x + config['offsets']['char'][0], SCREEN_HEIGHT // 2 + config['offsets']['char'][1])
            draw_avatar(char_center, force_m=True)

            # Desenha o destaque e texto de qual item está selecionado
            if wardrobe_selected_item_id:
                for item in config.get('wardrobe', []):
                    if item['id'] == wardrobe_selected_item_id and item.get('active') and item['id'] in wardrobe_images:
                        item_center = (char_center[0] + item['offset'][0], char_center[1] + item['offset'][1])
                        img_w, img_h = wardrobe_images[item['id']].get_size()
                        scale = item.get('scale', 1.0)
                        highlight_rect = pygame.Rect(0, 0, max(1, int(img_w * scale)), max(1, int(img_h * scale)))
                        highlight_rect.center = item_center
                        
                        is_locked = item.get('locked', False)
                        hl_color = (255, 50, 50) if is_locked else (255, 255, 0)
                        pygame.draw.rect(screen, hl_color, highlight_rect, 2)
                        
                        if is_locked:
                            sel_text = font.render(f"Travado: {item['name'][:12]} (Destrave p/ mover)", True, hl_color)
                        else:
                            sel_text = font.render(f"Editando: {item['name'][:15]} (SETAS = Mover)", True, hl_color)
                            
                        screen.blit(sel_text, (wardrobe_panel_width + 30, 50))
                        
                        if not is_locked:
                            slider_rect_w = pygame.Rect(wardrobe_panel_width + 30, 90, 200, 15)
                            pygame.draw.rect(screen, (80, 80, 80), slider_rect_w, border_radius=8)
                            knob_x = slider_rect_w.x + int(((scale - 0.1) / 4.9) * slider_rect_w.width)
                            pygame.draw.circle(screen, (200, 200, 200), (knob_x, slider_rect_w.centery), 10)
                            
                            scale_text = font.render(f"Tamanho: {scale:.2f} (ou SCROLL)", True, (255, 255, 255))
                            screen.blit(scale_text, (slider_rect_w.right + 20, slider_rect_w.y - 5))
                        break

        elif current_state == "RUNNING":
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
            
            # --- Lógica de Piscar ---
            if current_time - last_blink_time > next_blink_interval:
                is_blinking = True
                last_blink_time = current_time
                next_blink_interval = random.uniform(2, 6) # Próximo piscar
            
            breath_offset = 0
            sway_offset = 0
            if config.get('animations_enabled', True):
                # --- Animação de Respiração ---
                breath_offset = math.sin(current_time * 2.5) * 3.0 # Frequência 2.5, amplitude 3 pixels

                # --- Animação de Balanço ao Falar ---
                if is_speaking or force_mouth:
                    # Usa o volume atual (ou simula um volume se usar o atalho de teclado CTRL+M)
                    active_volume = current_volume if is_speaking else (SOUND_THRESHOLD * 4)
                    sway_amplitude = min(12.0, max(2.0, active_volume * 10.0)) # Limita o balanço a 12 pixels
                    sway_offset = math.sin(current_time * 18.0) * sway_amplitude # Frequência 18.0 (rápido)

            # --- Cálculos de Posição ---
            base_char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
            anim_offset = (int(sway_offset), int(breath_offset))

            # --- Desenho na Tela ---
            screen.fill(config['bg_color'])
            draw_avatar(base_char_center, anim_offset, force_eyes, force_mouth)
            
            if is_blinking and current_time - last_blink_time > 0.1:
                is_blinking = False
                
            if profile_notif_text and current_time - profile_notif_time < 2.0:
                p_surf = font.render(profile_notif_text, True, (255, 255, 0))
                pygame.draw.rect(screen, (0, 0, 0), (15, 15, p_surf.get_width() + 10, p_surf.get_height() + 10), border_radius=5)
                screen.blit(p_surf, (20, 20))

            # --- Envia o Frame para a Câmera Virtual ---
            if vcam:
                try:
                    # Captura a tela do pygame, inverte x e y, e envia para a câmera virtual
                    frame = pygame.surfarray.array3d(screen)
                    frame = np.swapaxes(frame, 0, 1)
                    vcam.send(frame)
                except Exception as e:
                    pass

        pygame.display.flip()
        clock.tick(config.get('fps_limit', 60))

    if vcam:
        vcam.close()
    pygame.quit()

if __name__ == '__main__':
    main()
