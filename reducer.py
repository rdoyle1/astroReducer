#!/usr/bin/env python
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from scipy import stats
import sys
import os
from astropy.io import fits
from os import listdir, makedirs
from os.path import isfile, isdir, join, exists, splitext
import re
from getpath import getpath
import uuid
from multiprocessing import Pool, cpu_count
import signal, time
from pickler import *

import warnings
warnings.filterwarnings("error")

class reducer(object):
	def __init__(self):
		self.path = os.getcwd()
		self.bias_path = self.path
		self.dark_path = self.path
		self.flat_path = self.path
		self.light_path = self.path
		self.cal_data = {"BIAS":{}, "DARK":{}, "Flat Field":{}}

	def __pathfinder(self, info):
		path = raw_input(info).strip()
		if path=="":
			path = getpath()
		if not isdir(path):
			raise self.reduceError("\"{}\" is not a valid file path".format(path))
		else:
			return path


	class reduceError(RuntimeError):
		def __init__(self, errors):
			self.errors = errors

		def __str__(self):
			return "Error: {}".format(repr(self.errors))

	def files(self, path, filetype, (obj, exp, fil) = (None, None, None)):
		allfiles = [f for f in listdir(path) if isfile(join(path, f))]
		for i,f in list(enumerate(allfiles)):
			try:
				header = fits.getheader(join(path, f))
				if header["IMAGETYP"] != filetype:
					allfiles[i] = None
				if obj!=None and header["OBJECT"]!=obj:
					allfiles[i] = None
				if exp!=None and "EXPOSURE" in header and str(header["EXPOSURE"])!=exp:
					allfiles[i] = None
				elif exp!=None and "EXPTIME" in header and str(header["EXPTIME"])!=exp:
					allfiles[i] = None 
				if fil!=None and header["FILTER"]!=fil:
					allfiles[i] = None
			except (KeyError, IOError, Warning) as e:
				allfiles[i] = None
		return [f for f in allfiles if f != None]

	def gen_bias(self):
		onlyfiles = self.files(self.bias_path, "BIAS")
		if len(onlyfiles)==0:
			return ["Error: No bias files found."]
		for f in onlyfiles:
			data = fits.getdata(join(self.bias_path, f))
			if "data" not in self.cal_data["BIAS"]:
				self.cal_data["BIAS"]["data"] = data.astype(np.float64)
				self.cal_data["BIAS"]["master"] = True
			else:
				self.cal_data["BIAS"]["data"] += data.astype(np.float64)
		if "data" in self.cal_data["BIAS"]:
			self.cal_data["BIAS"]["data"] /= len(onlyfiles)
			#self.cal_data["BIAS"]["filename"] = self.__save_fits(self.bias_path, self.cal_data["BIAS"]["data"], "BIAS")
		return []

	def gen_darks(self):
		onlyfiles = self.files(self.dark_path, "DARK")
		if len(onlyfiles)==0:
			return ["Error: No dark files found."]
		for f in onlyfiles:
			head = fits.getheader(join(self.dark_path, f))
			data = fits.getdata(join(self.dark_path, f))
			if "EXPOSURE" in head:
				if head["EXPOSURE"] not in self.cal_data["DARK"]:
					self.cal_data["DARK"][str(head["EXPOSURE"])] = {"data":data.astype(np.float64), "image count":1, "master":False}
				else:
					self.cal_data["DARK"][str(head["EXPOSURE"])]["data"] += data.astype(np.float64)
					self.cal_data["DARK"][str(head["EXPOSURE"])]["image count"] += 1
			elif "EXPTIME" in head and "EXPOSURE" not in head:
				if head["EXPTIME"] not in self.cal_data["DARK"]:
					self.cal_data["DARK"][str(head["EXPTIME"])] = {"data":data.astype(np.float64), "image count":1, "master":False}
				else:
					self.cal_data["DARK"][str(head["EXPTIME"])]["data"] += data.astype(np.float64)
					self.cal_data["DARK"][str(head["EXPOSURE"])]["image count"] += 1
			else:   
				raise self.reduceError("No exposure time specified in fits header of {}".format(f))
		for tag in self.cal_data["DARK"]:
			self.cal_data["DARK"][tag]["data"] /= self.cal_data["DARK"][tag]["image count"]
			if "data" in self.cal_data["BIAS"]:
				self.cal_data["DARK"][tag]["data"] -= self.cal_data["BIAS"]["data"]
				self.cal_data["DARK"][tag]["master"] = True
			#self.cal_data["DARK"][tag]["filename"] = self.__save_fits(self.dark_path, self.cal_data["DARK"][tag]["data"], "DARK",{"EXPOSURE":float(tag)})
		return []

	def gen_flats(self):
		onlyfiles = self.files(self.flat_path, "Flat Field")
		if len(onlyfiles)==0:
			return ["Error: No flat field files found."]
		for f in onlyfiles:
			head = fits.getheader(join(self.flat_path, f))
			data = fits.getdata(join(self.flat_path, f))
			if "FILTER" in head:
				if head["FILTER"] not in self.cal_data["Flat Field"]:
					self.cal_data["Flat Field"][str(head["FILTER"])] = {"data":data.astype(np.float64), "image count":1, "master":False}
				else:
					self.cal_data["Flat Field"][str(head["FILTER"])]["data"] += data.astype(np.float64)
					self.cal_data["Flat Field"][str(head["FILTER"])]["image count"] += 1
			else:   
				raise self.reduceError("No filter specified in fits header of {}".format(f))
		for tag in self.cal_data["Flat Field"]:
			self.cal_data["Flat Field"][tag]["data"] /= self.cal_data["Flat Field"][tag]["image count"]
			if "data" in self.cal_data["BIAS"]:
				self.cal_data["Flat Field"][tag]["data"] -= self.cal_data["BIAS"]["data"]
				self.cal_data["Flat Field"][tag]["master"] = True
			self.cal_data["Flat Field"][tag]["median"] = np.median(self.cal_data["Flat Field"][tag]["data"])
			self.cal_data["Flat Field"][tag]["data"] /= self.cal_data["Flat Field"][tag]["median"]
			#self.cal_data["Flat Field"][tag]["filename"] = self.__save_fits(self.flat_path, self.cal_data["Flat Field"][tag]["data"], "FLAT",{"FILTER":tag})
		return []

	def update_cal(self):
		if "data" in self.cal_data["BIAS"]:
			for tag in self.cal_data["DARK"]:
				if not self.cal_data["DARK"][tag]["master"]:
					self.cal_data["DARK"][tag]["data"] -= self.cal_data["BIAS"]["data"]
					self.cal_data["DARK"][tag]["master"] = True
			for tag in self.cal_data["Flat Field"]:
				if not self.cal_data["Flat Field"][tag]["master"]:
					self.cal_data["Flat Field"][tag]["data"] *= self.cal_data["Flat Field"][tag]["median"]
					self.cal_data["Flat Field"][tag]["data"] -= self.cal_data["BIAS"]["data"]
					self.cal_data["Flat Field"][tag]["data"] /= self.cal_data["Flat Field"][tag]["median"]
					self.cal_data["Flat Field"][tag]["master"] = True


	def count_calib(self):
		count = 0
		if "data" in self.cal_data["BIAS"]:
			count+=1
		for tag in self.cal_data["DARK"]:
			count+=1
		for tag in self.cal_data["Flat Field"]:
			count+=1
		return count


	def save_calib(self):
		self.update_cal()
		if "data" in self.cal_data["BIAS"]:
			filename = self.__save_fits(self.bias_path, self.cal_data["BIAS"]["data"], "BIAS")
		for tag in self.cal_data["DARK"]:
			filename = self.__save_fits(self.dark_path, self.cal_data["DARK"][tag]["data"], "DARK",{"EXPOSURE":float(tag)})
		for tag in self.cal_data["Flat Field"]:
			filename = self.__save_fits(self.flat_path, self.cal_data["Flat Field"][tag]["data"], "FLAT",{"FILTER":tag})
	
	def check_calib(self, frame_type="ALL"):
		warnings = []
		if frame_type=="BIAS":
			if "data" not in self.cal_data["BIAS"]:
				warnings.append("Warning: No bias image found - can't do bias subtraction. Continue anyway?")
		elif frame_type=="DARK":
			if len(self.cal_data["DARK"])==0:
				warnings.append("Warning: No dark images found - can't account for dark current. Continue anyway?")
			else:
				for tag in self.cal_data["DARK"]:
					if not self.cal_data["DARK"][tag]["master"]:
						warnings.append("Warning: No bias frame applied to dark frame with exposure {}. Continue anyway?".format(tag))
		elif frame_type=="Flat Field":
			if len(self.cal_data["Flat Field"])==0:
				warnings.append("Warning: No flat images found - can't account for detector sensitivity. Continue anyway?")
			else:
				for tag in self.cal_data["Flat Field"]:
					if not self.cal_data["Flat Field"][tag]["master"]:
						warnings.append("Warning: No bias frame applied to flat frame with filter \"{}\". Continue anyway?".format(tag))
		elif frame_type=="ALL":
			warnings.extend(self.check_calib("BIAS"))
			warnings.extend(self.check_calib("DARK"))
			warnings.extend(self.check_calib("Flat Field"))
		else:
			warnings.append("Warning: Unknown frame type. Continue anyway?")
		return warnings

	def sigint_handler(self, signum, frame):
		pass

	def red_light(self, match=(None,None,None)):
		if not exists(join(self.light_path,"Corrected")):
			makedirs(join(self.light_path,"Corrected"))
		self.update_cal()
		onlyfiles = self.files(self.light_path, "LIGHT", match)
		use_cpus = (cpu_count()/2) + 1
		p = Pool(use_cpus)
		signal.signal(signal.SIGINT, self.sigint_handler)
		files = p.map(self.red_light_pool, onlyfiles)
		signal.signal(signal.SIGINT, signal.SIG_DFL)
		return files
	
	def red_light_pool(self, filename):
		image = fits.open(join(self.light_path,filename))
		data = image[0].data.astype(np.float64)
		if "data" in self.cal_data["BIAS"]:
			data -= self.cal_data["BIAS"]["data"]
		try:
			if "EXPOSURE" in image[0].header:
				if "data" in self.cal_data["DARK"][str(image[0].header["EXPOSURE"])]:
					data -= self.cal_data["DARK"][str(image[0].header["EXPOSURE"])]["data"]
			elif "EXPTIME" in image[0].header:
				if "data" in self.cal_data["DARK"][str(image[0].header["EXPTIME"])]:
					data -= self.cal_data["DARK"][str(image[0].header["EXPTIME"])]["data"]
			else:
				image.close()
				return "{} not reduced - no exposure specified in header".format(filename)
				#raise self.reduceError("No exposure time specified in {}".format(filename))
		except KeyError:
			pass
			#raise self.reduceError("No matching dark frames for {}".format(filename))
		try:
			if "FILTER" in image[0].header:
				if "data" in self.cal_data["Flat Field"][str(image[0].header["FILTER"])]:
					data /= self.cal_data["Flat Field"][str(image[0].header["FILTER"])]["data"]
			else:   
				image.close()
				return "{} not reduced - no filter specified in header".format(filename)
				#raise self.reduceError("No filter specified in {}".format(filename))
		except KeyError:
			pass
			#raise self.reduceError("No matching flat frames for {}".format(filename))
		data = np.clip(data, 0, 2**(image[0].header["BITPIX"])-1)
		data = self.__convert_array(data, image[0].header["BITPIX"])
		image[0].data = data
		image.writeto(join(join(self.light_path,"Corrected"), filename), clobber=True)
		image.close()
		return join(join(self.light_path,"Corrected"), filename)

	def __convert_array(self, data, bitpix):
		if bitpix > 0:
			data = np.clip(data, 0, 2**(bitpix)-1)
		if bitpix == 8:
			data = data.astype(np.uint8)
		elif bitpix == 16:
			data = data.astype(np.uint16)
		elif bitpix == 32:
			data = data.astype(np.uint32)
		elif bitpix == -32:
			data = data.astype(np.float32)
		elif bitpix == -64:
			data = data.astype(np.float64)
		else:   
			raise self.reduceError("Unknown BITPIX: {}".format(bitpix))
		return data

	def __save_fits(self, path, data, filetype, tags = {}, bitpix=-32):
		data = self.__convert_array(data, bitpix)
		hdu = fits.PrimaryHDU(data)
		newfits = fits.HDUList([hdu])
		ext = "-"
		for tag in tags:
			ext += str(tags[tag]) + "-"
			newfits[0].header[tag] = tags[tag]
		filename = join(path, "{}{}{}".format(filetype, ext, self.__gen_temp_fits()))
		newfits[0].header["BITPIX"]=bitpix
		#if not exists(path):
		#	makedirs(path)
		newfits.writeto(filename, clobber = True)
		return filename

	def __gen_temp_fits(self):
		return "{}.fits".format(uuid.uuid4())

