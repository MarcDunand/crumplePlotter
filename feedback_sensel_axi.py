import sys
import math
from collections import deque
sys.path.append('./sensel-api/sensel-lib-wrappers/sensel-lib-python')
import sensel
import threading
import cv2
import numpy as np
from pyaxidraw import axidraw

#axidraw setup
axi = axidraw.AxiDraw()
axi.plot_setup()
axi.interactive()
if not axi.connect():
    print("Not connected")
    quit()
print("Connected to AxiDraw!")
axi.options.units = 2
axi.options.pen_pos_up = 98
axi.options.pen_pos_down = 2
axi.update()

axi.penup()
axi.moveto(75, 60)
axi.pendown()

enter_pressed = False

prevPos = deque(maxlen=100)

def waitForEnter():
    global enter_pressed
    input("Press Enter to exit...")
    enter_pressed = True
    return

def openSensel():
    handle = None
    (error, device_list) = sensel.getDeviceList()
    if device_list.num_devices != 0:
        (error, handle) = sensel.openDeviceByID(device_list.devices[0].idx)
    else:
        print("No Sensel devices found.")
    return handle

def initFrame():
    error = sensel.setFrameContent(handle, sensel.FRAME_CONTENT_PRESSURE_MASK)
    (error, frame) = sensel.allocateFrameData(handle)
    error = sensel.startScanning(handle)
    return frame

def scanFrames(frame, info, step, prevX, prevY):
    return runAxi(frame, info, step, prevX, prevY)


def findMaxForce(frame, info):
    num_rows = info.num_rows
    num_cols = info.num_cols

    error = sensel.readSensor(handle)
    (error, num_frames) = sensel.getNumAvailableFrames(handle)
    for j in range(num_frames):
        error = sensel.getFrame(handle, frame)
        displayHeatmap(frame, info) #draws heatmap and gets maximum exerted force on any sensel

    force_array = frame.force_array
    maxForce = -1
    maxForceIdx = -1
    for j in range(num_rows*num_cols):
        if(force_array[j] > maxForce):
            maxForce = force_array[j]
            maxForceIdx = j

    y = maxForceIdx//num_cols
    x = num_cols - (maxForceIdx-y*num_cols)
    y = num_rows - y

    return (x, y, maxForce)


def runAxi(frame, info, step, prevX, prevY):
    global prevPos

    (fX, fY, maxForce) = findMaxForce(frame, info)
    if(maxForce > 0):
        (axiX, axiY) = axi.current_pos()

        x = fX*1.24
        y = fY*1.22

        newX = min(230, max(0, x))
        newY = min(125, max(0, y))

        dist = math.dist((newX, newY), (axiX, axiY))

        if dist > 20:
            r = 20/dist
            newX = newX*r + axiX*(1-r)
            newY = newY*r + axiY*(1-r)
    
        print(newX, newY)

        prevPos.append((newX, newY))
        axi.lineto(newX, newY)
        return (x, y)

    elif len(prevPos) > 0:
        recent = prevPos.pop()
        axi.lineto(recent[0], recent[1])
        print("searching...")
        return (0, 0)

    else:
        print("HELP")
        return (0, 0)

def displayHeatmap(frame, info):
    num_rows = info.num_rows
    num_cols = info.num_cols
    force_array = frame.force_array

    # Initialize an empty NumPy array to hold the force values
    force_matrix = np.zeros((num_rows, num_cols), dtype=np.float32)

    # Manually fill the NumPy array with values from force_array
    maxForce = 0
    for row in range(num_rows):
        for col in range(num_cols):
            index = row * num_cols + col
            force_matrix[row, col] = force_array[index]

            maxForce = max(maxForce, force_array[index])

    # Normalize force_matrix to range 0-255
    forceLimit = 700
    if forceLimit > 0:
        normalized_force = (force_matrix / forceLimit) * 255
    else:
        normalized_force = force_matrix

    # Gamma Correct
    gamma = 2
    normalized_force = np.power(normalized_force / 255.0, 1 / gamma) * 255.0

    # Convert to uint8
    image = normalized_force.astype(np.uint8)

    # Resize the heatmap for better visibility (optional)
    heatmap_resized = cv2.resize(image, (num_cols * 5, num_rows * 5), interpolation=cv2.INTER_NEAREST)
    # Display the heatmap
    cv2.imshow('Force Heatmap', heatmap_resized)
    cv2.waitKey(1)  # Required for the image to update

    return maxForce

def closeSensel(frame):
    error = sensel.freeFrameData(handle, frame)
    error = sensel.stopScanning(handle)
    error = sensel.close(handle)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    handle = openSensel()
    if handle is not None:
        (error, info) = sensel.getSensorInfo(handle)
        frame = initFrame()

        t = threading.Thread(target=waitForEnter)
        t.start()
        step = 0
        axi.delay(500)
        (prevX, prevY) = (0, 0)
        while not enter_pressed:
            (prevX, prevY) = scanFrames(frame, info, step, prevX, prevY)
            step += 0.5
        closeSensel(frame)
    else:
        print("Failed to open Sensel device.")


#axidraw cooldown
axi.moveto(0, 0)
axi.disconnect()
axi.options.mode = "align"
axi.plot_run()