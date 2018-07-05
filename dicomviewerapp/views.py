from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import default_storage as storage
from django.contrib import messages
from .forms import UploadForm
from .models import DicomFile, DicomDataValue, DicomThumbnail
import dicomparser as dparse

def get_age_str(data):
	try:
		suffix = {'D': 'days', 'W': 'weeks', 'M': 'months', 'Y': 'years'}
		return str(int(data[:3])) + " " + suffix[data[3]]
	except:
		return str(data)

def get_value_from_data(vr, data):
	if vr == "AS":
		val = get_age_str(data)
	if type(data) == str or type(data) == unicode:
		val = data
	elif type(data) == int:
		val = str(data)
	else:
		val = "{} bytes of data".format(len(data))
	try:
		val = val.decode("utf-8")
	except:
		val = u""
	return val

def get_values(fields, values):
	if fields == []:
		return values
	f = fields[0]
	fields = fields[1:]
	group = f["group"]
	elt = f["element"]
	vr = f.get("vr", "")
	new_value = DicomDataValue(group = group,
		                       element = elt,
		                       vr = vr,
		                       meta = f.get("meta", False),
		                       parent = f["parent"])	
	if dparse.is_sequence(group, elt, vr):
		children = []
		for child in f["data"]:
			child["parent"] = new_value
			children.append(child)
		fields = fields + children
	else:
		val = get_value_from_data(f["data"])
		new_value.value = val
	values.append(new_value)
	return get_values(fields, values)

def handle_upload(file):
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        location = fs.location
	fields, thumbnail = dparse.parse_file(location + "/" + filename)
	size = file.size
	new_file = DicomFile(filename=file.name, filesize=file.size)
	for f in fields:
		f["parent"] = None
	new_values = get_values(fields, [])
	new_file.save()
	for nv in new_values:
		nv.file = new_file
		nv.save()
	if thumbnail is not None:
		t = DicomThumbnail()
		t.thumbnail = File(open(thumbnail, "r"))
		t.file = new_file
		t.save()

def index(request):
	saved_files = DicomFile.objects.all()
	return render(request,
		          'app/index.html',
		          {'files': saved_files, 'form': UploadForm()})

def upload(request):
	if request.method != "POST":
		return HttpResponseBadRequest()
	try:
		handle_upload(request.FILES['file'])
	except dparse.NotDicomException:
		messages.error(request, "The file you tried to upload was not a DICOM file. Please try again.")
	return HttpResponseRedirect('/app')

def details(request, pk):
	try:
		file_id = DicomFile.objects.get(pk=pk)
	except DicomFile.DoesNotExist:
		raise Http404("File with ID {} does not exist".format(pk))
	return render(request,
		          'app/file-detail.html',
		          {'file': file_id, 'values': file_id.get_values(), 'thumbnail': file_id.get_thumbnail()})
