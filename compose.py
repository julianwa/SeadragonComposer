#!/usr/bin/python
import sys, os, Image, math
from xmlobject import XMLFile

if (len(sys.argv) != 2):
	print "usage: "
	exit(0)

TileSize = 254L

def parseSparseImageSceneGraph(sceneGraphPath):
	x = XMLFile(path=sceneGraphPath)

	containingFolder = os.path.dirname(sceneGraphPath)

	sceneGraph = { "aspectRatio" : float(x["SceneGraph"]["AspectRatio"]._children[0]._value) }

	sceneNodes = []
	sceneGraph["sceneNodes"] = sceneNodes

	for sceneNodeNode in x["SceneGraph"]["SceneNode"]:

		s = {
			"imagePath" : os.path.join(containingFolder, sceneNodeNode.FileName._children[0]._value.replace('\\', '/')),
			"x": float(sceneNodeNode.x._children[0]._value),
			"y" : float(sceneNodeNode.y._children[0]._value),
			"width" : float(sceneNodeNode.Width._children[0]._value),
			"height" : float(sceneNodeNode.Height._children[0]._value),
			"zOrder" : int(sceneNodeNode.ZOrder._children[0]._value),
		}

		s["imageSize"] = Image.open(s["imagePath"]).size

		sceneNodes.append(s)

	return sceneGraph

def ceilLog2(x):
	result = 0
	while x > (1L << result):
		result = result + 1
	return result

def clamp(x, l, r):
	if (x < l):
		x = l
	if (x > r):
		x = r
	return x

def determineCompositeImageSize(sceneGraph):

	maxWidth = sys.float_info.min

	for sceneNode in sceneGraph["sceneNodes"]:
 		impliedWidth = sceneNode["imageSize"][0] / sceneNode["width"]
		if (impliedWidth > maxWidth):
			maxWidth = impliedWidth

	return (long(math.ceil(maxWidth)), long(math.ceil(maxWidth / sceneGraph["aspectRatio"])))

def intersectingTiles(compositeImageSize, sceneNode):

	finestLod = ceilLog2(compositeImageSize[0]) - int(math.floor(math.log(compositeImageSize[0] * sceneNode["width"] / sceneNode["imageSize"][0], 2)))

	lod = ceilLog2(compositeImageSize[0])
	lodSize = compositeImageSize

	tiles = []

	while lod > 1:

		if lod <= finestLod:
			lodBounds = (
					sceneNode["x"] * lodSize[0],
					sceneNode["y"] * lodSize[1],
					(sceneNode["x"] + sceneNode["width"]) * lodSize[0],
					(sceneNode["y"] + sceneNode["height"]) * lodSize[1]
			)
			discreteLodBounds = (
				clamp(long(math.floor(lodBounds[0])), 0, lodSize[0]),
				clamp(long(math.floor(lodBounds[1])), 0, lodSize[1]),
				clamp(long(math.ceil(lodBounds[2])), 0, lodSize[0]),
				clamp(long(math.ceil(lodBounds[3])), 0, lodSize[1])
			)

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

		lodSize = ((lodSize[0] + 1L) / 2L, (lodSize[1] + 1L) / 2L)
		lod = lod - 1

	return tiles

sceneGraph = parseSparseImageSceneGraph(sys.argv[1])
compositeImageSize = determineCompositeImageSize(sceneGraph)

for sceneNode in sceneGraph["sceneNodes"]:
	tiles = intersectingTiles(compositeImageSize, sceneNode)
	print "num tiles: " + str(len(tiles))

