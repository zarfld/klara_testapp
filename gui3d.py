from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random

"""
Enhanced 3D prototype using Ursina.

New features:
- Grid visual on ground
- Health bar + UI inventory
- Player first-person hand model
- Enemies cannot walk through blocks (basic obstacle handling)
- Custom block types (dirt, wood, glass, stair, furniture)
- Larger world and better statistics
- Support for build-mode block type selection
- Two-player optional local guest mode

Run after `pip install ursina` in the project venv.
"""

app = Ursina()

# Map / world
GRID_SIZE = 15
world_scale = GRID_SIZE * 2 + 2
ground = Entity(model='plane', scale=(world_scale, 1, world_scale), texture='white_cube', texture_scale=(GRID_SIZE, GRID_SIZE), collider='box', color=color.light_gray)

# Grid lines
grid_parent = Entity()
for x in range(-GRID_SIZE, GRID_SIZE + 1):
    Entity(parent=grid_parent, model='cube', scale=(0.03, 0.02, world_scale), position=(x, 0.02, 0), color=color.gray)
for z in range(-GRID_SIZE, GRID_SIZE + 1):
    Entity(parent=grid_parent, model='cube', scale=(world_scale, 0.02, 0.03), position=(0, 0.02, z), color=color.gray)

# Player
player = FirstPersonController()
player.cursor = Entity(parent=camera.ui, model='quad', scale=0.008, color=color.white)
player.health = 100
player.max_health = 100

# add a first-person hand model
hand = Entity(parent=camera, model='cube', color=color.rgb(255, 220, 180), position=(0.2, -0.35, 1), scale=(0.2, 0.2, 0.5))

# Inventory and game state
player_inventory = {'dirt': 10, 'wood': 5, 'glass': 2, 'stair': 2, 'furn': 1}
build_types = ['dirt', 'wood', 'glass', 'stair', 'furn']
selected_build = 0
player_score = 0

blocks_parent = Entity()
enemies_parent = Entity()
projectiles_parent = Entity()

# HUD
health_text = Text(text='', position=Vec2(-0.95, 0.48), scale=1.2, origin=(0, 0))
inventory_text = Text(text='', position=Vec2(-0.95, 0.43), scale=1.0, origin=(0, 0))
controls_text = Text(text='WASD/mouse: Move | LMB: shoot | B: build | 1-5: block type | M: toggle guest player | ESC: quit', position=Vec2(-0.7, 0.38), scale=0.8, origin=(0, 0))
message_text = Text(text='', position=Vec2(0, 0.45), scale=1.0, origin=(0.5, 0))

guest_player = None

def update_hud():
    health_text.text = f'HP: {player.health}/{player.max_health}'
    inv_str = ' '.join([f'[{i+1}] {t}:{player_inventory.get(t,0)}' for i, t in enumerate(build_types)])
    inventory_text.text = f'Select: {build_types[selected_build]} | {inv_str} | Score: {player_score}'

update_hud()

# block templates
BLOCK_TEMPLATES = {
    'dirt': {'color': color.brown, 'scale': (1, 1, 1), 'opacity': 1},
    'wood': {'color': color.rgb(160, 100, 50), 'scale': (1, 1, 1), 'opacity': 1},
    'glass': {'color': color.rgba(120, 220, 255, 120), 'scale': (1, 1, 1), 'opacity': 0.4},
    'stair': {'color': color.rgb(170, 170, 170), 'scale': (1, 0.4, 1), 'offset': (0, -0.3, 0)},
    'furn': {'color': color.azure, 'scale': (1, 0.5, 1), 'offset': (0, 0.25, 0)}
}


def create_block_at(pos, block_type):
    tpl = BLOCK_TEMPLATES.get(block_type, BLOCK_TEMPLATES['dirt'])
    final_pos = Vec3(pos[0], 0.5, pos[2])
    if 'offset' in tpl:
        final_pos += Vec3(*tpl['offset'])
    block = Entity(parent=blocks_parent, model='cube', position=final_pos, scale=tpl.get('scale', (1, 1, 1)), color=tpl['color'], collider='box')
    if tpl.get('opacity', 1) < 1:
        block.color = tpl['color']
        block.opacity = tpl['opacity']
    return block


def place_block():
    global selected_build
    build_type = build_types[selected_build]
    if player_inventory.get(build_type, 0) <= 0:
        message_text.text = f'Nicht genug {build_type}.'
        return

    target = player.position + player.forward * 2
    x, z = round(target.x), round(target.z)
    y = 0.5

    if abs(x) > GRID_SIZE or abs(z) > GRID_SIZE:
        message_text.text = 'Außerhalb der Weltgrenze.'
        return

    for b in blocks_parent.children:
        if round(b.x) == x and round(b.z) == z and abs(round(b.y) - y) < 0.75:
            message_text.text = 'Block existiert bereits.'
            return

    create_block_at((x, y, z), build_type)
    player_inventory[build_type] -= 1
    message_text.text = f'{build_type} platziert.'
    update_hud()


def world_raycast(start, end):
    hit = raycast(start, end - start, distance=(end - start).length(), ignore=[player, hand])
    return hit


def spawn_enemy():
    # spawn at random edge
    pos_options = [(-GRID_SIZE, 0.5, random.randint(-GRID_SIZE, GRID_SIZE)),
                   (GRID_SIZE, 0.5, random.randint(-GRID_SIZE, GRID_SIZE)),
                   (random.randint(-GRID_SIZE, GRID_SIZE), 0.5, -GRID_SIZE),
                   (random.randint(-GRID_SIZE, GRID_SIZE), 0.5, GRID_SIZE)]
    pos = random.choice(pos_options)
    e = Entity(parent=enemies_parent, model='cube', color=color.green, scale=(0.9, 0.9, 0.9), position=pos, collider='box')
    e.health = 3
    return e


def fire_projectile():
    proj = Entity(parent=projectiles_parent, model='sphere', color=color.red, scale=0.15, position=player.position + player.forward * 1.5)
    proj.direction = player.forward
    proj.speed = 20
    proj.lifetime = 1.0


def handle_projectiles(dt):
    global player_score
    for proj in list(projectiles_parent.children):
        proj.position += proj.direction * proj.speed * dt
        proj.lifetime -= dt

        for e in list(enemies_parent.children):
            if distance(proj.position, e.position) < 1.0:
                e.health -= 1
                destroy(proj)
                if e.health <= 0:
                    player_score += 10
                    player_inventory['wood'] += 1
                    destroy(e)
                    message_text.text = 'Zombi besiegt! +1 wood'
                    update_hud()
                break

        if proj.lifetime <= 0:
            destroy(proj)


def handle_enemies(dt):
    for e in list(enemies_parent.children):
        direction = Vec3(player.x - e.x, 0, player.z - e.z)
        if direction.length() < 1.5:
            player.health -= 8 * dt
            message_text.text = 'Zombi greift an!'
            update_hud()
            continue

        # simple obstacle avoidance: raycast toward player
        hit = raycast(e.position, direction.normalized(), distance=direction.length(), ignore=[e, enemies_parent])
        if hit.entity is not None and hit.entity in blocks_parent.children:
            # block in direct path, move around
            perp = Vec3(-direction.z, 0, direction.x).normalized()
            e.position += (perp * dt * 1.0)
        else:
            e.position += direction.normalized() * dt * 1.8


enemy_spawn_timer = 0.0


def update():
    global enemy_spawn_timer
    if player.health <= 0:
        message_text.text = 'Game over! Spieler tot.'
        return

    player.health = max(0, min(player.max_health, player.health))
    handle_projectiles(time.dt)
    handle_enemies(time.dt)

    enemy_spawn_timer -= time.dt
    if enemy_spawn_timer <= 0:
        spawn_enemy()
        enemy_spawn_timer = max(1.5, 2.2 + random.uniform(-0.8, 0.8))

    # keep hand in front of camera
    hand.position = (0.22 + random.uniform(-0.008, 0.008), -0.36 + sin(time.time() * 5) * 0.004, 1)


def update_message(txt):
    message_text.text = txt


def input(key):
    global selected_build, guest_player
    if key == 'left mouse down':
        fire_projectile()
    if key == 'b':
        place_block()
    if key in ['1', '2', '3', '4', '5']:
        selected_build = int(key) - 1
        message_text.text = f'Baumodus: {build_types[selected_build]}'
        update_hud()
    if key == 'm':
        if guest_player is None:
            guest_player = Entity(model='cube', color=color.azure, position=(player.x+1, 0.5, player.z+1), scale=0.8)
            message_text.text = 'Gastspieler aktiviert'
        else:
            destroy(guest_player)
            guest_player = None
            message_text.text = 'Gastspieler deaktiviert'


if __name__ == '__main__':
    for _ in range(3):
        spawn_enemy()
    update_hud()
    app.run()
