#!/usr/bin/python
"""Yet another curses-based directory tree browser, in Python.
I thought I could use something like this for filename entry, kind of
like the old 4DOS 'select' command --- cd $(cursoutline.py).  So you
navigate and hit Enter, and it exits and spits out the file you're on.
Originally from: http://lists.canonical.org/pipermail/kragen-hacks/2005-December/000424.html
Originally by: Kragen Sitaker
"""

"""
Mar 2016 - Modified to be class-based, and added lots of other little features
so it works with my program for Astronomy data reductions.
Randy Doyle
"""

# There are several general approaches to the drawing-an-outline
# problem.  This program supports the following operations:
# - move cursor to previous item (in preorder traversal)
# - move cursor to next item (likewise)
# - hide descendants
# - reveal children
# And because it runs over the filesystem, it must be at least somewhat lazy
# about expanding children.
# And it doesn't really bother to worry about someone else changing the outline
# behind its back.
# So the strategy is to store our current linear position in the
# inorder traversal, and defer operations on the current node until the next
# time we're traversing.

try:
    import curses.wrapper as wrapper
    import curses.panel as panel
except ImportError:
    from curses import wrapper, panel
import curses, time, random, cgitb, os, sys, struct, time
cgitb.enable(format="text")
ESC = 27
SP = 32
result = ''
start = os.getcwd()

def pad(data, width):
    # XXX this won't work with UTF-8
    return data + " " * (width - len(data))

class File:
    def __init__(self, name):
        self.name = name
    def render(self, depth, width):
        return pad("{}{} {}".format(" " * 4 * depth, self.icon(), os.path.basename(self.name)), width)
    def icon(self): return "   "
    def traverse(self): yield self, 0
    def expand(self): pass
    def collapse(self): pass

class Dir(File):
    def __init__(self, name, displaytype = 1):
        File.__init__(self, name)
	self.displaytype = displaytype
        try: self.kidnames = sorted(os.listdir(name))
        except: self.kidnames = None  # probably permission denied
        self.kids = None
        self.expanded = False
    def children(self):
        if self.kidnames is None: return []
        if self.kids is None:
            self.kids = [self.factory(os.path.join(self.name, kid)) for kid in self.kidnames]
            self.kids = [kid for kid in self.kids if kid != None]
        return self.kids
    def icon(self):
        if self.expanded: return '[-]'
        elif self.kidnames is None: return '[?]'
        elif self.children(): return '[+]'
        else: return '[ ]'
    def expand(self): self.expanded = True
    def collapse(self): self.expanded = False
    def traverse(self):
        yield self, 0
        if not self.expanded: return
        for child in self.children():
            for kid, depth in child.traverse():
                yield kid, depth + 1
    def factory(self, name):
        if os.path.basename(name).startswith('.'):
            return None
        if os.path.isdir(name):
            if self.displaytype != 2:
                return Dir(name,self.displaytype)
            else:
                return None
        else:
            if self.displaytype != 1:
                return File(name)
            else:
                return None
 
def factory(name):
    global filechoice
    if os.path.isdir(name):
        if filechoice != 2:
            return Dir(name)
        else:
            return None
    else:
        if filechoice != 1:
            return File(name)
        else:
            return None

class FileMenu(object):
    def __init__(self, stdscreen, title, displaytype, rootdir):
        self.window = stdscreen.subwin(0,0)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()
        self.title = title
        self.displaytype = displaytype
        self.rootdir = rootdir
        self.result = ""
        self.ESC = 27
        self.position = 0

    def factory(self, name):
        if os.path.basename(name).startswith('.'):
            return None
        if os.path.isdir(name):
            if self.displaytype != 2:
                return Dir(name,self.displaytype)
            else:
                return None
        else:
            if self.displaytype != 1:
                return File(name)
            else:
                return None

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items)-1
    
    def set_title(self, title):
        self.title = title

    def display(self):
        self.result = ""
        self.panel.top()
        self.panel.show()
        self.window.clear()
        curdir = self.rootdir
        mydir = self.factory(self.rootdir)
        mydir.expand()
        curidx = 0
        pending_action = None
        pending_save = False
        updir = False
        typing = False
        curtime = 0
        selected = ""
        prevbase = []
        while True:
            self.window.clear()
            mode = curses.A_NORMAL
	    self.write(1, 1, "{}: Use arrow keys to navigate".format(self.title), mode)
            self.write(2, 4, "ENTER to select an item, and ESCAPE to cancel.", mode)
            self.write(3, 4, "OR type a path (selected path shown at bottom)", mode)
            y, x = self.window.getmaxyx()
            self.write(4, 0, "_"*x, curses.A_NORMAL)
            line = 0
            offset = 5
            for data, depth in mydir.traverse():
                if updir and data.name in prevbase:
                    data.expand()
                elif data.name in prevbase and not data.expanded:
                    del prevbase[prevbase.index(data.name)]
                if line == curidx and typing == False:
                    mode = curses.A_REVERSE
                    selected = data.name
                    if pending_action:
                        getattr(data, pending_action)()
                        pending_action = None
                    elif pending_save:
                        self.result = data.name
                        break
                else:
                    mode = curses.A_NORMAL
                if 0 <= line + offset < y - 3:
                    self.write(line + offset, 0, data.render(depth, x),mode)
                line += 1
            self.write(y - 2, 0, "_"*x, curses.A_NORMAL)
            self.write(y - 1, 0, " {}".format(selected), curses.A_NORMAL,typer=typing)
            if self.result!="":
                break
            self.window.refresh()
            curses.doupdate()
            if not mydir.expanded:
                updir = True
                prevbase.append(curdir)
                curdir = os.path.dirname(os.path.abspath(curdir))
                mydir = self.factory(curdir)
                mydir.expand()
            else:
                updir = False
                ch = self.window.getch()
                if ch == curses.KEY_UP:
                    curidx -= 1
                    typing = False
                elif ch == curses.KEY_DOWN:
                    curidx += 1
                    typing = False
                elif ch == curses.KEY_PPAGE:
                    curidx -= curses.LINES
                    typing = False
                    if curidx < 0:
                        curidx = 0
                elif ch == curses.KEY_NPAGE:
                    curidx += curses.LINES
                    typing = False
                    if curidx >= line:
                        curidx = line - 1
                elif ch == curses.KEY_RIGHT:
                    pending_action = 'expand'
                    typing = False
                elif ch == curses.KEY_LEFT:
                    pending_action = 'collapse'
                    typing = False
                elif ch == self.ESC:
                    break
                elif ch == ord('\n'):
                    if typing:
                        self.result = selected
                        break
                    pending_save = True
                elif 0 <= ch < 256:
                    if not typing:
                        selected = ""
                        typing = True
                    if ch == 8 or ch == 127:
                        selected = selected[:-1]
                    else:
                        selected += struct.pack('B', ch).encode("utf-8").decode("utf-8") 
            curidx %= line
        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()
    
    def write(self, line, col, msg, mode, offset = 3, typer = False):
        y, x = self.window.getmaxyx()
	if len(msg) > x-col and x-col > 3 and not typer:
            msg = msg[0:x-col-3] + "..."
        if typer and len(msg) + col > x - 5 and x - col > 5:
            msg = "..."+msg[len(msg)-(x-col-5):]
        if 0 <= line < y:
            curses.setsyx(line, 0)
            self.window.clrtoeol()
            self.window.addstr(line, col, msg, mode)
            if typer:
                self.window.addstr(line, len(msg), "_", curses.A_BLINK)# | curses.A_REVERSE)
            

def main(stdscr):
    cargo_cult_routine(stdscr)
    stdscr.nodelay(0)
    mydir = factory(start)
    mydir.expand()
    curidx = 3
    pending_action = None
    pending_save = False

    while 1:
        stdscr.clear()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        line = 0
        offset = max(0, curidx - curses.LINES + 3)
        for data, depth in mydir.traverse():
            if line == curidx:
                stdscr.attrset(curses.color_pair(1) | curses.A_BOLD)
                if pending_action:
                    getattr(data, pending_action)()
                    pending_action = None
                elif pending_save:
                    global result
                    result = data.name
                    return
            else:
                stdscr.attrset(curses.color_pair(0))
            if 0 <= line - offset < curses.LINES - 1:
                stdscr.addstr(line - offset, 0,
                              data.render(depth, curses.COLS))
            line += 1
        stdscr.refresh()
        ch = stdscr.getch()
        if ch == curses.KEY_UP: curidx -= 1
        elif ch == curses.KEY_DOWN: curidx += 1
        elif ch == curses.KEY_PPAGE:
            curidx -= curses.LINES
            if curidx < 0: curidx = 0
        elif ch == curses.KEY_NPAGE:
            curidx += curses.LINES
            if curidx >= line: curidx = line - 1
        elif ch == curses.KEY_RIGHT: pending_action = 'expand'
        elif ch == curses.KEY_LEFT: pending_action = 'collapse'
        elif ch == ESC: return
        elif ch == ord('\n'): pending_save = True
        curidx %= line

def cargo_cult_routine(win):
    win.clear()
    win.refresh()
    curses.nl()
    curses.noecho()
    win.timeout(0)

def open_tty():
    saved_stdin = os.dup(0)
    saved_stdout = os.dup(1)
    os.close(0)
    os.close(1)
    stdin = os.open('/dev/tty', os.O_RDONLY)
    stdout = os.open('/dev/tty', os.O_RDWR)
    return saved_stdin, saved_stdout

def restore_stdio(saved_fds):
    (saved_stdin, saved_stdout) = saved_fds
    os.close(0)
    os.close(1)
    os.dup(saved_stdin)
    os.dup(saved_stdout)

def getpath(file_or_dir = 1):
    global result, filechoice
    filechoice = file_or_dir
    result = ""
    #global start
    if len(sys.argv) > 1:
        start = sys.argv[1]
    saved_fds = open_tty()
    try: wrapper(main)
    finally: restore_stdio(saved_fds)
    return result

if __name__=="__main__":
    print(getpath())
