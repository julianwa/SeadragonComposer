#include <iostream>
#include <fstream>
#include <Magick++.h>
#include <sys/stat.h>

using namespace std;
using namespace Magick;

int main(int argc, char *argv[])
{
	auto_ptr<Image> img(new Image::Image(argv[1]));
	
	img->write("blah.jpg");

	ifstream args("args.txt");

	while (!args.eof())
	{
		string line;
		getline(args, line);

		char outputFile[4096];
		int tileSizeX;
		int tileSizeY;
		double sourceOffsetX;
		double sourceOffsetY;
		double scaleFactor;

		sscanf(line.c_str(), "%s %d %d %lf %lf %lf", outputFile, &tileSizeX, &tileSizeY, &sourceOffsetX, &sourceOffsetY, &scaleFactor);

		auto_ptr<Image> newImg(new Image::Image());
		
		*newImg = *img;
		
		img->virtualPixelMethod(TransparentVirtualPixelMethod);
		img->backgroundColor(Color(0, 0, 0, TransparentOpacity));

		char viewport[4096];
		sprintf(viewport, "%dx%d+0+0", tileSizeX, tileSizeY);

		SetImageArtifact(newImg->image(), "distort:viewport", viewport);

		double distortArgs[] = { sourceOffsetX, sourceOffsetY, scaleFactor, 0, 0, 0 };
		
		newImg->distort(ScaleRotateTranslateDistortion, sizeof(distortArgs) / sizeof(double), distortArgs);

		struct stat stFileInfo; 
		if (stat(outputFile, &stFileInfo) == 0)
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

	return 0;
}