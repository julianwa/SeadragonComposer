#!/usr/bin/python
import sys, os, Image, math
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

	def lodBounds(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in pixels in the given level of detail, expressed as [x0,y0,x1,y1] with floats."""
		lodSize = calcLodSize(finestLodSize, lod)
		return (
			sceneNode.x * lodSize[0],
			sceneNode.y * lodSize[1],
			(sceneNode.x + sceneNode.width) * lodSize[0],
			(sceneNode.y + sceneNode.height) * lodSize[1]
		)

	def discreteLodBounds(self, finestLodSize, lod):
		"""Returns the bounds of the scene node in pixels in the given level of detail, expressed as [x0,y0,x1,y1] with longs."""
		lodBounds = self.lodBounds(finestLodSize, lod)
		lodSize = calcLodSize(finestLodSize, lod)
		return (
			clamp(long(math.floor(lodBounds[0])), 0, lodSize[0]),
			clamp(long(math.floor(lodBounds[1])), 0, lodSize[1]),
			clamp(long(math.ceil(lodBounds[2])), 0, lodSize[0]),
			clamp(long(math.ceil(lodBounds[3])), 0, lodSize[1])
		)

	def populateIntersectingTiles(self, finestLodSize):
		"""
		Populates the intersectingTiles instance variable with the set of tiles that this
		image intersects.
		"""
		tiles = []

		for lod in reversed(range(1, self.finestIntersectingLod(finestLodSize))):

			discreteLodBounds = self.discreteLodBounds(finestLodSize, lod)

			if (discreteLodBounds[2] - discreteLodBounds[0] <= 1 or discreteLodBounds[3] - discreteLodBounds[1] <= 1):
				break;

			tileBounds = (
				discreteLodBounds[0] / TileSize,
				discreteLodBounds[1] / TileSize,
				(discreteLodBounds[2] + (TileSize - 1)) / TileSize,
				(discreteLodBounds[3] + (TileSize - 1)) / TileSize
			)

			for tileY in range(tileBounds[1], tileBounds[3]):
				for tileX in range(tileBounds[0], tileBounds[2]):
					tiles.append((lod, tileX, tileY))

		self.intersectingTiles = tiles

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

	sceneNodes = []
	sceneGraph["sceneNodes"] = sceneNodes

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

	return sceneGraph


sceneGraph = parseSparseImageSceneGraph(sys.argv[1])
compositeImageSize = determineCompositeImageSize(sceneGraph)

tileRenders = {}

for sceneNode in sceneGraph["sceneNodes"]:
	sceneNode.populateIntersectingTiles(compositeImageSize)

	for tile in sceneNode.intersectingTiles:
		if not tile in tileRenders:
			tileRenders[tile] = set()
		tileRenders[tile].add(sceneNode)

tileRenderOrder = sorted(tileRenders.keys())

for tileToRender in tileRenderOrder:

	tileImage = Image.new("RGB", (TileSize, TileSize))

	sceneNodes = tileRenders[tileToRender]

	for sceneNode in sceneNodes:
		im = Image.open(sceneNode.imagePath)

	outputPath = os.path.join("blah", str(tileToRender[0]) + "_" + str(tileToRender[1]) + "_" + str(tileToRender[2]) + ".png")
	tileImage.save(outputPath)

	break
