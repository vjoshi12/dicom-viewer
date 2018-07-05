# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.urls import reverse
from constants import tag_map, vr_map

class DicomFile(models.Model):
	filename = models.CharField(max_length=200)
	filesize = models.IntegerField()

	def __str__(self):
		return self.filename

	def filesize_str(self):
		size = self.filesize
		if size < 1000:
			return "{} B".format(size)
		elif size < 1000000:
			return "{0:.2f} KB".format((size / 1000.0))
		elif size < 1000000000:
			return "{0:.2f} MB".format((size / 1000000.0))
		else:
			return "{0:.2f} GB".format((size / 1000000000.0))		

	def get_num_values(self):
		return len(DicomDataValue.objects.filter(file=self))

	def get_values(self):
		return DicomDataValue.objects.filter(file=self)

	def get_absolute_url(self):
		return reverse("file-detail", args=[self.id])

class DicomDataValue(models.Model):
	group = models.IntegerField()
	element = models.IntegerField()
	vr = models.CharField(max_length=5)
	meta = models.BooleanField()
	value = models.CharField(max_length=500)
	parent = models.ForeignKey('self', null=True, on_delete=models.CASCADE)
	file = models.ForeignKey('DicomFile', on_delete=models.CASCADE)

	def tag(self):
		return "(0x{:04x}, 0x{:04x})".format(self.group, self.element)

	def tag_desc(self):
		return tag_map.get((self.group, self.element), "")

	def vr_desc(self):
		return "{} ({})".format(vr_map.get(self.vr, ""), self.vr)

class DicomThumbnail(models.Model):
	thumbnail = models.ImageField()
	file = models.ForeignKey('DicomFile', on_delete=models.CASCADE)
