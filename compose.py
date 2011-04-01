#!/usr/bin/python
import sys, os, Image, math, subprocess
from xmlobject import XMLFile

if (len(sys.argv) != 2):
	print "usage: "
	exit(0)

TileSize = 254L

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

def calcLodSize(finestLodSize, lod):
	"""Returns the size of the given level of detail."""
	lodDiff = ceilLog2(finestLodSize[0]) - lod
	return (divPow2RoundUp(finestLodSize[0], lodDiff), divPow2RoundUp(finestLodSize[1], lodDiff))

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
		return ceilLog2(finestLodSize[0]) - int(math.floor(math.log(finestLodSize[0] * sceneNode.width / sceneNode.imageSize[0], 2)))

	def lodRect(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in pixels at the given level of detail."""
		lodSize = calcLodSize(finestLodSize, lod)
		return Rect(
			sceneNode.x * lodSize[0],
			sceneNode.y * lodSize[1],
			(sceneNode.x + sceneNode.width) * lodSize[0],
			(sceneNode.y + sceneNode.height) * lodSize[1]
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
				discreteLodRect.x0 / TileSize,
				discreteLodRect.y0 / TileSize,
				(discreteLodRect.x1 + (TileSize - 1)) / TileSize,
				(discreteLodRect.y1 + (TileSize - 1)) / TileSize)
		else:
			return Rect()

	def renderToTile(self, finestLodSize, tile):

		lod = tile[0]
		tileX = tile[1]
		tileY = tile[2]

		lodSize = calcLodSize(compositeImageSize, lod)
		lodRect = Rect(0, 0, lodSize[0], lodSize[1])

		sceneNodeLodRect = sceneNode.lodRect(compositeImageSize, lod)

		scaleFactor = sceneNodeLodRect.width() / sceneNode.imageSize[0]

		tileRect = Rect(tileX * TileSize, tileY * TileSize, (tileX + 1) * TileSize, (tileY + 1) * TileSize).intersection(lodRect)

		srcOffset = ((tileRect.x0 - sceneNodeLodRect.x0) / scaleFactor, (tileRect.y0 - sceneNodeLodRect.y0) / scaleFactor)

		outputPath = os.path.join("argh", "{0}_{1}_{2}_{3}.png".format("blah", lod, tileX, tileY))

		args = [
			"convert",
			sceneNode.imagePath,
			"-background", "transparent",
			"-virtual-pixel", "transparent",
			"-interpolate", "Bicubic",
			"-define", "distort:viewport={0}x{1}+0+0".format(tileRect.width(), tileRect.height()),
			"-distort", "SRT", "{0},{1}, {2}, 0, 0,0".format(srcOffset[0], srcOffset[1], scaleFactor),
			outputPath
		]

		process = subprocess.Popen(args)
		process.wait()

def determineCompositeImageSize(sceneGraph):
	""" Determines the composite image size in pixels, based on the size and layout of the scene nodes."""
	maxWidth = sys.float_info.min

	for sceneNode in sceneGraph["sceneNodes"]:
		impliedWidth = sceneNode.imageSize[0] / sceneNode.width
		if (impliedWidth > maxWidth):
			maxWidth = impliedWidth

	return (long(math.ceil(maxWidth)), long(math.ceil(maxWidth / sceneGraph["aspectRatio"])))


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