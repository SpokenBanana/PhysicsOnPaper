import cv2
import numpy
import sys
from PIL import Image, ImageDraw
from Simulation import *

width, height = 700, 700
pygame.init()
clock = pygame.time.Clock()
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption('Simulation')
simulation = Simulation()


def create_text(text, size=25, location=None):
    font = pygame.font.SysFont('pericles', size).render(text, False, (255, 255, 255), (10, 40, 75))
    if location is None:
        return font, font.get_rect()
    rect = font.get_rect()
    rect.centerx = location[0]
    rect.centery = location[1]
    return font, rect


def run_pygame():
    text, text_box = create_text("display vertices", location=(150, 500))
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                pos = pygame.mouse.get_pos()
                simulation.click_action(pos)
                if text_box.collidepoint(pos):
                    simulation.render_vertices = not simulation.render_vertices

        screen.fill([0x00, 0x00, 0x00])

        simulation.update()

        simulation.draw(screen)

        screen.blit(text, text_box)
        pygame.display.flip()
        clock.tick(120)


# crops out the sprite from the background image for the given contour
def get_sprite_from_vertices(vertices, background, cnt):
    im_array = numpy.asarray(background)
    mask = Image.new('L', (im_array.shape[1], im_array.shape[0]), 0)
    ImageDraw.Draw(mask).polygon(vertices, outline=1, fill=1)
    mask = numpy.array(mask)

    new_imarray = numpy.empty(im_array.shape, dtype='uint8')

    new_imarray[:, :, :3] = im_array[:, :, :3]

    new_imarray[:, :, 3] = mask * 255

    newimage = Image.fromarray(new_imarray, 'RGBA')
    rect = cv2.boundingRect(cnt)
    newimage = newimage.crop((int(rect[0]), int(rect[1]), int(rect[0] + rect[2]), int(rect[1] + rect[3])))
    return newimage


# gets the contour of all shapes in the image
def get_contours(img=cv2.imread('image.png', 1)):
    # de-noise,greyscale, blur, threshold the image, and finally get the contours of the shapes
    img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.medianBlur(img_gray, 5)
    ret, thresh = cv2.threshold(img_gray, 99, 255, cv2.THRESH_BINARY_INV)
    image, contour, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # filter out any child contours
    result = []
    for i in xrange(len(contour)):
        if hierarchy[0][i][3] == -1:
            result.append(contour[i])
    return result


def convert_to_simobjects(cnt):
    background = Image.open('image.png').convert('RGBA')
    epsilon = 0.01 * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    vertices = [(c[0][0], c[0][1]) for c in approx]

    # add height to the lines
    if len(vertices) < 3:
        vertices.append((vertices[0][0] + 5, vertices[0][1] + 5))
        vertices.append((vertices[1][0] + 5, vertices[1][1] + 5))

    image = get_sprite_from_vertices(vertices, background, cnt)
    simulation.add_sprite(image, vertices)


# drawing the instructions to screen
def intro():
    instructions, i_box = create_text("hold up your drawing to the web-cam!", 15, (width/2, 50))
    finish, f_box = create_text("when you think the camera has a clear view, pressed esc!", 15, (width/2, 150))
    screen.blit(instructions, i_box)
    screen.blit(finish, f_box)
    pygame.display.flip()


def start_camera():
    intro()
    cap = cv2.VideoCapture(0)
    img = None
    while cap.isOpened():
        ret, img = cap.read()
        cv2.imshow('output', img)

        k = cv2.waitKey(10)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                cap.release()
                cv2.destroyAllWindows()
                sys.exit()
        if k == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    cv2.imwrite("image.png", img)
    simulation.set_background('image.png')
    contours = get_contours(img)
    for cnt in contours:
        convert_to_simobjects(cnt)
    run_pygame()

if __name__ == '__main__':
    # simulation.set_background('test.png')
    # get_contours(cv2.imread('test.png'))
    # for cnt in get_contours(cv2.imread('test.png')):
    #     convert_to_simobjects(cnt)
    # run_pygame()
    start_camera()
