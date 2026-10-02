.PHONY: icons build package all clean

all: icons build package

icons:
	python3 packaging/make_icons.py

build:
	bash packaging/build-in-docker.sh

package:
	bash packaging/package.sh

clean:
	rm -rf build dist
