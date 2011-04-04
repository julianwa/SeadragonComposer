#include <iostream>
#include <fstream>
#include <sstream>
#include <Magick++.h>
#include <sys/stat.h>

using namespace std;
using namespace Magick;

int main(int argc, char *argv[])
{
	auto_ptr<Image> img(new Image::Image(argv[1]));

	ifstream args("args.txt");

	while (!args.eof())
	{
		string line;
		getline(args, line);

		if (line.length() > 0)
		{
			stringstream lineStream(line);

			if (line[0] == '#')
			{
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

				lineStream >> outputFile >> tileSizeX >> tileSizeY >> sourceOffsetX >> sourceOffsetY >> scaleFactor;

				auto_ptr<Image> newImg(new Image::Image());

				*newImg = *img;

				img->virtualPixelMethod(TransparentVirtualPixelMethod);
				img->backgroundColor(Color(0, 0, 0, TransparentOpacity));

				stringstream viewport;
				viewport << tileSizeX << 'x' << tileSizeY << "+0+0";

				SetImageArtifact(newImg->image(), "distort:viewport", viewport.str().c_str());

				double distortArgs[] = { sourceOffsetX, sourceOffsetY, scaleFactor, 0, 0, 0 };

				newImg->distort(ScaleRotateTranslateDistortion, sizeof(distortArgs) / sizeof(double), distortArgs);

				struct stat stFileInfo;
				if (stat(outputFile.c_str(), &stFileInfo) == 0)
				{
					auto_ptr<Image> existingImg(new Image::Image(outputFile));
					existingImg->composite(*newImg, 0, 0, OverCompositeOp);
					existingImg->write(outputFile);
				}
				else
				{
					newImg->write(outputFile);
				}
			}
		}

	}

	return 0;
}