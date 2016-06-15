#!/usr/bin/env python2

import curses
from curses import panel
import os, getpath, reducer
from astropy.io import fits
from os import listdir, makedirs
from os.path import isfile, isdir, join, exists, splitext
import time

class Menu(object):

    def __init__(self, items, stdscreen, title, submenu=0):
        self.window = stdscreen.subwin(0,0)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()
        self.title = title
        self.submenu=submenu
        self.breakout=False
        self.cancel=False
        self.confirmed=False

        self.position = 0
        self.items = items
        if submenu==3:
            self.items.append(('Ok', self.exit))
        elif submenu==2:
            self.items.append(('No',self.exit))
        elif submenu==1:
            self.items.append(('Go Back',self.exit))
        else:
            self.items.append(('Exit',self.exit))

    def exit(self):
        self.cancel=True

    def new_items(self,items):
        items.append(self.items[-1])
        self.items = items

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items)-1

    def write(self, line, col, msg, mode, offset = 3):
        y, x = self.window.getmaxyx()
        if len(msg.rstrip()) > x-col and x-col > 3:
            msg = msg[0:x-col-3] + "..."
        if 0 <= line < y:
            curses.setsyx(line, 0)
            self.window.clrtoeol()
            self.window.addstr(line, col, msg, mode)

    def init_display(self):
        if self.submenu==3:
            curses.flash()
            curses.beep()

    def display(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()
        self.confirmed = False
        self.cancel=False
        self.breakout=False
        self.init_display()

        while True:
            if self.breakout:
                self.confirmed = True
                break
            if self.cancel:
                break
            self.window.refresh()
            curses.doupdate()

            mode = curses.A_NORMAL
            msg = " {} ".format(self.title)
            self.write(1, 1, msg, mode, 1)
            y, x = self.window.getmaxyx()
            self.write(2, 0, "_"*x, curses.A_NORMAL)
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL
                if self.submenu < 2:
                    msg = " {}. {} ".format(index, item[0])
                else:
                    msg = " {} ".format(item[0])
                self.write(3+index, 1, msg, mode)

            key = self.window.getch()

            if key in [curses.KEY_ENTER, ord('\n')]:
                #if self.position == len(self.items)-1:
                #    break
                #else:
                if len(self.items[self.position])>2:
                    self.items[self.position][1](self.items[self.position][2:])
                else:
                    self.items[self.position][1]()

            elif key == curses.KEY_UP:
                self.navigate(-1)

            elif key == curses.KEY_DOWN:
                self.navigate(1)

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()

    def end(self):
        self.breakout=True

    def change_title(self,title):
        self.title = title

class MyApp(object):

    def __init__(self, stdscreen):
        self.screen = stdscreen
        curses.curs_set(0)
        self.path = os.getcwd()
        
        self.allowtarget = False
        self.targetname = None
        self.obj_criteria = (None, None, None)
        self.datareducer = reducer.reducer()
        self.filemenu = getpath.FileMenu(self.screen, "", 1, self.path)
        self.conf_menu = Menu([], self.screen, "", 2)
        self.conf_menu.items.insert(0,("Yes", self.conf_menu.end))
        self.note = Menu([], self.screen, "", 3)
        self.objects = []
        self.objectmenu = Menu(self.objects, self.screen, "Object Selection Menu", 1)
 
        self.cal_items = [
                ('Select Bias Directory & Generate Master Bias', self.bias),
                ('Select Dark Directory & Generate Master Darks', self.dark),
		('Select Flat Directory & Generate Master Flats', self.flat),
		('Save Calibration Images', self.save)
                ]
        calibration = Menu(self.cal_items, self.screen, "Calibration Menu", 1)

	self.light_items = [
                ('Select Data Directory', self.lightdir),
		('Select Target', self.selecttarget)
                ]
        light = Menu(self.light_items, self.screen, "Data Menu", 1)

        self.main_menu_items = [
                ('Set Up Calibration Images', calibration.display),
                ('Set Up Data Images', light.display),
                ('Run Reducer', self.run)
                ]
        main_menu = Menu(self.main_menu_items, self.screen, "Data Reducer Main Menu")
        main_menu.display()

    def empty(self):
        pass
    
    def bias(self):
        while True:
            self.filemenu.set_title("Select Bias Directory")
            self.filemenu.display()
            if self.filemenu.result != "":
                if not exists(self.filemenu.result):
                    self.alert("Error: {} doesn't exist.".format(self.filemenu.result))
                    return
                self.datareducer.bias_path = self.filemenu.result
                if not self.confirm("Generate biases from \"{}\"? (Screen will go blank until process finishes)".format(self.filemenu.result)):
                    return
                for error in self.datareducer.gen_bias():
                    self.alert(error)
                return
            else:
                if self.confirm("Do you want to cancel and go back to the menu?"):
                    return

    def flat(self):
        while True:
            self.filemenu.set_title("Select Flat Directory")
            self.filemenu.display()
            if self.filemenu.result != "":
                if not exists(self.filemenu.result):
                    self.alert("Error: {} doesn't exist.".format(self.filemenu.result))
                    return
                self.datareducer.flat_path = self.filemenu.result
                if not self.confirm("Generate flats from \"{}\"? (Screen will go blank until process finishes)".format(self.filemenu.result)):
                    return
                for warning in self.datareducer.check_calib("BIAS"):
                    if not self.confirm(warning):
                        return
                for error in self.datareducer.gen_flats():
                    self.alert(error)
                return
            else:
                if self.confirm("Do you want to cancel and go back to the menu?"):
                    return

    def dark(self):
        while True:
            self.filemenu.set_title("Select Dark Directory")
            self.filemenu.display()
            if self.filemenu.result != "":
                if not exists(self.filemenu.result):
                    self.alert("Error: {} doesn't exist.".format(self.filemenu.result))
                    return
                self.datareducer.dark_path = self.filemenu.result
                if not self.confirm("Generate darks from \"{}\"? (Screen will go blank until process finishes)".format(self.filemenu.result)):
                    return
                for warning in self.datareducer.check_calib("BIAS"):
                    if not self.confirm(warning):
                        return
                for error in self.datareducer.gen_darks():
                    self.alert(error)
                return
            else:
                if self.confirm("Do you want to cancel and go back to the menu?"):
                    return
    
    def lightdir(self):
        while True:
            self.filemenu.set_title("Select Data Directory")
            self.filemenu.display()
            if self.filemenu.result != "":
                if not exists(self.filemenu.result):
                    self.alert("Error: {} doesn't exist.".format(self.filemenu.result))
                    return
                self.datareducer.light_path = self.filemenu.result
                self.allowtarget=True
                self.alert("Data directory set to {}".format(self.filemenu.result))
                return
            else:
                if self.confirm("Do you want to cancel and go back to the menu?"):
                    return

    def object_permanence(self, val):
        name, obj, exp, fil = val[0]
        self.targetname = name
        self.obj_criteria = (obj, exp, fil)
	self.objectmenu.breakout=True

    def run(self):
        if not self.allowtarget:
            self.alert("No data directory specified, can't reduce data")
            return
        if self.targetname==None:
            self.alert("No target specified. Can't reduce data.")
            return
        for warning in self.datareducer.check_calib("ALL"):
            if not self.confirm(warning):
                return
        if self.confirm("Corrected images will be stored in \"{}\"".format(join(self.datareducer.light_path,"Corrected"))):
            allfiles = self.datareducer.red_light(self.obj_criteria)
	    self.alert("Reduction successful!")

    def selecttarget(self):
        if not self.allowtarget:
            self.alert("No data directory specified, can't select a target")
            return
        while True:
            self.targetname = None
            self.obj_criteria = (None, None, None)
            targets = {}
            onlyfiles = self.datareducer.files(self.datareducer.light_path, "LIGHT")
            for filename in onlyfiles:
                header = fits.getheader(join(self.datareducer.light_path, filename))
                if "OBJECT" in header:
                    objkey = header["OBJECT"]
                    if objkey not in targets:
                        targets[objkey]={"exp":{},"f":{}}
                    if "EXPOSURE" in header:
                        expkey = str(header["EXPOSURE"])
                        if expkey not in targets[objkey]["exp"]:
                            targets[objkey]["exp"][expkey] = True
                    elif "EXPTIME" in header:
                        expkey = str(header["EXPTIME"])
                        if expkey not in targets[objkey]["exp"]:
                            targets[objkey]["exp"][expkey] = True
                    if "FILTER" in header:
                        fkey = header["FILTER"]
                        if fkey not in targets[objkey]:
                            targets[objkey]["f"][fkey] = True
            names = []
            for obj in targets:
                name = "{} ".format(obj)
                if len(targets[obj]["exp"])==0 and len(targets[obj]["f"])==0:
                    names.append((obj,obj,None,None))
                elif len(targets[obj]["exp"])==0 and len(targets[obj]["f"])!=0:
                    for f in targets[obj]["f"]:
                        names.append(("{}, Filter {}".format(obj, f), obj, None, f))
                elif len(targets[obj]["exp"])!=0 and len(targets[obj]["f"])==0:
                    for expkey in targets[obj]["exp"]:
                        names.append(("{}, Exposure {}".format(obj, expkey), obj, exp, None))
                elif len(targets[obj]["exp"])!=0 and len(targets[obj]["f"])!=0:
                    for expkey in targets[obj]["exp"]:
                        for f in targets[obj]["f"]:
                            names.append(("{}, Exposure {}, Filter {}".format(obj, expkey, f) , obj, expkey, f))
                else:
                    raise Exception("Something Happened... IDK what.")
            objects = [(name, self.object_permanence, (name, obj, exp, fil)) for (name,obj,exp,fil) in names]
            if len(objects)==0:
                self.alert("No objects found. Check you have the right directory.")
                return
            objects.append(("Select All Files", self.object_permanence, ("All Files", None, None, None)))
	    self.objectmenu.new_items(objects)
            self.objectmenu.display()
            if self.targetname==None:
                return
            if self.confirm("Select {} as target?".format(self.targetname)):
		return

    def save(self):
        num_save = self.datareducer.count_calib()
        if num_save<=0:
            self.alert("No calibration images open to save.")
        elif self.confirm("Do you want to save all ({}) calibration images? (Unique filenames are generated)".format(num_save)):
            self.datareducer.save_calib()
            self.alert("{} images were saved.".format(num_save))
    
    def alert(self,msg):
        self.note.change_title(msg)
        self.note.display()

    def confirm(self, msg):
        self.conf_menu.change_title(msg)
        self.conf_menu.display()
        if self.conf_menu.confirmed:
            return True
        else:
            return False
        

if __name__ == '__main__':
    curses.wrapper(MyApp)
