#!/usr/bin/python
import sys, Image
from xmlobject import XMLFile

def parseSparseImageSceneGraph(sceneGraphPath):
	x = XMLFile(path=sceneGraphPath)

	sceneNodes = []

	for sceneNodeNode in x["SceneGraph"]["SceneNode"]:
		s = {}
		s["fileName"] = sceneNodeNode.FileName._children[0]._value
		s["x"] = float(sceneNodeNode.x._children[0]._value)
		s["y"] = float(sceneNodeNode.y._children[0]._value)
		s["width"] = float(sceneNodeNode.Width._children[0]._value)
		s["height"] = float(sceneNodeNode.Height._children[0]._value)
		s["zOrder"] = int(sceneNodeNode.ZOrder._children[0]._value)

		sceneNodes.append(s)

	return sceneNodes

if (len(sys.argv) != 2):
	print "usage: "
	exit(0)

sceneNodes = parseSparseImageSceneGraph(sys.argv[1])

for sceneNode in sceneNodes:
	print sceneNode["width"]