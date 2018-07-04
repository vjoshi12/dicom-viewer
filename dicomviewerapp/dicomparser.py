import sys
import numpy
import struct
import io
import os
from PIL import Image

type1_vrs = ["OB", "OW", "OF", "SQ", "UT", "UN"]
padded_vrs = ["AE", "CS", "DA", "DS", "DT", "IS", "LO", "SH", "TM"]
null_padded_vrs = ["OB", "PN", "UI"]
long_vrs = ["LT", "UT"]

string_vrs = padded_vrs + null_padded_vrs + long_vrs

class NotDicomException(Exception):
	pass

def read_data_value(f, field, length):
	data = f.read(length)
	vr = ""
	if "vr" in field:
		vr = field["vr"]
	try:
		if vr in long_vrs:
			data = data.decode("utf-8").rstrip(" ")
		elif vr in null_padded_vrs:
			data = data.decode("utf-8").rstrip("\0")
		elif vr in padded_vrs:
			data = data.decode("utf-8").strip()
		elif vr == "US":
			data = struct.unpack("<H", data)[0]
	except:
		data = ""
	field["data"] = data
	return field

def is_sequence(group, elt, vr):
	return vr == "SQ" or (vr == "OB" and group == 0x7fe0 and elt == 0x10)

def parse_field(f):
	tag = f.read(4)
	if tag == "":
		return ""
	group, elt = struct.unpack("<HH", tag)
	field = {"group": group, "element": elt}

	if group == 0xfffe and elt == 0xe000: # sequence item
		item_length = struct.unpack("<L", f.read(4))[0]
		if item_length == 0xffffffff:
			item_fields = []
			while True:
				cur = parse_field(f)
				if cur == "":
					break
				item_fields.append(cur)
			return item_fields
		else:
			return read_data_value(f, field, item_length)
	elif group == 0xfffe and elt == 0xe00d: # item delimiter
		f.read(4)
		return ""
	elif group == 0xfffe and elt == 0xe0dd: # sequence delimiter
		f.read(4)
		return ""
	else:
		vr = struct.unpack("2s", f.read(2))[0]
		field["vr"] = vr.decode("utf-8")
		length = 0
		if vr in type1_vrs:
			if is_sequence(group, elt, vr):
				f.read(6)
				field["data"] = []
				while True:
					seq_field = parse_field(f)
					if seq_field == "":
						break
					elif type(seq_field) == list:
						field["data"] = field["data"] + seq_field
					else:
						field["data"].append(seq_field)
				return field
			else:
				f.read(2)
				length = struct.unpack("<L", f.read(4))[0]
				return read_data_value(f, field, length)
		else:
			length = struct.unpack("<H", f.read(2))[0]
			return read_data_value(f, field, length)

def in_optional_meta(field):
	return field["group"] == 0x2 and field["element"] in [0x13, 0x16, 0x0100, 0x0102]

def save_pixel_data(filename, fields):
	import pydicom

	ds = pydicom.dcmread(filename)
	data = ds.pixel_array
	fio = io.BytesIO(data)
	i = Image.open(fio)
	i.thumbnail(128, 128)
	i.save(filename + ".thumbnail", "JPEG")

def ok():
	fieldMap = {}
	for f in fields:
		if f["group"] not in fieldMap:
			fieldMap[f["group"]] = {f["element"]: f["data"]}
		else:
			fieldMap[f["group"]][f["element"]] = f["data"]

	bits_allocated = fieldMap[0x28][0x100]
	if bits_allocated == 1:
		format_str = "uint8"
	elif fieldMap[0x28][0x103] == 0: # pixel representation
		format_str = "uint{}".format(bits_allocated)
	elif fieldMap[0x28][0x103] == 1:
		format_str = "int{}".format(bits_allocated)
	else:
		format_str = "bad_pixel_representation"

	try:
		numpy_dtype = numpy.dtype(format_str)
	except TypeError:
		msg = "Data type {} not valid".format(format_str)
		raise TypeError(msg)

	pixels = fieldMap[0x7fe0][0x10]
	pixels_len = len(pixels)
	rows = fieldMap[0x28][0x10]
	cols = fieldMap[0x28][0x11]
	expected_len = rows * cols
	frames = 1
	if 0x8 in fieldMap[0x28]: # number of frames
		frames = int(fieldMap[0x28][0x8])

	if frames != 1:
		raise "CANT HANDLE"

	full_data = b"".join([d["data"] for d in pixels])
	fio = io.BytesIO(full_data)
	i = Image.open(fio)

def parse_file(filename, f):
	f.seek(0)
	f.read(128)
	header = f.read(4)
	if header.decode("utf-8") != "DICM":
		raise NotDicomException
	parse_field(f) # length
	parse_field(f) # version
	fields = list()
	media_class_uid = parse_field(f)
	fields.append(media_class_uid)
	media_instance_uid = parse_field(f)
	fields.append(media_instance_uid)
	transfer_syntax_uid = parse_field(f)
	fields.append(transfer_syntax_uid)
	impl_class_uid = parse_field(f)
	fields.append(impl_class_uid)

	print "\tParsed metadata..."

	data_fields = list()
	while True:
		cur_field = parse_field(f)
		fields.append(cur_field)
		if in_optional_meta(cur_field):
			fields.append(cur_field)
		else:
			data_fields.append(cur_field)
			break

	while True:
		cur_field = parse_field(f)
		if cur_field == "":
			break
		else:
			data_fields.append(cur_field)
			vr = ""
			if "vr" in cur_field:
				vr = cur_field["vr"]
			g = str(cur_field["group"])
			e = str(cur_field["element"])
			data = ""
			if vr == "OB" and cur_field["group"] == 0x7fe0 and cur_field["element"] == 0x10:
				data = "pixel data with " + str(len(cur_field["data"])) + " items"
			elif vr in string_vrs:
				data = cur_field["data"]
			elif vr == "SQ":
				data = "sequence with " + str(len(cur_field["data"])) + " elements"
			elif vr == "US":
				data = str(cur_field["data"])
			else:
				data = str(len(cur_field["data"])) + " bytes"
			print "(" + g + "," + e + ") - " + vr + ": " + data

	print "\tGot " + str(len(fields)) + " meta fields"
	print "\tGot " + str(len(data_fields)) + " data fields"

	for f in fields:
		f["meta"] = True

	for field in data_fields:
		if field["group"] == 0x7fe0 and field["element"] == 0x10:
			print "\tSaving pixel data..."
			save_pixel_data(filename, data_fields)
			break

	return fields + data_fields

def parse_file_from_str(filename):
	with open(filename, "rb") as f:
		parse_file(filename, f)
		
if __name__ == "__main__":
	dicom_files = [os.path.join(dp, f) for dp, dn, fnames in os.walk(sys.argv[1]) for f in fnames]
	for d in dicom_files:
		print "Parsing {}".format(d)
		try:
			parse_file_from_str(d)
		except NotDicomException:
			print "\tNot a dicom file!"
		except NotImplementedError:
			print "\tNot implemented error"
			raise
		except:
			raise