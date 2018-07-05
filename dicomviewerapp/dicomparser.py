import sys
import struct
import os

Debug = False

type1_vrs = ["OB", "OW", "OF", "SQ", "UT", "UN"]
padded_vrs = ["AE", "CS", "DA", "DS", "DT", "IS", "LO", "SH", "TM"]
null_padded_vrs = ["OB", "PN", "UI"]
long_vrs = ["LT", "UT"]

string_vrs = padded_vrs + null_padded_vrs + long_vrs

class NotDicomException(Exception):
	pass

def read_data_value(f, field, length):
	data = f.read(length)
	vr = field.get("vr", "")
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
		return None
	group, elt = struct.unpack("<HH", tag)
	field = {"group": group, "element": elt}

	if group == 0xfffe and elt == 0xe000: # sequence item
		item_length = struct.unpack("<L", f.read(4))[0]
		if item_length == 0xffffffff:
			item_fields = []
			while True:
				cur = parse_field(f)
				if cur:
					item_fields.append(cur)
				else:
					break
			return item_fields
		else:
			return read_data_value(f, field, item_length)
	elif group == 0xfffe and elt == 0xe00d: # item delimiter
		f.read(4)
		return None
	elif group == 0xfffe and elt == 0xe0dd: # sequence delimiter
		f.read(4)
		return None
	else:
		vr = struct.unpack("2s", f.read(2))[0]
		field["vr"] = vr.decode("utf-8")
		if vr in type1_vrs:
			if is_sequence(group, elt, vr):
				f.read(6)
				field["data"] = []
				while True:
					seq_field = parse_field(f)
					if seq_field is None:
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

def save_thumbnail(filename):
	import subprocess
	import os.path
	from PIL import Image

	last_dot = filename.rfind(".")
	if last_dot == -1:
		jpeg_filename = filename + ".jpg"
	else:
		jpeg_filename = filename[:last_dot] + ".jpg"

	# extract the JPEG from the DICOM file
	print subprocess.check_output(["dcmj2pnm", filename, jpeg_filename])

	if os.path.isfile(jpeg_filename):
		# convert the JPEG into a readable format for pillow
		print subprocess.check_output(["econvert", "-i", jpeg_filename, "-o", jpeg_filename])
		i = Image.open(jpeg_filename)
		i.thumbnail((128, 128))
		thumbnail_fname = jpeg_filename[:-3] + "thumbnail.jpg"
		i.save(thumbnail_fname)
		return thumbnail_fname
	else:
		return None

def print_field(field):
	vr = field.get("vr", "")
	g = str(field["group"])
	e = str(field["element"])
	data = ""
	if vr == "OB" and field["group"] == 0x7fe0 and field["element"] == 0x10:
		data = "pixel data with " + str(len(field["data"])) + " items"
	elif vr in string_vrs:
		data = field["data"]
	elif vr == "SQ":
		data = "sequence with " + str(len(field["data"])) + " elements"
	elif vr == "US":
		data = str(field["data"])
	else:
		data = str(len(field["data"])) + " bytes"
	print "\t(" + g + "," + e + ") - " + vr + ": " + data

def parse_file(filename, f):
	f.seek(0)
	f.read(128)
	header = f.read(4)
	if header.decode("utf-8") != "DICM":
		raise NotDicomException
	meta_fields = [parse_field(f) for i in xrange(6)]

	data_fields = []
	while True:
		cur_field = parse_field(f)
		if cur_field == None:
			break
		elif in_optional_meta(cur_field):
			meta_fields.append(cur_field)
		else:
			data_fields.append(cur_field)
			if Debug:
				print_field(cur_field)

	for f in meta_fields:
		f["meta"] = True

	thumbnail = None
	for field in data_fields:
		if field["group"] == 0x7fe0 and field["element"] == 0x10:
			try:
				thumbnail = save_thumbnail(filename)
			except:
				print "\tSaving thumbnail failed for {}".format(filename)
			break

	return (meta_fields + data_fields), thumbnail

def parse_file_from_str(filename):
	with open(filename, "rb") as f:
		parse_file(filename, f)
		
if __name__ == "__main__":
	files = [os.path.join(dp, f) for dp, dn, fnames in os.walk(sys.argv[1]) for f in fnames]
	Debug = True
	for d in files:
		print "Parsing {}".format(d)
		try:
			parse_file_from_str(d)
		except NotDicomException:
			print "\tNot a dicom file!"
		except:
			raise
