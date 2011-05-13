
CC=g++
CFLAGS=-c -I/opt/local/include/ImageMagick
LDFLAGS=-L/opt/local/lib /opt/local/lib/libMagick++.dylib /opt/local/lib/libMagickCore.dylib
SOURCES=tiler.cpp
OBJECTS=$(SOURCES:.cpp=.o)
EXECUTABLE=tiler

all: $(SOURCES) $(EXECUTABLE)

$(EXECUTABLE): $(OBJECTS) 
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

.cpp.o:
	$(CC) $(CFLAGS) $< -o $@

clean: 
	rm -f *.o $(EXECUTABLE)
