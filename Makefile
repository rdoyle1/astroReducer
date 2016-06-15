all:
	rm -rf *.pyc
	zip -r ../reducer.zip *

clean:
	rm ../reducer.zip
