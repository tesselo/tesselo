FROM remotepixel/amazonlinux-gdal:latest
# Install python libraries.
ADD requirements.txt /tmp/requirements.txt
RUN mkdir /tmp/vendored
RUN pip3 install -t /tmp/vendored -r /tmp/requirements.txt

# Archive python modules.
RUN cd /tmp && zip -r9q /tmp/package.zip vendored/*

# Archive GDAL shared libraries.
RUN cd $APP_DIR/local && zip -r9q --symlinks /tmp/package.zip lib/*.so*
RUN cd $APP_DIR/local && zip -r9q /tmp/package.zip share
