#!/usr/bin/python

#
# Seadragon Composer
#
#  Copyright (c) 2011, Julian Walker <julianreidwalker@gmail.com>
#  All rights reserved.
#
#  Some of the code found here was adapted from https://github.com/openzoom/deepzoom.py,
#  developed by: Daniel Gasienica <daniel@gasienica.ch> and Kapil Thangavelu <kapil.foss@gmail.com>.
#
#  Redistribution and use in source and binary forms, with or without modification,
#  are permitted provided that the following conditions are met:
#
#	   1. Redistributions of source code must retain the above copyright notice,
#		  this list of conditions and the following disclaimer.
#
#	   2. Redistributions in binary form must reproduce the above copyright
#		  notice, this list of conditions and the following disclaimer in the
#		  documentation and/or other materials provided with the distribution.
#
#	   3. Neither the name of OpenZoom nor the names of its contributors may be used
#		  to endorse or promote products derived from this software without
#		  specific prior written permission.
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
import time
import urllib
import xml.dom.minidom

try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

TILE_SIZE = 254L
NS_DEEPZOOM = "http://schemas.microsoft.com/deepzoom/2008"

################################################################################

def ceilLog2(x):
	"""Returns the ceiling of the log base 2 of the given long."""
	result = 0

	while x > (1L << result):
		result = result + 1

	return result

def clamp(x, l, r):
	"""Returns the value x clamped to to the range [l, r]."""
	if (x < l):
		x = l
	if (x > r):
		x = r
	return x

def divPow2RoundUp(x, n):
	"""Returns the value x divided by 2^n, rounded up."""
	return (x + (1L << n) - 1) / (1L << n);

################################################################################

def calcLodFromSize(size):
	"""Returns the level of detail number given its size."""
	return ceilLog2(max(size[0], size[1]))

def calcLodSize(finestLodSize, lod):
	"""Returns the size of the given level of detail."""
	lodDiff = calcLodFromSize(finestLodSize) - lod
	return (divPow2RoundUp(finestLodSize[0], lodDiff), divPow2RoundUp(finestLodSize[1], lodDiff))

################################################################################

def ensurePath(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def retry(attempts, backoff=2):
    """Retries a function or method until it returns or
    the number of attempts has been reached."""

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    attempts = int(math.floor(attempts))
    if attempts < 0:
        raise ValueError("attempts must be 0 or greater")

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            last_exception = None
            for _ in xrange(attempts):
                try:
                    return f(*args, **kwargs)
                except Exception as exception:
                    last_exception = exception
                    time.sleep(backoff**(attempts + 1))
            raise last_exception
        return f_retry
    return deco_retry

@retry(6)
def safeOpen(path):
    return StringIO.StringIO(urllib.urlopen(path).read())

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
	def __init__(self, imagePath, x, y, width, height, zOrder, minRenderWidthInPixels, numFadeInLevels):
		self.imagePath = imagePath
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.zOrder = zOrder
		self.minRenderWidthInPixels = minRenderWidthInPixels
		self.numFadeInLevels = numFadeInLevels
		self.imageSize = (0,0)

	def finestLod(self, finestLodSize):
		"""Returns the scene node's finest level of detail. The scene node will still be rendered to overlapping
		tiles at a finer level of detail than this, but it will be upsampled.
		"""
		return calcLodFromSize(finestLodSize) - int(math.floor(math.log(finestLodSize[0] * self.width / self.imageSize[0], 2)))

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

	def renderToTile(self, destinationFolder, finestLodSize, tile, opacity, tilerArgsFile):

		lod = tile[0]
		tileX = tile[1]
		tileY = tile[2]

		lodSize = calcLodSize(finestLodSize, lod)
		sceneNodeLodRect = self.lodRect(finestLodSize, lod)
		scaleFactor = sceneNodeLodRect.width() / self.imageSize[0]

		tileRect = Rect(
			tileX * TILE_SIZE - 1,
			tileY * TILE_SIZE - 1,
			(tileX + 1) * TILE_SIZE + 1,
			(tileY + 1) * TILE_SIZE + 1).intersection(Rect(0, 0, lodSize[0], lodSize[1]))

		srcOffset = (
			(tileRect.x0 - sceneNodeLodRect.x0) / scaleFactor,
			(tileRect.y0 - sceneNodeLodRect.y0) / scaleFactor)

		outputPath = os.path.join(
			ensurePath(os.path.join(destinationFolder, str(lod))),
			"{0}_{1}.png".format(tileX, tileY))

		# If the tiler args file is non-null, we're using tiler. Otherwise, we render the tile
		# using ImageMagick's convert and composite applications
		if tilerArgsFile is None:

			if opacity is not 255:
				print ""
				sys.exit("Exiting. Partial transparency not currently supported when using ImageMagick.")

			# Write a tile image with only this scene node's contribution in it to convertOutputPath.
			convertOutputPath = outputPath
			if os.path.exists(outputPath):
				convertOutputPath = os.path.splitext(outputPath)[0] + "_convert_temp.png"

			convertArgs = [
				"convert",
				self.imagePath,
				"-background", "transparent",
				"-virtual-pixel", "transparent",
				"-interpolate", "Bicubic",
				"-define", "distort:viewport={0}x{1}+0+0".format(tileRect.width(), tileRect.height()),
				"-distort", "SRT", "{0},{1}, {2}, 0, 0,0".format(srcOffset[0], srcOffset[1], scaleFactor),
				convertOutputPath
			]

			process = subprocess.Popen(convertArgs)
			process.wait()

			# If another scene node has already made a contribution to this tile, then composite this scene node's
			# contribution over it.
			if outputPath != convertOutputPath:
				compositeArgs = [
					"composite",
					convertOutputPath,
					outputPath,
					outputPath
				]

				process = subprocess.Popen(compositeArgs)
				process.wait()

				os.remove(convertOutputPath)

		else:
			# Write the details for rendering the tile to the tilerArgsFile. The tiler application will handle
			# the actually render.
			tilerArgsFile.write("{0} {1} {2} {3} {4} {5} {6}\n".format(outputPath, tileRect.width(), tileRect.height(), srcOffset[0], srcOffset[1], scaleFactor, opacity))

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

def getElementValue(element):
	return element.childNodes[0].nodeValue

def getChildElementValue(element, childTagName):
	elements = element.getElementsByTagName(childTagName)
	if len(elements) > 0:
		return getElementValue(element.getElementsByTagName(childTagName)[0])
	else:
		return None

def parseSparseImageSceneGraph(sceneGraphUrl):

	doc = xml.dom.minidom.parse(safeOpen(sceneGraphUrl))

	sceneGraph = {
		"aspectRatio" : float(getElementValue(doc.getElementsByTagName("AspectRatio")[0]))
	}

	containingFolder = os.path.dirname(sceneGraphUrl)

	sceneNodes = sceneGraph["sceneNodes"] = []

	for sceneNodeNode in doc.getElementsByTagName("SceneNode"):

		minRenderWidthInPixels = getChildElementValue(sceneNodeNode, "MinRenderWidthInPixels")
		minRenderWidthInPixels = 1 if minRenderWidthInPixels is None else minRenderWidthInPixels
		if minRenderWidthInPixels <= 0:
			sys.exit("MinWidth must be positive")

		numFadeInLevels = getChildElementValue(sceneNodeNode, "NumFadeInLevels")
		numFadeInLevels = 0 if numFadeInLevels is None else numFadeInLevels
		if numFadeInLevels < 0:
			sys.exit("NumFadeInLevels must be non-negative")

		sceneNode = SceneNode(
			os.path.join(containingFolder, getChildElementValue(sceneNodeNode, "FileName").replace('\\', '/')),
			float(getChildElementValue(sceneNodeNode, "x")),
			float(getChildElementValue(sceneNodeNode, "y")),
			float(getChildElementValue(sceneNodeNode, "Width")),
			float(getChildElementValue(sceneNodeNode, "Height")),
			int(getChildElementValue(sceneNodeNode, "ZOrder")),
			int(minRenderWidthInPixels),
			int(numFadeInLevels)
		)

		sceneNode.imageSize = Image.open(sceneNode.imagePath).size

		sceneNodes.append(sceneNode)

	# Sort the scene nodes by ascending z-order
	sceneNodes.sort(key=lambda sceneNode: sceneNode.zOrder)

	return sceneGraph

################################################################################

def writeDzi(destination, dziSize):
    """Save descriptor file."""
    file = open(destination, "w")
    doc = xml.dom.minidom.Document()

    image = doc.createElementNS(NS_DEEPZOOM, "Image")
    image.setAttribute("xmlns", NS_DEEPZOOM)
    image.setAttribute("TileSize", str(TILE_SIZE))
    image.setAttribute("Overlap", "1")
    image.setAttribute("Format", "png")

    size = doc.createElementNS(NS_DEEPZOOM, "Size")
    size.setAttribute("Width", str(dziSize[0]))
    size.setAttribute("Height", str(dziSize[1]))

    image.appendChild(size)
    doc.appendChild(image)

    descriptor = doc.toprettyxml(encoding="UTF-8")

    file.write(descriptor)
    file.close()

################################################################################

def renderTileImages(imagesFolder, compositeImageSize, sceneNodes, useImageMagick):
	"""Renders the scene nodes to the tile images that comprise the composite image."""

	# The finest LOD of the composite image
	finestLod = calcLodFromSize(compositeImageSize)

	# Iterate through each scene node in order of ascending draw order
	for sceneNode in sceneNodes:

		sys.stdout.write("{0} {1}x{2}: ".format(sceneNode.imagePath, sceneNode.imageSize[0], sceneNode.imageSize[1]))
		sys.stdout.flush()

		# The finest LOD of the scene node. This is the finest LOD at which the scene node
		# generates tiles. However, it will also be rendered to overlapping tiles at finer LODs.
		sceneNodeFinestLod = sceneNode.finestLod(compositeImageSize)

		# The coarsest LOD of the scene node. We ensure that the scene node is never rendered to a tile at less than
		# its min width. However, when the coarsest LOD is downsampled, the image may appear smaller than this width.
		sceneNodeCoarsestLod = sceneNodeFinestLod
		while sceneNodeCoarsestLod > 0 and sceneNode.lodRect(compositeImageSize, sceneNodeCoarsestLod - 1).width() >= sceneNode.minRenderWidthInPixels:
			sceneNodeCoarsestLod -= 1


		tilerArgsFile = None
		if not useImageMagick:
			tilerArgsFilePath = "tilerArgs.txt"
			tilerArgsFile = open(tilerArgsFilePath, "w")

		# Iterate over all possible LODs to which the scene node may be rendered
		for lod in reversed(range(sceneNodeCoarsestLod, finestLod + 1)):

			lodProgressStr = ("" if lod is not sceneNodeFinestLod else "*") + str(lod)

			if useImageMagick:
				sys.stdout.write((" " if lod is not finestLod else "") + lodProgressStr)
				sys.stdout.flush()
			else:
				tilerArgsFile.write("#" + lodProgressStr + "\n")

			# The tiles that the scene node overlaps in the LOD
			tileRect = sceneNode.tileRect(compositeImageSize, lod)

			if tileRect.empty():
				break

			# Set the opacity for this level of detail based on the number of "fade in levels". The number of fade
			# in levels specifies over how many levels the image fades from transparent to fullly opaque.
			#
			# For example:
			#   * If num fade in levels is set to 1, then sceneNodeCoarsestLevel would get half opacity and the
			#     rest would get full opacity.
			#   * If num fade in levels is 3, then sceneNodeCoarsestLevel would get quarter opacity, the next level
			#     would get half opacity, next would get three quarters, and rest would get full opacity.
			lodOpacity = max(0, min(255, int(255 * (lod - sceneNodeCoarsestLod + 1) / float(sceneNode.numFadeInLevels + 1))));

			tileRectsToRender = []

			if lod <= sceneNodeFinestLod:
				# If the lod is within the range of the LODs for which the scene node generates tiles,
				# we know it needs to be rendered.
				tileRectsToRender.append(tileRect)
			else:
				# Otherwise, check if the scene node overlaps any tiles generated by another scene node at this LOD.
				for otherSceneNode in sceneNodes:
					if (not sceneNode is otherSceneNode) and lod <= otherSceneNode.finestLod(compositeImageSize):
						otherTileRect = otherSceneNode.tileRect(compositeImageSize, lod)
						tileRectIntersection = tileRect.intersection(otherTileRect)
						if not tileRectIntersection.empty():
							tileRectsToRender.append(tileRectIntersection)

			tileCoordsRendered = set()

			# Iterate over all of the tile rects to render and render the containing tiles. If another scene node
			# has already rendered to the tile, then this scene node will composite over the previous results.
			# (That's why we render in ascending draw order.)
			for tileRectToRender in tileRectsToRender:
				for tileCoord in tileRectToRender:
					# Make sure we don't waste time rendering the same tile coordinate twice. This would happen
					# if multiple scene nodes overlapped this one, each one contributing a tile rect to render.
					if not tileCoord in tileCoordsRendered:
						sceneNode.renderToTile(imagesFolder, compositeImageSize, (lod, tileCoord[0], tileCoord[1]), lodOpacity, tilerArgsFile)
						tileCoordsRendered.add(tileCoord)

		if not useImageMagick:

			tilerArgsFile.close()

			scriptPath = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "tiler"))

			if not os.path.exists:
				sys.exit("\n\nExiting. Could not find tiler application at: " + scriptPath + ". Did you build it?")

			tilerArgs = [
				scriptPath,
				sceneNode.imagePath,
				tilerArgsFilePath
			]

			process = subprocess.Popen(tilerArgs)
			process.wait()

			os.remove(tilerArgsFilePath)

		sys.stdout.write("\n")
		sys.stdout.flush();

def main():

	parser = optparse.OptionParser(usage="Usage: %prog [options] sceneGraph outputName")
	parser.add_option("--use-ImageMagick", action="store_true", dest="useImageMagick", help="Use the ImageMagick " +
		"convert and composite applications instead of tiler. This is useful if tiler can't be compiled, " +
		"but should only be used if necessary since tiler provides much better performance.")

	(options, args) = parser.parse_args()

	if len(args) != 2:
		parser.print_help()
		sys.exit(1)

	sceneGraphPath = args[0]
	imagesFolder = args[1] + "_files"
	outputDzi = args[1] + ".dzi"

	sceneGraph = parseSparseImageSceneGraph(sceneGraphPath)
	compositeImageSize = determineCompositeImageSize(sceneGraph)

	if compositeImageSize[0] < 1 or compositeImageSize[1] < 1:
		sys.stderr.write("Error calculating the size of the composite image.")
		sys.exit(1)

	print "Composite image size: {0}x{1}".format(compositeImageSize[0], compositeImageSize[1])
	print "Finest level of detail: {0}".format(calcLodFromSize(compositeImageSize))

	writeDzi(outputDzi, compositeImageSize)

	renderTileImages(imagesFolder, compositeImageSize, sceneGraph["sceneNodes"], options.useImageMagick)

################################################################################

if __name__ == "__main__":
	main()
