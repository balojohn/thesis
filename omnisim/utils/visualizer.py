import pygame
import math
import sys

class EnvVisualizer:
    def __init__(self, env_node):
        """
        Visualizer for generated environment nodes (e.g., HomeNode).
        Automatically scales to fit your screen while keeping aspect ratio.
        Supports interactive zooming and panning.
        """
        self.node = env_node
        self.running = True
        self._last_sensor_values = {}

        # === Environment info ===
        self.env_width = getattr(env_node, "width", 20.0)
        self.env_height = getattr(env_node, "height", 20.0)
        self.properties = getattr(env_node, "properties", {})

        # === Determine window size dynamically ===
        pygame.init()
        info = pygame.display.Info()
        max_w, max_h = int(info.current_w * 0.9), int(info.current_h * 0.9)

        env_aspect = self.env_width / self.env_height
        screen_aspect = max_w / max_h
        if env_aspect > screen_aspect:
            self.width = max_w
            self.height = int(max_w / env_aspect)
        else:
            self.height = max_h
            self.width = int(max_h * env_aspect)

        # Compute scale factor (pixels per world unit)
        self.scale = self.width / self.env_width

        # === Setup pygame ===
        pygame.display.set_caption(f"{env_node.env_name} Environment")

        # --- Add extra width for side info panel ---
        self.panel_width = 520  # enough space for all sensor info
        total_width = self.width + self.panel_width

        # Main display
        self.screen = pygame.display.set_mode((total_width, self.height))

        # --- Fonts and clock ---
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 14)
        self.bigfont = pygame.font.SysFont("consolas", 18, bold=True)
        
        # === Colors ===
        self.bg_color = (25, 25, 30)
        self.grid_color = (40, 40, 45)
        self.border_color = (100, 100, 100)
        self.text_color = (230, 230, 230)
        self.colors = {
            "sensor": (0, 200, 255),
            "actuator": (255, 180, 0),
            "composite": (255, 100, 120),
            "actor": (180, 120, 255),
            "obstacle": (200, 200, 200),
        }

        # === Camera control (zoom + pan) ===
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom_step = 1.1
        self.pan_speed = 20.0
        self.dragging = False
        self.drag_start = None

    # -----------------------------------------------------
    # ---------------- DRAW HELPERS -----------------------
    # -----------------------------------------------------

    def world_to_screen(self, x, y):
        """Map world coords (0,0 bottom-left) → screen coords (top-left origin)."""
        sx = int((x - self.pan_x) * self.scale * self.zoom)
        sy = int(self.height - (y - self.pan_y) * self.scale * self.zoom)
        return (sx, sy)

    def draw_arrow(self, pos, theta, color=(255, 255, 255)):
        length = 14
        end = (
            pos[0] + length * math.cos(math.radians(theta)),
            pos[1] - length * math.sin(math.radians(theta)),
        )
        pygame.draw.line(self.screen, color, pos, end, 2)
        head_angle = math.radians(theta)
        hx1 = end[0] - 5 * math.cos(head_angle - 0.4)
        hy1 = end[1] + 5 * math.sin(head_angle - 0.4)
        hx2 = end[0] - 5 * math.cos(head_angle + 0.4)
        hy2 = end[1] + 5 * math.sin(head_angle + 0.4)
        pygame.draw.polygon(self.screen, color, [(end[0], end[1]), (hx1, hy1), (hx2, hy2)])

    def draw_grid(self):
        step = max(1, int(self.scale * self.zoom))
        for x in range(0, self.width, step):
            pygame.draw.line(self.screen, self.grid_color, (x, 0), (x, self.height))
        for y in range(0, self.height, step):
            pygame.draw.line(self.screen, self.grid_color, (0, y), (self.width, y))

    def draw_background(self):
        self.screen.fill(self.bg_color)
        self.draw_grid()
        pygame.draw.rect(self.screen, self.border_color, (0, 0, self.width - 1, self.height - 1), 2)

        # --- Environment name ---
        name_text = self.bigfont.render(f"{self.node.env_name} Environment", True, (180, 220, 255))
        self.screen.blit(name_text, (12, 10))

        # --- Display environmental properties ---
        y_offset = 36
        for k, v in self.properties.items():
            txt = self.font.render(f"{k.capitalize()}: {v}", True, self.text_color)
            self.screen.blit(txt, (12, y_offset))
            y_offset += 18

        # --- Camera overlay ---
        zoom_text = self.font.render(f"Zoom: {self.zoom:.2f}x", True, (180, 220, 255))
        pan_text = self.font.render(f"Pan: ({self.pan_x:.1f}, {self.pan_y:.1f})", True, (180, 220, 255))
        self.screen.blit(zoom_text, (self.width - 160, 10))
        self.screen.blit(pan_text, (self.width - 200, 28))

    # -----------------------------------------------------
    # ---------------- SENSOR TABLE -----------------------
    # -----------------------------------------------------

    def draw_sensor_table(self):
        """Draw a right-side panel listing sensors and their current values/detections."""
        sensor_values = getattr(self.node, "sensor_values", {})
        env_props = getattr(self.node, "env_properties", {})

        # --- Layout ---
        panel_x = self.width  # start of the right panel
        panel_y = 40
        panel_width = self.panel_width
        row_h = 28

        # --- Background ---
        pygame.draw.rect(
            self.screen, (28, 30, 38),
            (panel_x, panel_y, panel_width, self.height - panel_y - 16),
            border_radius=8,
        )
        pygame.draw.rect(
            self.screen, (75, 80, 95),
            (panel_x, panel_y, panel_width, self.height - panel_y - 16),
            2, border_radius=8,
        )

        # --- Title ---
        title = self.bigfont.render("Affection results", True, (210, 220, 255))
        self.screen.blit(title, (panel_x + 16, panel_y + 12))
        y = panel_y + 48

        # --- Environment section ---
        self.screen.blit(self.font.render("Environment", True, (160, 200, 255)), (panel_x + 14, y))
        y += 6
        pygame.draw.line(self.screen, (70, 70, 80), (panel_x + 12, y), (panel_x + panel_width - 12, y))
        y += 12

        for prop, val in env_props.items():
            label = prop.replace("_", " ").title()
            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            self.screen.blit(self.font.render(label, True, (200, 200, 200)), (panel_x + 22, y))
            self.screen.blit(self.font.render(val_str, True, (160, 255, 160)), (panel_x + 210, y))
            y += row_h

        # --- Separator ---
        y += 8
        pygame.draw.line(self.screen, (95, 95, 110), (panel_x + 10, y), (panel_x + panel_width - 10, y))
        y += 18

        # --- Sensor section header ---
        self.screen.blit(self.font.render("Sensors", True, (160, 200, 255)), (panel_x + 14, y))
        y += 6
        pygame.draw.line(self.screen, (70, 70, 80), (panel_x + 12, y), (panel_x + panel_width - 12, y))
        y += 14

        headers = ["Name", "Property", "Value", "Detection"]
        col_x = [panel_x + 14, panel_x + 130, panel_x + 250, panel_x + 360]
        for i, h in enumerate(headers):
            self.screen.blit(self.font.render(h, True, (150, 160, 190)), (col_x[i], y))
        y += 22
        pygame.draw.line(self.screen, (70, 70, 80), (panel_x + 10, y), (panel_x + panel_width - 10, y))
        y += 12

        # --- Recursive sensor collector ---
        def collect_sensors(node_section):
            sensors = {}
            if not isinstance(node_section, dict):
                return sensors
            for name, node in node_section.items():
                if not isinstance(node, dict):
                    continue
                if node.get("class") == "sensor":
                    sensors[name] = node
                else:
                    sensors.update(collect_sensors(node))
            return sensors

        all_sensors = collect_sensors(self.node.nodes)

        # --- Draw rows ---
        for sname, sent in sorted(all_sensors.items()):
            stype = sent.get("subtype") or sent.get("type") or "Unknown"
            val = sensor_values.get(sname)
            # --- Cache previous values to prevent flicker (esp. camera) ---
            if val in (None, {}, []):
                # reuse last non-empty value if available
                val = self._last_sensor_values.get(sname, val)
            else:
                # store this new value
                self._last_sensor_values[sname] = val
            det_str = ""
            # Format value and detection cleanly
            if isinstance(val, dict):
                if "distance" in val and "detected_name" in val:
                    target = val.get("detected_name", "None")
                    dist = val.get("distance", 0)
                    det_str = f"{target} ({dist:.1f})"
                    val_str = f"{dist:.1f}"
                elif stype.lower() == "camera":
                    # --- Camera-specific: show summary ---
                    detected = [k for k, v in val.items() if isinstance(v, dict)]
                    if detected:
                        val_str = f"{len(detected)} target(s)"
                        det_str = ", ".join(detected[:2])
                        if len(detected) > 2:
                            det_str += ", …"
                    else:
                        val_str = "-"
                        det_str = ""
                elif stype.lower() in ("areaalarm", "linearalarm", "alarm"):
                    # --- Alarms: show triggered state and detections ---
                    trig = val.get("triggered")
                    dets = val.get("detections", {})

                    # --- Triggered state ---
                    if isinstance(trig, (bool, int, float)):
                        val_str = "Triggered" if float(trig) > 0 else "Idle"
                    else:
                        val_str = "-"

                    # --- Detection formatting (camera-style) ---
                    detected = []
                    if isinstance(dets, dict):
                        detected = list(dets.keys())
                    elif isinstance(dets, (list, tuple, set)):
                        detected = [str(d) for d in dets if d]
                    # Support nested structures like {"r_1": {"x":...}}
                    elif dets:
                        try:
                            detected = [str(dets)]
                        except Exception:
                            detected = []

                    if detected:
                        det_str = ", ".join(detected[:2])
                        if len(detected) > 2:
                            det_str += ", …"
                    else:
                        det_str = ""
                else:
                    # Default dict formatting
                    if len(val) == 1:
                        k, v = next(iter(val.items()))
                        val_str = f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
                    else:
                        val_str = ", ".join(
                            f"{k}:{v:.1f}" if isinstance(v, (int, float)) else f"{k}:{v}"
                            for k, v in val.items()
                        )
            elif isinstance(val, (int, float)):
                val_str = f"{val:.2f}"
            else:
                val_str = str(val) if val else "-"

            color = (180, 255, 180) if isinstance(val, (int, float, dict)) else (200, 200, 200)
            self.screen.blit(self.font.render(sname, True, (230, 230, 230)), (col_x[0], y + 2))
            self.screen.blit(self.font.render(stype.title(), True, (200, 200, 200)), (col_x[1], y))
            self.screen.blit(self.font.render(val_str, True, color), (col_x[2], y))
            if det_str:
                self.screen.blit(self.font.render(det_str, True, (180, 220, 255)), (col_x[3], y))
            y += row_h

            if y > self.height - 40:
                break
    # -----------------------------------------------------
    # ---------------- ENTITY DRAWING ---------------------
    # -----------------------------------------------------

    def draw_entity(self, x, y, theta, entity, label):
        """Draw geometric shape for an entity based on its declared properties."""
        pos = self.world_to_screen(x, y)
        eclass = entity.get("class", "").lower()
        color = self.colors.get(eclass, (200, 200, 200))

        # --- Try to find shape in multiple possible sources ---
        shape = None
        # Directly on the entity (node-level)
        if isinstance(entity.get("shape"), dict):
            shape = entity["shape"]
        # Inside properties
        elif isinstance(entity.get("properties", {}).get("shape"), dict):
            shape = entity["properties"]["shape"]
        # In the matching pose (pose may hold shape)
        elif hasattr(self.node, "poses"):
            found_pose = None
            # Find pose by label (slow but safe)
            def find_pose(d):
                for k, v in d.items():
                    if k == label and isinstance(v, dict) and "shape" in v:
                        return v
                    elif isinstance(v, dict):
                        res = find_pose(v)
                        if res:
                            return res
                return None
            found_pose = find_pose(self.node.poses)
            if found_pose and isinstance(found_pose.get("shape"), dict):
                shape = found_pose["shape"]

        # --- Fallback ---
        if not isinstance(shape, dict):
            shape = {}

        shape_type = shape.get("type", "").lower()

        # === Draw by shape type ===
        if shape_type == "rectangle":
            # Rectangle(width, length)
            w = shape.get("width", 1.0)
            l = shape.get("length", 1.0)
            hw, hl = (w / 2) * self.scale * self.zoom, (l / 2) * self.scale * self.zoom
            pts = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
            rot = math.radians(theta)
            rotated = [
                (
                    pos[0] + px * math.cos(rot) - py * math.sin(rot),
                    pos[1] - (px * math.sin(rot) + py * math.cos(rot))
                )
                for px, py in pts
            ]
            pygame.draw.polygon(self.screen, color, rotated, 2)

        elif shape_type == "square":
            # Square(length)
            length = shape.get("length", 1.0)
            hw = hl = (length / 2) * self.scale * self.zoom
            pts = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
            rot = math.radians(theta)
            rotated = [
                (
                    pos[0] + px * math.cos(rot) - py * math.sin(rot),
                    pos[1] - (px * math.sin(rot) + py * math.cos(rot))
                )
                for px, py in pts
            ]
            pygame.draw.polygon(self.screen, color, rotated, 2)
        
        elif shape_type == "circle":
            r = shape.get("radius", shape.get("size", 0.5)) * self.scale * self.zoom
            pygame.draw.circle(self.screen, color, pos, int(r), 2)

        elif shape_type == "arbitraryshape":
            pts = shape.get("points", [])
            if len(pts) >= 2:
                # Alarm pose is the local origin (anchor)
                ent_x, ent_y, ent_theta = x, y, theta
                rot = math.radians(ent_theta)

                # Convert local shape points → world → screen coords
                screen_pts = []
                for p in pts:
                    # Local point relative to entity pose
                    wx = ent_x + (p["x"] * math.cos(rot) - p["y"] * math.sin(rot))
                    wy = ent_y + (p["x"] * math.sin(rot) + p["y"] * math.cos(rot))
                    sx, sy = self.world_to_screen(wx, wy)
                    screen_pts.append((sx, sy))

                # --- Base color: sensor color ---
                base_color = self.colors.get("sensor", (0, 200, 255))
                color = base_color
                width = 2

                # --- Change color only if triggered ---
                val = self.node.sensor_values.get(label)
                if isinstance(val, dict) and val.get("triggered", 0) > 0:
                    color = (255, 60, 60)
                    width = 4

                # Draw line segment (laser beam)
                pygame.draw.lines(self.screen, color, False, screen_pts, width)

        else:
            pygame.draw.circle(self.screen, color, pos, 4)

        # --- Label box with automatic offset ---
        label_surf = self.font.render(label, True, (0, 0, 0))
        lw, lh = label_surf.get_size()

        # Try 4 offset directions and pick one that doesn't overlap nearby entities
        candidate_offsets = [
            (10, -10),   # top-right
            (-lw - 10, -10),  # top-left
            (10, lh + 10),    # bottom-right
            (-lw - 10, lh + 10)  # bottom-left
        ]

        # Track drawn label rectangles to avoid overlaps
        if not hasattr(self, "_label_rects"):
            self._label_rects = []

        # Pick first offset that doesn’t collide with existing labels
        for ox, oy in candidate_offsets:
            test_rect = pygame.Rect(pos[0] + ox, pos[1] + oy, lw, lh)
            if not any(test_rect.colliderect(r) for r in self._label_rects):
                chosen_rect = test_rect
                break
        else:
            # fallback: top-right if all collide
            chosen_rect = pygame.Rect(pos[0] + 10, pos[1] - 10, lw, lh)

        # Store rect for next labels
        self._label_rects.append(chosen_rect)

        # Draw background + text
        pygame.draw.rect(self.screen, color, chosen_rect.inflate(6, 4), border_radius=3)
        self.screen.blit(label_surf, (chosen_rect.x + 3, chosen_rect.y + 2))

        # --- Orientation arrow ---
        self.draw_arrow(pos, theta, color)

    # -----------------------------------------------------
    # ---------------- INPUT HANDLING ---------------------
    # -----------------------------------------------------

    def handle_input(self):
        """Keyboard & mouse input for zoom and pan."""
        keys = pygame.key.get_pressed()

        # Zoom with keyboard
        if keys[pygame.K_EQUALS] or keys[pygame.K_PLUS]:
            self.zoom *= self.zoom_step
        elif keys[pygame.K_MINUS] or keys[pygame.K_UNDERSCORE]:
            self.zoom /= self.zoom_step
        elif keys[pygame.K_r]:
            self.zoom = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0

        # Pan with arrow keys
        if keys[pygame.K_LEFT]:
            self.pan_x -= self.pan_speed / self.zoom
        if keys[pygame.K_RIGHT]:
            self.pan_x += self.pan_speed / self.zoom
        if keys[pygame.K_UP]:
            self.pan_y += self.pan_speed / self.zoom
        if keys[pygame.K_DOWN]:
            self.pan_y -= self.pan_speed / self.zoom

        # Mouse events
        mouse_buttons = pygame.mouse.get_pressed(num_buttons=3)
        mx, my = pygame.mouse.get_pos()

        # Right-click drag to pan
        if mouse_buttons[2]:
            if not self.dragging:
                self.dragging = True
                self.drag_start = (mx, my)
            else:
                dx = (mx - self.drag_start[0]) / (self.scale * self.zoom)
                dy = (my - self.drag_start[1]) / (self.scale * self.zoom)
                self.pan_x -= dx
                self.pan_y += dy
                self.drag_start = (mx, my)
        else:
            self.dragging = False

        # Mouse wheel for zoom
        for event in pygame.event.get(pygame.MOUSEWHEEL):
            if event.y > 0:
                self.zoom *= self.zoom_step
            elif event.y < 0:
                self.zoom /= self.zoom_step
    
    def _draw_all_entities(self):
        """Traverse all node entities recursively and draw them if a matching pose is found."""
        def find_pose_by_name(d, name, depth=0):
            if not isinstance(d, dict):
                return None
            # --- Case 1: key directly matches ---
            if name in d and isinstance(d[name], dict):
                pose = d[name]
                if all(k in pose for k in ("x", "y", "theta")):
                    return pose
                if "rel_pose" in pose and all(k in pose["rel_pose"] for k in ("x", "y", "theta")):
                    return pose["rel_pose"]
            # --- Case 2: this dict itself has a matching name ---
            if "name" in d and d["name"].lower() == name.lower():
                if all(k in d for k in ("x", "y", "theta")):
                    return d
                if "rel_pose" in d and all(k in d["rel_pose"] for k in ("x", "y", "theta")):
                    return d["rel_pose"]
            # --- Case 3: recurse deeper ---
            for v in d.values():
                if isinstance(v, dict):
                    res = find_pose_by_name(v, name, depth + 1)
                    if res:
                        return res
            return None

        def recurse(branch):
            """Depth-first traversal of all node branches (no class filtering)."""
            if not isinstance(branch, dict):
                return
            for key, node in branch.items():
                if not isinstance(node, dict):
                    continue
                if "class" in node:
                    pose = find_pose_by_name(self.node.poses, key)
                    if pose:
                        # Debug print so you can verify it draws the deep ones
                        # print(f"[DRAW] {key} ({node.get('class')}) -> {pose}")
                        self.draw_entity(pose["x"], pose["y"], pose["theta"], node, key)
                # Always recurse deeper
                recurse(node)

        # start from the full nodes dict (not just top categories)
        recurse(self.node.nodes)
    
    # -----------------------------------------------------
    # ---------------- MAIN LOOP --------------------------
    # -----------------------------------------------------

    def render(self):
        """Main pygame render loop (draws all entities)."""
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.stop()
                        return

                self.handle_input()
                self.draw_background()
                self._label_rects = []   # reset label collision memory

                # --- Draw all entities ---
                self._draw_all_entities()

                # --- Draw sensor data table ---
                self.draw_sensor_table()

                pygame.display.flip()
                self.clock.tick(30)

        except KeyboardInterrupt:
            print("[Visualizer] Interrupted by user.")
            self.stop()
    # -----------------------------------------------------
    # ----------------- LIFECYCLE -------------------------
    # -----------------------------------------------------

    def stop(self):
        self.running = False
        pygame.quit()
