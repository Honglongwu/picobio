import numpy as np
from matplotlib import pyplot as plt

filename = "test.cov"
png_filename = "test.png"

def load(filename):
    h = open(filename)
    line = h.readline()
    assert line.startswith(">")
    while line and line[0] == ">":
        name = line[1:].split(None,1)[0]
        values = []
        while line:
            line = h.readline()
            if not line or line[0] == ">":
                break
            values.append([float(v) for v in line.rstrip("\n").split("\t")])
        yield name, np.array(values, np.float)
    h.close()

def make_colors(start, end, steps):
    delta = (end - start) / float(steps-1)
    return ["#%02x%02x%02x" % tuple(start + i*delta) for i in range(steps)]

def stack(data, filename, colors=None):
    fig = plt.figure()
    total = len(data)
    fig = plt.figure()
    if not colors:
        #Assumes all the examples have same number of colors:
        if data[0][1].shape[0] == 3:
            colors = ["#CC6666", "#1DACD6", "#6E5160"]
        elif data[0][1].shape[0] == 5:
            colors = ["#CDCDC1", "#8B8B83", "#FF6A6A", "#F0E68C", "#CDC673"]
        else:
            colors = make_colors(np.array([0xCC, 0x66, 0x66]),
                                 #np.array([0x6E, 0x51, 0x60]),
                                 np.array([0x90, 0x41, 0x50]),
                                 #np.array([0x20, 0xF0, 0x60]),
                                 data[0][1].shape[0])
        print colors
    for i, (name, values) in enumerate(data):
        x = range(values.shape[1])
        print i, name, values.shape, "coverage:"
        print "\t".join("%0.1f" % v for v in values.sum(axis=1))
        y_stack = np.cumsum(values, axis=0)
        ax1 = fig.add_subplot(total, 1, i+1)
        ax1.fill_between(x, 0, y_stack[0,:], facecolor=colors[0], alpha=.7)
        for i in range(0, values.shape[0]-1):
            ax1.fill_between(x, y_stack[i,:], y_stack[i+1,:], facecolor=colors[i+1], alpha=.7)
    plt.show()
    plt.savefig(filename)

data = list(load(filename))
stack(data, png_filename)
