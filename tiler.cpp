#include <iostream>
#include <fstream>
#include <sstream>
#include <sys/stat.h>
#include <Magick++.h>

using namespace std;
using namespace Magick;

/// <summary>
/// Renders the given image to multiple tiles whose details are provided in a tile specs file. The format of the file is:
///
///		# comment
///		outputFile tileSizeX tileSizeY sourceOffsetX sourceOffsetY scaleFactor
///		...
///
/// </summary>
int main(int argc, char *argv[])
{
	if (argc != 3)
	{
		cout << "Usage: %prog <image> <tile specs>";
	}

	auto_ptr<Image> img(new Image::Image(argv[1]));

	// Set the background color and virtual pixel to transparent.
	img->virtualPixelMethod(TransparentVirtualPixelMethod);
	img->backgroundColor(Color(0, 0, 0, TransparentOpacity));

	ifstream tileSpecs(argv[2]);

	while (!tileSpecs.eof())
	{
		string line;
		getline(tileSpecs, line);

		if (line.length() > 0)
		{
			stringstream lineStream(line);

			if (line[0] == '#')
			{
				// Comments are echoed to stdout.
				char c;
				string s;
				lineStream >> c >> s;
				cout << s << ' ';
				flush(cout);
			}
			else
			{
				string outputFile;
				int tileSizeX;
				int tileSizeY;
				double sourceOffsetX;
				double sourceOffsetY;
				double scaleFactor;

				// Read the tile spec.
				lineStream >> outputFile >> tileSizeX >> tileSizeY >> sourceOffsetX >> sourceOffsetY >> scaleFactor;

				// Create an image for the tile that's a copy/reference to the source image.
				auto_ptr<Image> tileImg(new Image::Image());
				*tileImg = *img;

				// Set the viewport for the tile image to the tile size.
				stringstream viewport;
				viewport << tileSizeX << 'x' << tileSizeY << "+0+0";
				SetImageArtifact(tileImg->image(), "distort:viewport", viewport.str().c_str());

				// Distort the tile image using the the following distortion args, in the format: X,Y, Scale, Angle, NewX,NewY
				// (See http://www.imagemagick.org/Usage/distorts/#srt for details.)
				double distortArgs[] = { sourceOffsetX, sourceOffsetY, scaleFactor, 0, 0, 0 };
				tileImg->distort(ScaleRotateTranslateDistortion, sizeof(distortArgs) / sizeof(double), distortArgs);

				// If there's already an image for this tile then that means another image has rendered output
				// to it. In that case we composite this image's contribution over the contribution(s) of the previous
				// image(s).
				struct stat stFileInfo;
				if (stat(outputFile.c_str(), &stFileInfo) == 0)
				{
					auto_ptr<Image> existingTileImg(new Image::Image(outputFile));
					existingTileImg->composite(*tileImg, 0, 0, OverCompositeOp);
					existingTileImg->write(outputFile);
				}
				else
				{
					tileImg->write(outputFile);
				}
			}
		}
	}

	return 0;
}