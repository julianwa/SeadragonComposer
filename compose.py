#!/usr/bin/python

#
# Seadragon Composer
#
#  Copyright (c) 2011, Julian Walker <julianreidwalker@gmail.com>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without modification,
#  are permitted provided that the following conditions are met:
#
#      1. Redistributions of source code must retain the above copyright notice,
#         this list of conditions and the following disclaimer.
#
#      2. Redistributions in binary form must reproduce the above copyright
#         notice, this list of conditions and the following disclaimer in the
#         documentation and/or other materials provided with the distribution.
#
#      3. Neither the name of OpenZoom nor the names of its contributors may be used
#         to endorse or promote products derived from this software without
#         specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#  ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import sys
import os
import Image
import math
import subprocess
import optparse
from xmlobject import XMLFile

TILE_SIZE = 254L

def ceilLog2(x):
	"""Returns the ceiling of the log base 2 of the given long."""
	result = 0
	while x > (1L << result):
		result = result + 1
	return result

################################################################################

def clamp(x, l, r):
	"""Returns the value x clamped to to the range [l, r]."""
	if (x < l):
		x = l
	if (x > r):
		x = r
	return x

################################################################################

def divPow2RoundUp(x, n):
	"""Returns the value x divided by 2^n, rounded up."""
	return (x + (1L << n) - 1) / (1L << n);

################################################################################

def calcLodSize(finestLodSize, lod):
	"""Returns the size of the given level of detail."""
	lodDiff = ceilLog2(finestLodSize[0]) - lod
	return (divPow2RoundUp(finestLodSize[0], lodDiff), divPow2RoundUp(finestLodSize[1], lodDiff))

################################################################################

class Rect:

	def __init__(self, x0 = 0, y0 = 0, x1 = 0, y1 = 0):
		self.x0 = x0
		self.y0 = y0
		self.x1 = x1
		self.y1 = y1

	def width(self):
		return self.x1 - self.x0

	def height(self):
		return self.y1 - self.y0

	def size(self):
		return (self.x1 - self.x0, self.y1 - self.y0)

	def area(self):
		return (self.x1 - self.x0) * (self.y1 - self.y0)

	def empty(self):
		return self.x0 >= self.x1 or self.y0 >= self.y1

	def intersection(self, rect):
		return Rect(
			max(self.x0, rect.x0),
			max(self.y0, rect.y0),
			min(self.x1, rect.x1),
			min(self.y1, rect.y1)
		)

	def __getitem__(self, index):
		""" Returns the discrete point at the given index, in row-major order. Only valid for discrete Rects."""

		w = self.x1 - self.x0

		if not isinstance(w, (int, long)):
			raise Exception("May only be applied to discrete Rects.")

		return (index / w, index % w)


	def __iter__(self):
		""" Returns an iterator over the discrete points in the Rect, in row-major order. Only valid for discrete Rects."""

		if not isinstance(self.x0, (int, long)):
			raise Exception("May only be applied to discrete Rects.")

		for y in range(self.y0, self.y1):
			for x in range(self.x0, self.x1):
				yield (x, y)

	def __str__(self):
		return "Rect(" + str(self.x0) + "," + str(self.y0) + "," + str(self.x1) + "," + str(self.y1) + ")"

################################################################################

class SceneNode:
	def __init__(self, imagePath, x, y, width, height, zOrder):
		self.imagePath = imagePath
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.zOrder = zOrder
		self.imageSize = (0,0)

	def finestIntersectingLod(self, finestLodSize):
		return ceilLog2(finestLodSize[0]) - int(math.floor(math.log(finestLodSize[0] * self.width / self.imageSize[0], 2)))

	def lodRect(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in pixels at the given level of detail."""
		lodSize = calcLodSize(finestLodSize, lod)
		return Rect(
			self.x * lodSize[0],
			self.y * lodSize[1],
			(self.x + self.width) * lodSize[0],
			(self.y + self.height) * lodSize[1]
		)

	def discreteLodRect(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in pixels at the given level of detail."""
		lodRect = self.lodRect(finestLodSize, lod)
		lodSize = calcLodSize(finestLodSize, lod)
		return Rect(
			clamp(long(math.floor(lodRect.x0)), 0, lodSize[0]),
			clamp(long(math.floor(lodRect.y0)), 0, lodSize[1]),
			clamp(long(math.ceil(lodRect.x1)), 0, lodSize[0]),
			clamp(long(math.ceil(lodRect.y1)), 0, lodSize[1])
		)

	def tileRect(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in tiles at the given level of detail."""
		discreteLodRect = self.discreteLodRect(finestLodSize, lod)
		if discreteLodRect.area() > 1:
			return Rect(
				discreteLodRect.x0 / TILE_SIZE,
				discreteLodRect.y0 / TILE_SIZE,
				(discreteLodRect.x1 + (TILE_SIZE - 1)) / TILE_SIZE,
				(discreteLodRect.y1 + (TILE_SIZE - 1)) / TILE_SIZE)
		else:
			return Rect()

	def renderToTile(self, finestLodSize, tile):

		lod = tile[0]
		tileX = tile[1]
		tileY = tile[2]

		lodSize = calcLodSize(finestLodSize, lod)
		lodRect = Rect(0, 0, lodSize[0], lodSize[1])

		sceneNodeLodRect = self.lodRect(finestLodSize, lod)

		scaleFactor = sceneNodeLodRect.width() / self.imageSize[0]

		tileRect = Rect(tileX * TILE_SIZE, tileY * TILE_SIZE, (tileX + 1) * TILE_SIZE, (tileY + 1) * TILE_SIZE).intersection(lodRect)

		srcOffset = ((tileRect.x0 - sceneNodeLodRect.x0) / scaleFactor, (tileRect.y0 - sceneNodeLodRect.y0) / scaleFactor)

		outputPath = os.path.join("argh", "{0}_{1}_{2}_{3}.png".format("blah", lod, tileX, tileY))

		args = [
			"convert",
			self.imagePath,
			"-background", "transparent",
			"-virtual-pixel", "transparent",
			"-interpolate", "Bicubic",
			"-define", "distort:viewport={0}x{1}+0+0".format(tileRect.width(), tileRect.height()),
			"-distort", "SRT", "{0},{1}, {2}, 0, 0,0".format(srcOffset[0], srcOffset[1], scaleFactor),
			outputPath
		]

		process = subprocess.Popen(args)
		process.wait()

################################################################################

def determineCompositeImageSize(sceneGraph):
	""" Determines the composite image size in pixels, based on the size and layout of the scene nodes."""
	maxWidth = sys.float_info.min

	for sceneNode in sceneGraph["sceneNodes"]:
		impliedWidth = sceneNode.imageSize[0] / sceneNode.width
		if (impliedWidth > maxWidth):
			maxWidth = impliedWidth

	return (long(math.ceil(maxWidth)), long(math.ceil(maxWidth / sceneGraph["aspectRatio"])))

################################################################################

def parseSparseImageSceneGraph(sceneGraphPath):
	x = XMLFile(path=sceneGraphPath)

	containingFolder = os.path.dirname(sceneGraphPath)

	sceneGraph = { "aspectRatio" : float(x["SceneGraph"]["AspectRatio"]._children[0]._value) }

	sceneNodes = sceneGraph["sceneNodes"] = []

	for sceneNodeNode in x["SceneGraph"]["SceneNode"]:

		sceneNode = SceneNode(
			os.path.join(containingFolder, sceneNodeNode.FileName._children[0]._value.replace('\\', '/')),
			float(sceneNodeNode.x._children[0]._value),
			float(sceneNodeNode.y._children[0]._value),
			float(sceneNodeNode.Width._children[0]._value),
			float(sceneNodeNode.Height._children[0]._value),
			int(sceneNodeNode.ZOrder._children[0]._value)
		)

 		sceneNode.imageSize = Image.open(sceneNode.imagePath).size

		sceneNodes.append(sceneNode)

	# Sort the scene nodes by ascending z-order
	sceneNodes.sort(key=lambda sceneNode: sceneNode.zOrder)

	return sceneGraph

################################################################################

def main():

	sceneGraph = parseSparseImageSceneGraph(sys.argv[1])
	compositeImageSize = determineCompositeImageSize(sceneGraph)

	tileRenders = {}

	for sceneNode in sceneGraph["sceneNodes"]:

		for lod in reversed(range(1, sceneNode.finestIntersectingLod(compositeImageSize))):

			tileRect = sceneNode.tileRect(compositeImageSize, lod)

			if tileRect.empty():
				break

			for tileCoord in tileRect:
				sceneNode.renderToTile(compositeImageSize, (lod, tileCoord[0], tileCoord[1]))

################################################################################

if __name__ == "__main__":
    main()