import pygame
import sounddevice as sd
import numpy as np
import random
import threading
import tkinter as tk
from tkinter import filedialog
import time
import json
import os

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
        "offsets": {"char": [0, 0], "eyes": [0, 0], "mouth": [0, 0]}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Garante que as chaves principais existam
                config.setdefault('paths', defaults['paths'])
                config.setdefault('offsets', defaults['offsets'])
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

# --- Estado do Personagem ---
is_speaking = False
is_blinking = False
last_blink_time = 0
next_blink_interval = random.uniform(2, 6) # Piscar a cada 2-6 segundos

def audio_callback(indata, frames, time, status):
    """
    Callback para processar o áudio do microfone.
    Verifica se o volume do som ultrapassa um limiar.
    """
    global is_speaking
    volume_norm = np.linalg.norm(indata) * 10
    if volume_norm > SOUND_THRESHOLD:
        is_speaking = True
    else:
        is_speaking = False

def start_audio_stream():
    """Inicia a captura de áudio em uma thread separada."""
    with sd.InputStream(callback=audio_callback):
        sd.sleep(duration=1000000) # Mantém a stream aberta

def main():
    """Função principal que executa o loop do jogo."""
    global last_blink_time, next_blink_interval, is_blinking

    pygame.init()

    # --- Configuração da Janela ---
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Personagem Interativo")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    # --- Variáveis de Estado da Interface ---
    current_state = "MENU"
    config = load_config()
    paths = config['paths']
    offsets = config['offsets']
    images = {}

    # Variáveis do modo de posicionamento
    editing_part_index = 0
    parts_list = ['char', 'eyes', 'mouth']

    # Botões da interface (posição x, posição y, largura, altura)
    btn_char = pygame.Rect(50, 100, 350, 50)
    btn_eyes_open = pygame.Rect(50, 200, 350, 50)
    btn_eyes_closed = pygame.Rect(50, 300, 350, 50)
    btn_mouth_open = pygame.Rect(50, 400, 350, 50)
    btn_start = pygame.Rect(50, 550, 350, 50)
    btn_positioning_save = pygame.Rect(SCREEN_WIDTH - 270, SCREEN_HEIGHT - 70, 250, 50)

    char_rect, eyes_rect, mouth_rect = None, None, None

    def get_file(title):
        """Abre o explorador de arquivos para escolher uma imagem."""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Garante que a janela fique por cima do pygame
        p = filedialog.askopenfilename(title=title, filetypes=[("Imagens PNG", "*.png")])
        root.destroy()
        return p

    audio_thread_started = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Se o botão esquerdo do mouse for clicado
                if current_state == "MENU":
                    pos = event.pos
                    if btn_char.collidepoint(pos):
                        new_path = get_file("Selecione a imagem base do Personagem")
                        if new_path:
                            config['paths']["char"] = new_path
                            save_config(config)
                    elif btn_eyes_open.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Olhos Abertos")
                        if new_path:
                            config['paths']["eyes_open"] = new_path
                            save_config(config)
                    elif btn_eyes_closed.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Olhos Fechados")
                        if new_path:
                            config['paths']["eyes_closed"] = new_path
                            save_config(config)
                    elif btn_mouth_open.collidepoint(pos):
                        new_path = get_file("Selecione a imagem de Boca Aberta")
                        if new_path:
                            config['paths']["mouth_open"] = new_path
                            save_config(config)
                    elif btn_start.collidepoint(pos) and all(paths.values()):
                        # Tenta carregar as imagens assim que iniciar
                        try:
                            images["char"] = pygame.image.load(paths["char"]).convert_alpha()
                            images["eyes_open"] = pygame.image.load(paths["eyes_open"]).convert_alpha()
                            images["eyes_closed"] = pygame.image.load(paths["eyes_closed"]).convert_alpha()
                            images["mouth_open"] = pygame.image.load(paths["mouth_open"]).convert_alpha()
                            
                            # Muda para a tela de posicionamento
                            current_state = "POSITIONING"
                            
                        except pygame.error as e:
                            print(f"Erro ao carregar imagem: {e}")
                
                elif current_state == "POSITIONING":
                    if btn_positioning_save.collidepoint(event.pos):
                        config['offsets'] = offsets
                        save_config(config)
                        current_state = "RUNNING"
                        
                        # Iniciar a captura de áudio somente ao entrar no modo final
                        if not audio_thread_started:
                            audio_thread = threading.Thread(target=start_audio_stream)
                            audio_thread.daemon = True
                            audio_thread.start()
                            audio_thread_started = True
            
            elif event.type == pygame.KEYDOWN:
                if current_state == "POSITIONING":
                    selected_part = parts_list[editing_part_index]
                    step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1

                    if event.key == pygame.K_UP: offsets[selected_part][1] -= step
                    elif event.key == pygame.K_DOWN: offsets[selected_part][1] += step
                    elif event.key == pygame.K_LEFT: offsets[selected_part][0] -= step
                    elif event.key == pygame.K_RIGHT: offsets[selected_part][0] += step
                    elif event.key == pygame.K_TAB:
                        editing_part_index = (editing_part_index + 1) % len(parts_list)
                            
                            # --- Iniciar a captura de áudio ---
                        if not audio_thread_started:
                                audio_thread = threading.Thread(target=start_audio_stream)
                                audio_thread.daemon = True
                                audio_thread.start()
                                audio_thread_started = True

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
                screen.blit(text_surf, (btn.x + 10, btn.y + 12))
                
                if paths[key]:
                    # Mostra o final do caminho se for muito longo para não cortar
                    path_display = "... " + paths[key][-50:] if len(paths[key]) > 50 else paths[key]
                    path_surf = font.render(path_display, True, (200, 200, 200))
                    screen.blit(path_surf, (btn.x + btn.width + 15, btn.y + 12))

            # Desenha o botão de Iniciar
            can_start = all(paths.values())
            start_color = (0, 200, 0) if can_start else (100, 100, 100)
            pygame.draw.rect(screen, start_color, btn_start, border_radius=5)
            start_text = font.render("INICIAR", True, (255, 255, 255) if can_start else (150, 150, 150))
            screen.blit(start_text, (btn_start.x + 120, btn_start.y + 12))

        elif current_state == "POSITIONING":
            screen.fill((50, 50, 80)) # Fundo azul escuro para o modo de posição

            # --- Cálculos de Posição ---
            char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
            char_rect = images['char'].get_rect(center=char_center)

            eyes_center = (char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])
            eyes_rect = images['eyes_open'].get_rect(center=eyes_center)

            mouth_center = (char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])
            mouth_rect = images['mouth_open'].get_rect(center=mouth_center)

            # --- Desenho das Partes ---
            screen.blit(images['char'], char_rect)
            screen.blit(images['eyes_open'], eyes_rect)
            screen.blit(images['mouth_open'], mouth_rect)

            # --- Desenho da Interface de Ajuda ---
            selected_part_name = parts_list[editing_part_index].upper()
            highlight_rect = {'char': char_rect, 'eyes': eyes_rect, 'mouth': mouth_rect}[parts_list[editing_part_index]]
            pygame.draw.rect(screen, (255, 255, 0), highlight_rect, 2)

            # Textos de ajuda
            title_text = font.render("Modo de Posição", True, (255, 255, 255))
            part_text = font.render(f"Editando: {selected_part_name}", True, (255, 255, 0))
            controls_text1 = font.render("Use as SETAS para mover (SHIFT para mais rápido)", True, (255, 255, 255))
            controls_text2 = font.render("Pressione TAB para trocar a parte", True, (255, 255, 255))
            screen.blit(title_text, (20, 20))
            screen.blit(part_text, (20, 60))
            screen.blit(controls_text1, (20, SCREEN_HEIGHT - 80))
            screen.blit(controls_text2, (20, SCREEN_HEIGHT - 50))

            # Botão de salvar
            pygame.draw.rect(screen, (0, 200, 0), btn_positioning_save, border_radius=5)
            save_text = font.render("Salvar e Iniciar", True, (255, 255, 255))
            screen.blit(save_text, (btn_positioning_save.x + 45, btn_positioning_save.y + 12))

        elif current_state == "RUNNING":
            # --- Lógica de Piscar ---
            if current_time - last_blink_time > next_blink_interval:
                is_blinking = True
                last_blink_time = current_time
                next_blink_interval = random.uniform(2, 6) # Próximo piscar
            
            # --- Cálculos de Posição ---
            char_center = (SCREEN_WIDTH // 2 + offsets['char'][0], SCREEN_HEIGHT // 2 + offsets['char'][1])
            char_rect = images['char'].get_rect(center=char_center)

            eyes_center = (char_center[0] + offsets['eyes'][0], char_center[1] + offsets['eyes'][1])
            eyes_open_rect = images['eyes_open'].get_rect(center=eyes_center)
            eyes_closed_rect = images['eyes_closed'].get_rect(center=eyes_center)

            mouth_center = (char_center[0] + offsets['mouth'][0], char_center[1] + offsets['mouth'][1])
            mouth_open_rect = images['mouth_open'].get_rect(center=mouth_center)

            # --- Desenho na Tela ---
            screen.fill(GREEN_BACKGROUND)
            screen.blit(images["char"], char_rect)

            # Desenha os olhos
            if is_blinking:
                screen.blit(images["eyes_closed"], eyes_closed_rect)
                # Duração curta do piscar
                if current_time - last_blink_time > 0.1:
                    is_blinking = False
            else:
                screen.blit(images["eyes_open"], eyes_open_rect)

            # Desenha a boca
            if is_speaking:
                screen.blit(images["mouth_open"], mouth_open_rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == '__main__':
    main()
