import pygame
import random
import json
import math
import os
from enum import Enum
import time

pygame.init()
pygame.mixer.init()

# fuck this shit game
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
GRAVITY = 0.5
JUMP_STRENGTH = -8
PIPE_WIDTH = 80
MAX_PARTICLES = 150


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (135, 206, 235)
DARK_BLUE = (70, 130, 180)
GREEN = (34, 139, 34)
DARK_GREEN = (0, 100, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
GOLD = (255, 215, 0)
ORANGE = (255, 165, 0)
GRAY = (128, 128, 128)
PURPLE = (147, 112, 219)
CYAN = (0, 255, 255)
DARK_GRAY = (40, 40, 40)
LIGHT_GRAY = (200, 200, 200)

class GameState(Enum):
    MENU = 1
    LEVEL_SELECT = 2
    PLAYING = 3
    GAME_OVER = 4
    PAUSED = 5
    LEVEL_COMPLETE = 6
    TRANSITION = 7
    SETTINGS = 8

class Particle:
    def __init__(self, x, y, color, velocity_x=0, velocity_y=0, size=3, lifetime=30):
        self.x = x
        self.y = y
        self.color = color
        self.velocity_x = velocity_x + random.uniform(-2, 2)
        self.velocity_y = velocity_y + random.uniform(-2, 2)
        self.size = size
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.gravity = 0.2

    def update(self):
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.velocity_y += self.gravity
        self.lifetime -= 1

    def draw(self, screen):
        size = max(1, int(self.size * (self.lifetime / self.max_lifetime)))
        if size > 0:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), size)

    def is_dead(self):
        return self.lifetime <= 0

class Cloud:
    def __init__(self, cloud_sprites):
        self.x = random.randint(0, SCREEN_WIDTH)
        self.y = random.randint(50, 200)
        self.speed = random.uniform(0.3, 0.8)
        self.size = random.randint(30, 60)
        sprite = random.choice(cloud_sprites)
        self.scaled_sprite = pygame.transform.scale(sprite, (self.size * 3, self.size * 2))

    def update(self):
        self.x -= self.speed
        if self.x < -self.size * 3:
            self.x = SCREEN_WIDTH + self.size
            self.y = random.randint(50, 200)

    def draw(self, screen):
        screen.blit(self.scaled_sprite, (int(self.x), int(self.y)))

class Bird:
    def __init__(self, x, y, sprites, wing_flap_sound):
        self.x = x
        self.y = y
        self.velocity = 0
        self.size = 20
        self.alive = True
        self.rotation = 0
        self.flap_time = 0
        self.trail_particles = []
        self.shield_active = False
        self.shield_time = 0
        self.idle_sprite = sprites['idle']
        self.wing_up_sprite = sprites['wing_up']
        self.wing_down_sprite = sprites['wing_down']
        self.cached_sprites = {}
        self.wing_flap_sound = wing_flap_sound

    def jump(self):
        if self.alive:
            self.velocity = JUMP_STRENGTH
            self.flap_time = 10
            self.wing_flap_sound.play()

    def update(self):
        self.velocity += GRAVITY
        self.y += self.velocity

        self.rotation = max(-30, min(30, self.velocity * 3))

        if self.flap_time > 0:
            self.flap_time -= 1

        if self.shield_active:
            self.shield_time -= 1
            if self.shield_time <= 0:
                self.shield_active = False

        if random.random() < 0.15:
            color = random.choice([YELLOW, GOLD, ORANGE])
            self.trail_particles.append(
                Particle(self.x - self.size, self.y, color,
                        velocity_x=-2, velocity_y=self.velocity * 0.3,
                        size=4, lifetime=15)
            )

        self.trail_particles = [p for p in self.trail_particles if not p.is_dead()]
        for particle in self.trail_particles:
            particle.update()

    def draw(self, screen):
        for particle in self.trail_particles:
            particle.draw(screen)

        if self.shield_active:
            pygame.draw.circle(screen, (100, 200, 255),
                             (int(self.x), int(self.y)),
                             int(self.size * 1.5), 2)

        if self.flap_time > 5:
            current_sprite = self.wing_up_sprite
        elif self.flap_time > 0:
            current_sprite = self.wing_down_sprite
        else:
            current_sprite = self.idle_sprite

        rotation_key = (id(current_sprite), int(self.rotation))
        if rotation_key not in self.cached_sprites:
            self.cached_sprites[rotation_key] = pygame.transform.rotate(current_sprite, -self.rotation)
            if len(self.cached_sprites) > 50:
                self.cached_sprites.clear()

        rotated = self.cached_sprites[rotation_key]
        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated, rect.topleft)

class Pipe:
    def __init__(self, x, pipe_gap, level, pipe_sprite):
        self.x = x
        self.pipe_gap = pipe_gap
        min_height = 80 + level * 2
        max_height = SCREEN_HEIGHT - pipe_gap - 80 - level * 2
        max_height = max(min_height + 50, max_height)
        self.height = random.randint(min_height, max_height)
        self.passed = False
        self.pipe_sprite = pipe_sprite
        self.top_pipe = None
        self.bottom_pipe = None
        self.pipe_type = "normal"
        self.update_sprites()

    def update_sprites(self):
        self.top_pipe = pygame.transform.scale(self.pipe_sprite, (PIPE_WIDTH, self.height))
        bottom_y = self.height + self.pipe_gap
        bottom_height = SCREEN_HEIGHT - bottom_y
        self.bottom_pipe = pygame.transform.scale(self.pipe_sprite, (PIPE_WIDTH, bottom_height))

    def update(self, pipe_speed):
        self.x -= pipe_speed

    def draw(self, screen):
        screen.blit(self.top_pipe, (self.x, 0))
        bottom_y = self.height + self.pipe_gap
        screen.blit(self.bottom_pipe, (self.x, bottom_y))

    def check_collision(self, bird):
        if bird.x + bird.size > self.x and bird.x - bird.size < self.x + PIPE_WIDTH:
            if bird.y - bird.size < self.height or bird.y + bird.size > self.height + self.pipe_gap:
                return True
        return False

class MovingPipe(Pipe):

    def __init__(self, x, pipe_gap, level, pipe_sprite):
        super().__init__(x, pipe_gap, level, pipe_sprite)
        self.original_height = self.height
        self.move_range = 60
        self.move_speed = 1 + level * 0.05
        self.move_offset = 0
        self.pipe_type = "moving"

    def update(self, pipe_speed):
        super().update(pipe_speed)
        self.move_offset += self.move_speed
        self.height = int(self.original_height + math.sin(self.move_offset * 0.05) * self.move_range)
        self.update_sprites()

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Jumping Difficulties")
        self.clock = pygame.time.Clock()
        self.fullscreen = False

        self.font = pygame.font.Font(None, 36)
        self.font_large = pygame.font.Font(None, 72)
        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_tiny = pygame.font.Font(None, 18)

        self.music_volume = 0.7
        self.sfx_volume = 0.7

        self.wing_flap_sound = pygame.mixer.Sound("wingflap.mp3")

        pygame.mixer.music.load("mainmenu.mp3")
        pygame.mixer.music.set_volume(self.music_volume)
        pygame.mixer.music.play(-1)
        self.current_music = "menu"

        self.bird_sprites = {
            'idle': pygame.image.load("sprite1.png").convert_alpha(),
            'wing_up': pygame.image.load("sprite2.png").convert_alpha(),
            'wing_down': pygame.image.load("sprite3.png").convert_alpha()
        }

        self.cloud_sprites = [
            pygame.image.load("cloud1_sprite.png").convert_alpha(),
            pygame.image.load("cloud2_sprite.png").convert_alpha(),
            pygame.image.load("cloud3_sprite.png").convert_alpha()
        ]

        self.sky_sprite = pygame.transform.scale(
            pygame.image.load("afternoon_sprite.png").convert(),
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )

        self.ground_sprite = pygame.image.load("ground_sprite.png").convert()
        self.pipe_sprite = pygame.image.load("pipe_sprite.png").convert_alpha()

        self.gradient_cache = {}

        self.state = GameState.MENU
        self.current_level = 1
        self.max_level = 30
        self.unlocked_levels = 1
        self.score = 0
        self.high_score = 0
        self.level_time = 0
        self.combo = 0
        self.max_combo = 0
        self.level_score = 0
        self.level_high_scores = {}
        self.level_best_times = {}

        self.bird = None
        self.pipes = []
        self.particles = []
        self.clouds = [Cloud(self.cloud_sprites) for _ in range(5)]

        self.screen_shake = 0
        self.slow_motion = False
        self.slow_motion_time = 0

        self.ground_scroll = 0
        self.fade_alpha = 0
        self.transition_timer = 0
        self.transition_duration = 60

        self.dragging_music = False
        self.dragging_sfx = False


        self.cheat_sequence = []
        self.cheat_start_time = 0
        self.cheat_time_window = 1.6
        self.cheat_unlocked_message_timer = 0

        self.load_progress()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    def switch_to_game_music(self, level=None):

        if level is None:
            level = self.current_level


        level = max(1, min(30, level))

        music_name = f"game{level}"

        if self.current_music != music_name:
            pygame.mixer.music.fadeout(1000)
            pygame.time.wait(1000)
            pygame.mixer.music.load(f"game{level}.mp3")
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1)
            self.current_music = music_name

    def switch_to_menu_music(self):
        if self.current_music != "menu":
            pygame.mixer.music.stop()
            pygame.mixer.music.load("mainmenu.mp3")
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1)
            self.current_music = "menu"

    def apply_volume_settings(self):
        pygame.mixer.music.set_volume(self.music_volume)
        self.wing_flap_sound.set_volume(self.sfx_volume)

    def check_cheat_code(self, key):

        current_time = time.time()


        if not self.cheat_sequence or (current_time - self.cheat_start_time) > self.cheat_time_window:
            self.cheat_sequence = []
            self.cheat_start_time = current_time


        if key == pygame.K_UP:
            self.cheat_sequence.append('UP')
        elif key == pygame.K_DOWN:
            self.cheat_sequence.append('DOWN')
        else:
            return

        if len(self.cheat_sequence) == 4:
            if self.cheat_sequence == ['UP', 'UP', 'DOWN', 'DOWN']:

                self.unlocked_levels = self.max_level
                self.save_progress()
                self.cheat_unlocked_message_timer = 180  # Show message for 3 seconds

                self.add_celebration_particles()

            self.cheat_sequence = []
        elif len(self.cheat_sequence) > 4:

            self.cheat_sequence = []

    def get_pipe_gap(self):
        base_gap = 200
        min_gap = 130

        if self.current_level <= 10:

            gap = base_gap - (self.current_level - 1) * 4
        elif self.current_level <= 20:

            gap = 160 - (self.current_level - 11) * 2
        else:

            gap = 140 - (self.current_level - 21) * 1

        return max(min_gap, int(gap))

    def get_pipe_speed(self):
        base_speed = 3
        max_speed = 7


        if self.current_level <= 10:

            speed = base_speed + (self.current_level - 1) * 0.2
        elif self.current_level <= 20:

            speed = 4.8 + (self.current_level - 11) * 0.15
        else:

            speed = 6.3 + (self.current_level - 21) * 0.07

        return min(speed, max_speed) * (0.5 if self.slow_motion else 1)

    def get_pipe_distance(self):
        base_distance = 300
        min_distance = 210


        if self.current_level <= 10:

            distance = base_distance - (self.current_level - 1) * 5
        elif self.current_level <= 20:

            distance = 255 - (self.current_level - 11) * 3
        else:

            distance = 225 - (self.current_level - 21) * 1.5

        return max(min_distance, int(distance))

    def get_level_duration(self):
        base_duration = 30
        max_duration = 90
        increase_per_level = (max_duration - base_duration) / self.max_level
        duration = base_duration + (self.current_level - 1) * increase_per_level
        return int(duration * FPS)

    def load_progress(self):
        try:
            with open("save.json", "r") as f:
                data = json.load(f)
                self.unlocked_levels = data.get("unlocked_levels", 1)
                self.high_score = data.get("high_score", 0)
                self.level_high_scores = data.get("level_high_scores", {})
                self.level_best_times = data.get("level_best_times", {})
                self.music_volume = data.get("music_volume", 0.7)
                self.sfx_volume = data.get("sfx_volume", 0.7)
                self.apply_volume_settings()
        except:
            pass

    def save_progress(self):
        data = {
            "unlocked_levels": self.unlocked_levels,
            "high_score": self.high_score,
            "level_high_scores": self.level_high_scores,
            "level_best_times": self.level_best_times,
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume
        }
        with open("save.json", "w") as f:
            json.dump(data, f)

    def reset_level(self):
        self.bird = Bird(150, SCREEN_HEIGHT // 2, self.bird_sprites, self.wing_flap_sound)
        self.particles = []
        self.level_time = 0
        self.combo = 0
        self.screen_shake = 0
        self.slow_motion = False
        self.level_duration = self.get_level_duration()
        self.level_score = 0
        self.pipes = []

    def add_explosion(self, x, y, color, count=15):
        if len(self.particles) < MAX_PARTICLES:
            for _ in range(min(count, MAX_PARTICLES - len(self.particles))):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(2, 8)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                self.particles.append(
                    Particle(x, y, color, vx, vy, random.randint(3, 6), random.randint(20, 40))
                )

    def add_celebration_particles(self):
        for _ in range(30):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(-50, SCREEN_HEIGHT // 2)
            color = random.choice([GOLD, YELLOW, ORANGE, CYAN, GREEN])
            self.particles.append(
                Particle(x, y, color,
                        velocity_x=random.uniform(-3, 3),
                        velocity_y=random.uniform(2, 6),
                        size=random.randint(3, 6),
                        lifetime=random.randint(40, 80))
            )

    def add_score_particles(self, x, y):
        if len(self.particles) < MAX_PARTICLES - 5:
            for _ in range(5):
                self.particles.append(
                    Particle(x, y, random.choice([GOLD, YELLOW, WHITE]),
                            velocity_x=random.uniform(-3, 3),
                            velocity_y=random.uniform(-5, -2),
                            size=3, lifetime=30)
                )

    def shake_screen(self, intensity):
        self.screen_shake = intensity

    def draw_gradient_rect(self, surface, color1, color2, rect):
        cache_key = (color1, color2, rect.width, rect.height)
        if cache_key not in self.gradient_cache:
            grad_surface = pygame.Surface((rect.width, rect.height))
            for y in range(rect.height):
                ratio = y / rect.height
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                pygame.draw.line(grad_surface, (r, g, b), (0, y), (rect.width, y))
            self.gradient_cache[cache_key] = grad_surface
            if len(self.gradient_cache) > 10:
                self.gradient_cache.clear()

        surface.blit(self.gradient_cache[cache_key], (rect.x, rect.y))

    def draw_button(self, text, rect, mouse_pos, icon=None):
        hover = rect.collidepoint(mouse_pos)

        if hover:
            rect = rect.inflate(10, 5)

        color = WHITE if hover else (50, 50, 50)
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, GOLD if hover else WHITE, rect, 3, border_radius=10)

        text_color = BLACK if hover else WHITE
        text_surf = self.font.render(text, True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

        return hover

    def draw_text_with_shadow(self, text, font, color, x, y, shadow_color=BLACK, shadow_offset=2, centered=False):
        shadow = font.render(text, True, shadow_color)
        text_surf = font.render(text, True, color)

        if centered:
            shadow_rect = shadow.get_rect(center=(x + shadow_offset, y + shadow_offset))
            text_rect = text_surf.get_rect(center=(x, y))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(text_surf, text_rect)
        else:
            self.screen.blit(shadow, (x + shadow_offset, y + shadow_offset))
            self.screen.blit(text_surf, (x, y))

    def draw_slider(self, x, y, width, value, label, mouse_pos, mouse_pressed):
        slider_rect = pygame.Rect(x, y + 30, width, 10)
        handle_x = x + int(value * width)
        handle_rect = pygame.Rect(handle_x - 8, y + 22, 16, 26)

        self.draw_text_with_shadow(label, self.font_medium, WHITE, x, y)

        vol_text = self.font_small.render(f"{int(value * 100)}%", True, GOLD)
        self.screen.blit(vol_text, (x + width + 20, y + 28))

        pygame.draw.rect(self.screen, DARK_GRAY, slider_rect, border_radius=5)
        pygame.draw.rect(self.screen, GOLD, (x, y + 30, int(value * width), 10), border_radius=5)
        pygame.draw.rect(self.screen, WHITE, slider_rect, 2, border_radius=5)

        handle_color = GOLD if handle_rect.collidepoint(mouse_pos) else WHITE
        pygame.draw.rect(self.screen, handle_color, handle_rect, border_radius=4)
        pygame.draw.rect(self.screen, BLACK, handle_rect, 2, border_radius=4)

        new_value = value
        if mouse_pressed and handle_rect.collidepoint(mouse_pos):
            return value, True
        elif mouse_pressed and slider_rect.collidepoint(mouse_pos):
            new_value = (mouse_pos[0] - x) / width
            new_value = max(0, min(1, new_value))
            return new_value, True

        return value, False

    def draw_settings(self):
        self.draw_gradient_rect(self.screen, BLUE, DARK_BLUE,
                               pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)

        self.draw_text_with_shadow("SETTINGS", self.font_large, GOLD,
                                   SCREEN_WIDTH // 2, 80, centered=True)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()[0]

        music_y = 200
        new_music_vol, music_dragging = self.draw_slider(
            200, music_y, 300, self.music_volume, "Music Volume", mouse_pos, mouse_pressed
        )

        if new_music_vol != self.music_volume or music_dragging:
            self.music_volume = new_music_vol
            pygame.mixer.music.set_volume(self.music_volume)
            self.dragging_music = music_dragging

        sfx_y = 300
        new_sfx_vol, sfx_dragging = self.draw_slider(
            200, sfx_y, 300, self.sfx_volume, "SFX Volume", mouse_pos, mouse_pressed
        )

        if new_sfx_vol != self.sfx_volume or sfx_dragging:
            self.sfx_volume = new_sfx_vol
            self.wing_flap_sound.set_volume(self.sfx_volume)
            self.dragging_sfx = sfx_dragging

        back_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 420, 200, 50)
        if self.draw_button("Back", back_rect, mouse_pos) and mouse_pressed:
            if not self.dragging_music and not self.dragging_sfx:
                self.save_progress()
                self.state = GameState.MENU
                pygame.time.wait(200)

    def draw_menu(self):
        self.draw_gradient_rect(self.screen, BLUE, DARK_BLUE,
                               pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)


        self.particles = [p for p in self.particles if not p.is_dead()][:MAX_PARTICLES]
        for particle in self.particles:
            particle.update()
            particle.draw(self.screen)

        self.draw_text_with_shadow("JUMPING DIFFICULTIES", self.font_large, GOLD,
                                   SCREEN_WIDTH // 2, 80, centered=True)

        self.draw_text_with_shadow("By the Slamex Team", self.font_small, WHITE,
                                   SCREEN_WIDTH // 2, 145, centered=True)

        mouse_pos = pygame.mouse.get_pos()

        start_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 220, 200, 50)
        level_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 285, 200, 50)
        settings_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 350, 200, 50)
        quit_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 415, 200, 50)

        if self.draw_button("Start Game", start_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.current_level = 1
            self.score = 0
            self.reset_level()
            self.switch_to_game_music(self.current_level)
            self.state = GameState.PLAYING
            pygame.time.wait(200)

        if self.draw_button("Level Select", level_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.state = GameState.LEVEL_SELECT
            pygame.time.wait(200)

        if self.draw_button("Settings", settings_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.state = GameState.SETTINGS
            pygame.time.wait(200)

        if self.draw_button("Quit", quit_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            return False

        self.draw_text_with_shadow(f"Unlocked: {self.unlocked_levels}/{self.max_level}",
                                   self.font_small, WHITE, SCREEN_WIDTH - 270, 30)

        hint_text = self.font_small.render("Press F11 for Fullscreen", True, LIGHT_GRAY)
        self.screen.blit(hint_text, (20, SCREEN_HEIGHT - 30))


        if self.cheat_unlocked_message_timer > 0:
            self.cheat_unlocked_message_timer -= 1
            alpha = min(255, self.cheat_unlocked_message_timer * 2)

            message_surf = self.font_large.render("ALL LEVELS UNLOCKED!", True, GOLD)
            message_rect = message_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))


            temp_surf = pygame.Surface(message_surf.get_size())
            temp_surf.fill(BLACK)
            temp_surf.blit(message_surf, (0, 0))
            temp_surf.set_alpha(alpha)


            shadow_surf = self.font_large.render("ALL LEVELS UNLOCKED!", True, BLACK)
            shadow_rect = shadow_surf.get_rect(center=(SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 + 3))
            shadow_temp = pygame.Surface(shadow_surf.get_size())
            shadow_temp.fill(BLACK)
            shadow_temp.blit(shadow_surf, (0, 0))
            shadow_temp.set_alpha(alpha)

            self.screen.blit(shadow_temp, shadow_rect)
            self.screen.blit(temp_surf, message_rect)

        return True

    def draw_level_select(self):
        self.draw_gradient_rect(self.screen, BLUE, DARK_BLUE,
                               pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)


        self.particles = [p for p in self.particles if not p.is_dead()][:MAX_PARTICLES]
        for particle in self.particles:
            particle.update()
            particle.draw(self.screen)

        self.draw_text_with_shadow("SELECT LEVEL", self.font_large, GOLD,
                                   SCREEN_WIDTH // 2, 50, centered=True)

        mouse_pos = pygame.mouse.get_pos()

        back_rect = pygame.Rect(50, 50, 100, 40)
        if self.draw_button("Back", back_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.state = GameState.MENU
            pygame.time.wait(200)

        cols = 10
        box_size = 60
        spacing = 10
        start_x = (SCREEN_WIDTH - (cols * (box_size + spacing))) // 2
        start_y = 120

        for level in range(1, self.max_level + 1):
            row = (level - 1) // cols
            col = (level - 1) % cols
            x = start_x + col * (box_size + spacing)
            y = start_y + row * (box_size + spacing)

            rect = pygame.Rect(x, y, box_size, box_size)

            if level <= self.unlocked_levels:
                if level <= 10:
                    color = GREEN
                    border_color = DARK_GREEN
                elif level <= 20:
                    color = ORANGE
                    border_color = (200, 100, 0)
                elif level <= 30:
                    color = RED
                    border_color = (150, 0, 0)
                else:
                    color = PURPLE
                    border_color = (100, 50, 150)

                if rect.collidepoint(mouse_pos):
                    color = tuple(min(c + 50, 255) for c in color)

                    level_key = str(level)
                    if level_key in self.level_high_scores or level_key in self.level_best_times:
                        stats_y = y + box_size + 5
                        if level_key in self.level_high_scores:
                            score_text = self.font_small.render(
                                f"Best: {self.level_high_scores[level_key]}", True, GOLD)
                            self.screen.blit(score_text, (x - 10, stats_y))
                        if level_key in self.level_best_times:
                            time_text = self.font_small.render(
                                f"Time: {self.level_best_times[level_key]}s", True, CYAN)
                            self.screen.blit(time_text, (x - 10, stats_y + 20))

                pygame.draw.rect(self.screen, color, rect, border_radius=8)
                pygame.draw.rect(self.screen, border_color, rect, 3, border_radius=8)

                level_text = self.font.render(str(level), True, WHITE)
                text_rect = level_text.get_rect(center=rect.center)
                self.screen.blit(level_text, text_rect)

                if rect.collidepoint(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    self.current_level = level
                    self.score = 0
                    self.reset_level()
                    self.switch_to_game_music(self.current_level)
                    self.state = GameState.PLAYING
                    pygame.time.wait(200)
            else:
                pygame.draw.rect(self.screen, GRAY, rect, border_radius=8)
                pygame.draw.rect(self.screen, (60, 60, 60), rect, 3, border_radius=8)


        if self.cheat_unlocked_message_timer > 0:
            self.cheat_unlocked_message_timer -= 1
            alpha = min(255, self.cheat_unlocked_message_timer * 2)

            message_surf = self.font_large.render("ALL LEVELS UNLOCKED!", True, GOLD)
            message_rect = message_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

            temp_surf = pygame.Surface(message_surf.get_size())
            temp_surf.fill(BLACK)
            temp_surf.blit(message_surf, (0, 0))
            temp_surf.set_alpha(alpha)

            shadow_surf = self.font_large.render("ALL LEVELS UNLOCKED!", True, BLACK)
            shadow_rect = shadow_surf.get_rect(center=(SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 + 3))
            shadow_temp = pygame.Surface(shadow_surf.get_size())
            shadow_temp.fill(BLACK)
            shadow_temp.blit(shadow_surf, (0, 0))
            shadow_temp.set_alpha(alpha)

            self.screen.blit(shadow_temp, shadow_rect)
            self.screen.blit(temp_surf, message_rect)

    def draw_level_complete(self):
        self.draw_gradient_rect(self.screen, BLUE, DARK_BLUE,
                               pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)

        self.particles = [p for p in self.particles if not p.is_dead()][:MAX_PARTICLES]
        for particle in self.particles:
            particle.update()
            particle.draw(self.screen)

        if random.random() < 0.15 and len(self.particles) < MAX_PARTICLES:
            x = random.randint(0, SCREEN_WIDTH)
            color = random.choice([GOLD, YELLOW, ORANGE])
            self.particles.append(
                Particle(x, -10, color,
                        velocity_x=random.uniform(-2, 2),
                        velocity_y=random.uniform(3, 6),
                        size=random.randint(3, 6),
                        lifetime=random.randint(40, 70))
            )

        self.draw_text_with_shadow("LEVEL COMPLETE!", self.font_large, GOLD,
                                   SCREEN_WIDTH // 2, 100, centered=True)

        self.draw_text_with_shadow(f"Level {self.current_level - 1} Complete!",
                                   self.font, WHITE, SCREEN_WIDTH // 2, 200, centered=True)

        self.draw_text_with_shadow(f"Level Score: {self.level_score}",
                                   self.font, GOLD, SCREEN_WIDTH // 2, 260, centered=True)

        self.draw_text_with_shadow(f"Total Score: {self.score}",
                                   self.font_small, WHITE, SCREEN_WIDTH // 2, 310, centered=True)

        progress = self.transition_timer / self.transition_duration
        bar_width = 400
        bar_height = 20
        bar_x = SCREEN_WIDTH // 2 - bar_width // 2
        bar_y = 380

        pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=10)
        pygame.draw.rect(self.screen, GOLD, (bar_x, bar_y, int(bar_width * progress), bar_height), border_radius=10)
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2, border_radius=10)

        self.draw_text_with_shadow("Preparing next level...", self.font_small, WHITE,
                                   SCREEN_WIDTH // 2, 420, centered=True)

        self.transition_timer += 1

        if self.transition_timer >= self.transition_duration - 20:
            fade_amount = (self.transition_timer - (self.transition_duration - 20)) / 20
            fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade_surface.fill(BLACK)
            fade_surface.set_alpha(int(255 * fade_amount))
            self.screen.blit(fade_surface, (0, 0))

        if self.transition_timer >= self.transition_duration:
            self.transition_timer = 0
            self.reset_level()
            # Switch to the new level's music
            self.switch_to_game_music(self.current_level)
            self.state = GameState.TRANSITION
            self.fade_alpha = 255

    def draw_transition(self):
        self.draw_game()

        if self.fade_alpha > 0:
            fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade_surface.fill(BLACK)
            fade_surface.set_alpha(self.fade_alpha)
            self.screen.blit(fade_surface, (0, 0))

            self.fade_alpha -= 8
            if self.fade_alpha <= 0:
                self.fade_alpha = 0
                self.state = GameState.PLAYING

    def draw_hud_panel(self, x, y, width, height, title, value, color=WHITE):
        panel_surface = pygame.Surface((width, height))
        panel_surface.set_alpha(180)
        panel_surface.fill(DARK_GRAY)
        self.screen.blit(panel_surface, (x, y))

        pygame.draw.rect(self.screen, color, (x, y, width, height), 2, border_radius=5)

        title_surf = self.font_small.render(title, True, LIGHT_GRAY)
        self.screen.blit(title_surf, (x + 5, y + 3))

        value_surf = self.font_medium.render(str(value), True, color)
        self.screen.blit(value_surf, (x + 5, y + 25))

    def draw_game(self):
        shake_x = shake_y = 0
        if self.screen_shake > 0:
            shake_x = random.randint(-self.screen_shake, self.screen_shake)
            shake_y = random.randint(-self.screen_shake, self.screen_shake)
            self.screen_shake -= 1

        self.screen.blit(self.sky_sprite, (shake_x, shake_y))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)

        pipe_speed = self.get_pipe_speed()
        pipe_gap = self.get_pipe_gap()
        pipe_distance = self.get_pipe_distance()

        self.ground_scroll -= pipe_speed
        ground_width = self.ground_sprite.get_width()
        if self.ground_scroll <= -ground_width:
            self.ground_scroll = 0

        ground_y = SCREEN_HEIGHT - 50
        scaled_ground = pygame.transform.scale(self.ground_sprite, (ground_width, 50))

        num_tiles = (SCREEN_WIDTH // ground_width) + 2
        for i in range(num_tiles):
            self.screen.blit(scaled_ground, (i * ground_width + self.ground_scroll + shake_x, ground_y + shake_y))

        if self.bird.alive:
            self.level_time += 1

            if self.slow_motion:
                self.slow_motion_time -= 1
                if self.slow_motion_time <= 0:
                    self.slow_motion = False

            if len(self.pipes) == 0 or self.pipes[-1].x < SCREEN_WIDTH - pipe_distance:
                self.pipes.append(MovingPipe(SCREEN_WIDTH, pipe_gap,
                                           self.current_level, self.pipe_sprite))

        for pipe in self.pipes[:]:
            pipe.update(pipe_speed)
            pipe.draw(self.screen)

            if pipe.x < -PIPE_WIDTH:
                self.pipes.remove(pipe)

            if not pipe.passed and pipe.x < self.bird.x:
                pipe.passed = True
                points = 1
                self.score += points
                self.level_score += points
                self.combo += 1
                self.max_combo = max(self.max_combo, self.combo)

                self.add_score_particles(pipe.x + PIPE_WIDTH // 2,
                                        pipe.height + pipe.pipe_gap // 2)

            if pipe.check_collision(self.bird) and not self.bird.shield_active:
                self.bird.alive = False
                self.combo = 0
                self.shake_screen(10)
                self.add_explosion(self.bird.x, self.bird.y, YELLOW, 20)

        self.particles = [p for p in self.particles if not p.is_dead()][:MAX_PARTICLES]
        for particle in self.particles:
            particle.update()
            particle.draw(self.screen)

        self.bird.update()
        self.bird.draw(self.screen)

        if self.bird.y < 0 or self.bird.y > SCREEN_HEIGHT - 50:
            if not self.bird.shield_active:
                self.bird.alive = False
                self.shake_screen(10)
                self.add_explosion(self.bird.x, self.bird.y, ORANGE, 20)

        time_left = max(0, (self.level_duration - self.level_time) // FPS)

        self.draw_hud_panel(10, 10, 150, 55, "SCORE", self.score, GOLD)
        self.draw_hud_panel(170, 10, 100, 55, "LEVEL", self.current_level, CYAN)

        time_color = RED if time_left <= 5 else YELLOW if time_left <= 10 else WHITE
        self.draw_hud_panel(280, 10, 100, 55, "TIME", f"{time_left}s", time_color)

        if self.combo > 0:
            self.draw_hud_panel(SCREEN_WIDTH - 160, 10, 150, 55, "COMBO", f"x{self.combo}", ORANGE)

        level_key = str(self.current_level)
        if level_key in self.level_high_scores:
            hs_panel = pygame.Surface((150, 40))
            hs_panel.set_alpha(150)
            hs_panel.fill(DARK_GRAY)
            self.screen.blit(hs_panel, (SCREEN_WIDTH - 160, SCREEN_HEIGHT - 50))
            pygame.draw.rect(self.screen, GOLD, (SCREEN_WIDTH - 160, SCREEN_HEIGHT - 50, 150, 40), 2, border_radius=5)

            hs_text = self.font_small.render(f"Level Best: {self.level_high_scores[level_key]}",
                                            True, GOLD)
            self.screen.blit(hs_text, (SCREEN_WIDTH - 155, SCREEN_HEIGHT - 42))

        if not self.bird.alive:
            level_key = str(self.current_level)
            if level_key not in self.level_high_scores or self.level_score > self.level_high_scores[level_key]:
                self.level_high_scores[level_key] = self.level_score

            self.fade_alpha = 0
            self.state = GameState.GAME_OVER

            if self.score > self.high_score:
                self.high_score = self.score
                self.save_progress()

        if self.level_time >= self.level_duration:
            level_key = str(self.current_level)
            time_taken = self.level_time // FPS
            if level_key not in self.level_best_times or time_taken < self.level_best_times[level_key]:
                self.level_best_times[level_key] = time_taken

            if level_key not in self.level_high_scores or self.level_score > self.level_high_scores[level_key]:
                self.level_high_scores[level_key] = self.level_score

            if self.current_level >= self.unlocked_levels:
                self.unlocked_levels = self.current_level + 1
                self.save_progress()

            if self.current_level < self.max_level:
                self.current_level += 1
                self.state = GameState.LEVEL_COMPLETE
                self.transition_timer = 0
                self.fade_alpha = 0
                self.add_celebration_particles()
            else:
                self.state = GameState.GAME_OVER
                self.fade_alpha = 0
                if self.score > self.high_score:
                    self.high_score = self.score
                    self.save_progress()

    def draw_game_over(self):
        self.draw_gradient_rect(self.screen, BLUE, DARK_BLUE,
                               pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)

        if self.fade_alpha < 255:
            self.fade_alpha += 8

        self.draw_text_with_shadow("GAME OVER", self.font_large, RED,
                                   SCREEN_WIDTH // 2, 100, centered=True)

        self.draw_text_with_shadow(f"Final Score: {self.score}", self.font, GOLD,
                                   SCREEN_WIDTH // 2, 200, centered=True)

        self.draw_text_with_shadow(f"High Score: {self.high_score}", self.font_small, WHITE,
                                   SCREEN_WIDTH // 2, 250, centered=True)

        self.draw_text_with_shadow(f"Level Reached: {self.current_level}", self.font_small, CYAN,
                                   SCREEN_WIDTH // 2, 290, centered=True)

        mouse_pos = pygame.mouse.get_pos()

        retry_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 350, 200, 50)
        menu_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 420, 200, 50)

        if self.draw_button("Retry", retry_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.reset_level()
            self.switch_to_game_music(self.current_level)
            self.state = GameState.PLAYING
            pygame.time.wait(200)

        if self.draw_button("Menu", menu_rect, mouse_pos) and pygame.mouse.get_pressed()[0]:
            self.switch_to_menu_music()
            self.state = GameState.MENU
            self.particles = []
            pygame.time.wait(200)

        if self.fade_alpha < 255:
            fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            fade_surface.fill(BLACK)
            fade_surface.set_alpha(255 - self.fade_alpha)
            self.screen.blit(fade_surface, (0, 0))

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    # Check for cheat code
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        self.check_cheat_code(event.key)

                    if event.key == pygame.K_SPACE and self.state in (GameState.PLAYING, GameState.LEVEL_COMPLETE, GameState.TRANSITION) and self.bird and self.bird.alive:
                        self.bird.jump()
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif event.key == pygame.K_ESCAPE:
                        if self.state == GameState.PLAYING:
                            self.state = GameState.PAUSED
                        else:
                            self.state = GameState.MENU

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state in (GameState.PLAYING, GameState.LEVEL_COMPLETE, GameState.TRANSITION) and self.bird and self.bird.alive:
                        self.bird.jump()

                elif event.type == pygame.MOUSEBUTTONUP:
                    self.dragging_music = False
                    self.dragging_sfx = False

            if self.state == GameState.MENU:
                running = self.draw_menu()
            elif self.state == GameState.LEVEL_SELECT:
                self.draw_level_select()
            elif self.state == GameState.PLAYING:
                self.draw_game()
            elif self.state == GameState.LEVEL_COMPLETE:
                self.draw_level_complete()
            elif self.state == GameState.TRANSITION:
                self.draw_transition()
            elif self.state == GameState.GAME_OVER:
                self.draw_game_over()
            elif self.state == GameState.SETTINGS:
                self.draw_settings()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
