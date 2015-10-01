import pygame
import Box2D
import math


class Simulation:
    def __init__(self):
        self.world = Box2D.b2World(gravity=(0, 15), doSleep=True)
        self.background = None
        self.background_rect = None
        self.sprites = []
        self.spawns = []
        self.render_vertices = False

    def set_background(self, img):
        self.background = pygame.image.load(img)
        self.background_rect = self.background.get_rect()

    def add_sprite(self, image, vertices):
        self.sprites.append(Spawner(vertices[:], image, self.world))

    def clone(self, image, vertices, dynamic=True):
        self.sprites.append(SimObject(vertices, image, dynamic))
        return self.sprites[-1]

    def update(self):
        self.world.Step(1 / 60.0, 10, 10)
        for sprite in self.sprites:
            sprite.update(self.background_rect)
        self.world.ClearForces()

    def click_action(self, pos):
        for sprite in self.sprites:
            if sprite.pos.collidepoint(pos):
                sprite.click()

    def draw(self, surface):
        surface.blit(self.background, self.background_rect)
        for sprite in self.sprites:
            sprite.draw(surface)
        if self.render_vertices:
            for body in self.world.bodies:
                for fixture in body.fixtures:
                    vertices = [(body.transform * v) for v in fixture.shape.vertices]
                    pygame.draw.polygon(surface, (0, 0, 0), vertices, 2)


class Spawner:
    def __init__(self, vertices, image, world):
        self.world = world
        self.vertices = vertices[:]
        self.image = image
        self.objects = []
        self.occupied = False
        self.spawn(False)
        self.pos = self.objects[0].spawn

    def spawn(self, dynamic):
        # we need to know if the spawn is occupied so we won't spawn more than one object in the area
        if not dynamic and not self.occupied:
            self.objects.append(SimObject(self.vertices, self.image, self.world, dynamic))
            self.occupied = True
        elif self.occupied:
            self.objects[-1].go_dynamic(self.world)
            self.occupied = False
        else:
            self.objects.append(SimObject(self.vertices, self.image, self.world, dynamic))

    def click(self):
        self.spawn(True)

    def update(self, bounds):
        to_remove = []
        for obj in self.objects:
            obj.update()
            if not obj.sprite['rect'].colliderect(bounds):
                obj.destroy(self.world)
                if not self.occupied:
                    self.spawn(False)
                to_remove.append(obj)
        for r in to_remove:
            self.objects.remove(r)

    def draw(self, surface):
        for obj in self.objects:
            if obj.body.type == Box2D.b2_dynamicBody:
                obj.draw(surface)


class SimObject:
    def __init__(self, vertices, image, world, dynamic=False):
        self.vertices = vertices[:]
        self.image = image

        self.sprite = get_sprite(image)

        if dynamic:
            self.body, self.fixture = create_dynamic_polygon(vertices[:], world)
        else:
            self.body, self.fixture = create_polygon(vertices[:], world)

        # find the top-left corner of the bounding box of the polygon
        minx = min(vertices, key=lambda x: x[0])[0]
        miny = min(vertices, key=lambda x: x[1])[1]
        self.sprite['rect'] = self.spawn = self.sprite['image'].get_rect()
        self.sprite['rect'][0] = self.spawn[0] = minx
        self.sprite['rect'][1] = self.spawn[1] = miny

    def click(self, pos, world):
        if self.body.type is not Box2D.b2_dynamicBody and self.sprite['rect'].collidepoint(pos):
            world.DestroyBody(self.body)
            if isinstance(self.fixture, list):
                vertices = self.vertices[:]
            else:
                vertices = self.fixture.shape.vertices

            self.body, self.fixture = create_dynamic_polygon(vertices, world)
            return True
        return False

    def go_dynamic(self, world):
        world.DestroyBody(self.body)
        if isinstance(self.fixture, list):
            vertices = self.vertices[:]
        else:
            vertices = self.fixture.shape.vertices

        self.body, self.fixture = create_dynamic_polygon(vertices, world)

    def update(self):
        if self.body.type is not Box2D.b2_dynamicBody:
            return

        # rotate according to the physics but keep the sprite box as tight as possible
        img = self.image.rotate(-math.degrees(self.body.transform.angle), expand=True)
        img = img.crop(img.getbbox())

        self.sprite['image'] = pygame.image.fromstring(img.tostring(), img.size, img.mode)
        self.sprite['rect'] = self.sprite['image'].get_rect()

        # find the new top-left corner
        vertices = []
        if isinstance(self.fixture, list):
            for fixture in self.fixture:
                for vertex in fixture.shape.vertices:
                    vertices.append((self.body.transform * vertex))
        else:
            vertices = [(self.body.transform * v) for v in self.fixture.shape.vertices]

        self.sprite['rect'][0] = min(vertices, key=lambda x: x[0])[0]
        self.sprite['rect'][1] = min(vertices, key=lambda x: x[1])[1]

    def draw(self, surface):
        surface.blit(self.sprite['image'], self.sprite['rect'])

    def in_bounds(self, bound):
        return bound.colliderect(self.sprite['rect'])

    def destroy(self, world):
        world.DestroyBody(self.body)


def get_sprite(img):
    sprite = {'image': pygame.image.fromstring(img.tostring(), img.size, img.mode)}
    sprite['rect'] = sprite['image'].get_rect()
    return sprite


def create_dynamic_polygon(vertices, world):
    body = world.CreateDynamicBody()

    # box2d cannot create polygons with 16 or more vertices so triangulate them
    if len(vertices) >= 16:
        fixtures = triangulate(vertices[:], body)
        return body, fixtures

    box = Box2D.b2PolygonShape(vertices=vertices)

    # this means we have a concave shape
    if len(box.vertices) < len(vertices) - 1:
        fixtures = triangulate(vertices[:], body)
        return body, fixtures

    box = body.CreatePolygonFixture(vertices=vertices, density=1, friction=.1, restitution=.5)
    return body, box


def create_polygon(vertices, world):
    body = world.CreateBody(Box2D.b2BodyDef())

    # box = Box2D.b2PolygonShape(vertices=vertices)
    box = Box2D.b2ChainShape(vertices_loop=vertices[:])

    fixture = Box2D.b2FixtureDef()
    fixture.shape = box
    fixture.density = 2
    fixture.friction = .3
    fixture.restitution = .5
    body.CreateFixture(fixture)
    return body, fixture


# gets the vertices and breaks it up into triangles
def triangulate(vertices, body):
    can_triangulate = True
    fixtures = []
    while can_triangulate:
        if len(vertices) <= 3:
            break
        can_triangulate = False
        for i in xrange(len(vertices)):
            v1 = vertices[i - 1]
            v2 = vertices[i]
            v3 = vertices[(i + 1) % len(vertices)]
            if not is_convex(v1, v2, v3):
                clip = False
                for vertex in vertices:
                    if vertex not in (v1, v2, v3) and not does_triangle_contain(v1, v2, v3, vertex):
                        clip = True
                        break
                if clip:
                    vertices.pop(i)
                    can_triangulate = True
                    fixtures.append(
                        body.CreatePolygonFixture(vertices=[v1, v2, v3], density=2, friction=.3, restitution=.3))
                    break

    # left with one last shape, add it in!
    if len(vertices) != 0:
        fixtures.append(
            body.CreatePolygonFixture(vertices=vertices, density=2, friction=.3, restitution=.3))
    return fixtures


def does_triangle_contain(v1, v2, v3, vertex):
    points = [0.0] * 3
    epsilon = 0.0000001
    points.append(((v2[1] - v3[1]) * (vertex[0] - v3[0]) + (v3[0] - v2[0]) * (vertex[1] - v3[1]))
                  / (((v2[1] - v3[1]) * (v1[0] - v3[0]) + (v3[0] - v2[0]) * (v1[1] - v3[1])) + epsilon))

    points.append(((v3[1] - v1[1]) * (vertex[0] - v3[0]) + (v1[0] - v3[0]) * (vertex[1] - v3[1]))
                  / (((v2[1] - v3[1]) * (v1[0] - v3[0]) + (v3[0] - v2[0]) * (v1[1] - v3[1])) + epsilon))

    points.append(1 - points[0] - points[1])

    for point in points:
        if point >= 1 or points <= 0:
            return False
    return True


def is_convex(v1, v2, v3):
    return (v2[0] - v1[0]) * (v3[1] - v1[1]) - (v2[1] - v1[1]) * (v3[0] - v1[0]) >= 0
