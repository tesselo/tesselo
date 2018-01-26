FROM ubuntu:xenial

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:webupd8team/java
RUN apt-get update
RUN echo debconf shared/accepted-oracle-license-v1-1 select true | debconf-set-selections
RUN echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections
RUN apt-get install -y oracle-java8-installer
RUN apt-get install -y unzip
RUN apt-get install -y curl
# Install ProductDownload
RUN curl -O -L https://github.com/kraftek/awsdownload/releases/download/1.7.1/ProductDownload-1.7.1.zip
RUN unzip ProductDownload-1.7.1.zip -d /
# Install Sen2Cor
# http://step.esa.int/main/third-party-plugins-2/sen2cor/
RUN curl -O -L http://step.esa.int/thirdparties/sen2cor/2.4.0/Sen2Cor-2.4.0-Linux64.run
RUN chmod +x ./Sen2Cor-2.4.0-Linux64.run
RUN ./Sen2Cor-2.4.0-Linux64.run
# java -jar /ProductDownload/ProductDownload.jar --sensor S2 --aws --out /Products --tiles 34TFQ --startdate 2018-01-01 --enddate 2018-01-10 --relative.orbit 93 --store AWS --cloudpercentage 75 --limit 1
