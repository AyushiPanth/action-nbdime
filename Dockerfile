FROM debian:buster

## For chromedriver installation: wget/libgconf/unzip
RUN apt-get update -y && apt-get install -y \
    chromium \
    git \
    libgconf-2-4 \
    python3 \
    python3-pip \
    unzip \
    wget \
    xvfb

# This needs to be set to be compatible with the version of chromium in this Debian
ARG CHROMEDRIVER_VERSION="83.0.4103.39"

# Download, unzip, and install chromedriver
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip

# Create directory for project name
RUN mkdir -p /opt/action-nbdime/downloads

ARG SELENIUM_VERSION="3.141.0"
ARG NBDIME_VERSION="2.1.0"
## Python project dependencies
RUN pip3 install selenium==${SELENIUM_VERSION} nbdime==${NBDIME_VERSION}

COPY entrypoint.py /opt/action-nbdime/entrypoint.py
RUN chmod +x /opt/action-nbdime/entrypoint.py

# Set display port and dbus env to avoid Chromium hanging
ENV DISPLAY=:99
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

ENTRYPOINT ["/opt/action-nbdime/entrypoint.py"]
