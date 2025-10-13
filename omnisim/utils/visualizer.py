import pygame
import math
import sys

# ---------- Visualization Helper ----------

class EnvVisualizer:
    def __init__(self, env_node, width=1600, height=800, scale=30):
        """env_node: instance of your EnvironmentNode"""
        self.node = env_node
        self.width = width
        self.height = height
        self.scale = scale   # pixels per world unit
        self.center = (width // 2, height // 2)
        self.running = True

        pygame.init()
        pygame.display.set_caption(f"{env_node.env_name} Visualizer")
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 14)

    def world_to_screen(self, x, y):
        """Convert world (x,y) to screen coordinates (flip y-axis)."""
        sx = int(self.center[0] + x * self.scale)
        sy = int(self.center[1] - y * self.scale)
        return (sx, sy)

    def draw_arrow(self, pos, theta, color=(255, 255, 255)):
        """Draw heading arrow."""
        length = 15
        end = (
            pos[0] + length * math.cos(math.radians(theta)),
            pos[1] - length * math.sin(math.radians(theta))
        )
        pygame.draw.line(self.screen, color, pos, end, 2)

    def draw_entity(self, x, y, theta, color, label):
        pos = self.world_to_screen(x, y)
        pygame.draw.circle(self.screen, color, pos, 6)
        self.draw_arrow(pos, theta, color)
        text = self.font.render(label, True, (255, 255, 255))
        self.screen.blit(text, (pos[0] + 8, pos[1] - 8))

    def draw_recursive(self, data, prefix=""):
        """Recursively draw all pose nodes in self.poses."""
        if not isinstance(data, dict):
            return
        for name, val in data.items():
            if isinstance(val, dict):
                if all(k in val for k in ["x", "y", "theta"]):
                    # This is a pose dict
                    color = (0, 255, 0) if "sensor" in prefix else (255, 165, 0)
                    if "composite" in prefix:
                        color = (0, 128, 255)
                    self.draw_entity(val["x"], val["y"], val["theta"], color, name)
                else:
                    # Recurse deeper
                    self.draw_recursive(val, prefix + "." + name)
            elif isinstance(val, list):
                for v in val:
                    self.draw_recursive(v, prefix + "." + name)

    def render(self):
        """Main render loop."""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    sys.exit()

            self.screen.fill((20, 20, 20))
            self.draw_recursive(self.node.poses)
            pygame.display.flip()
            self.clock.tick(10)  # FPS limit

    def stop(self):
        self.running = False
        pygame.quit()
